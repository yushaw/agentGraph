"""
Unit tests for web_search parallel content cleaning.
Tests that content cleaning is executed in parallel with concurrency limit.
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
import time


class TestWebSearchParallelCleaning:
    """Test web_search parallel content cleaning"""

    @pytest.mark.asyncio
    async def test_parallel_cleaning_execution(self):
        """Content cleaning should be executed in parallel"""
        # Mock httpx response
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "data": [
                {
                    "title": f"Result {i}",
                    "url": f"https://example.com/{i}",
                    "content": "A" * 3000,  # Long enough to trigger cleaning
                    "description": f"Description {i}"
                }
                for i in range(5)
            ]
        }
        mock_response.status_code = 200

        # Track cleaning call times
        cleaning_times = []

        async def mock_clean(content, processors, context):
            """Mock cleaning that takes 0.1 seconds"""
            start = time.time()
            await asyncio.sleep(0.1)  # Simulate LLM call
            cleaning_times.append(time.time() - start)
            return f"Cleaned: {content[:50]}"

        # Mock dependencies
        with patch("httpx.Client") as mock_client_class:
            mock_client = MagicMock()
            mock_client.__enter__.return_value = mock_client
            mock_client.post.return_value = mock_response
            mock_client_class.return_value = mock_client

            with patch("generalAgent.tools.content_processors.get_content_cleaner") as mock_get_cleaner:
                mock_cleaner = MagicMock()
                mock_cleaner.should_process.return_value = True
                mock_cleaner.process = mock_clean
                mock_get_cleaner.return_value = mock_cleaner

                with patch("generalAgent.tools.content_processors.run_content_pipeline", side_effect=mock_clean):
                    with patch.dict("os.environ", {"JINA_API_KEY": "test_key"}):
                        from generalAgent.tools.builtin.jina_search import web_search

                        # Measure total execution time
                        start_time = time.time()
                        result_json = await web_search.ainvoke({
                            "query": "test query",
                            "num_results": 5
                        })
                        total_time = time.time() - start_time

        # Verify parallel execution
        # If serial: 5 * 0.1 = 0.5s
        # If parallel: max(0.1, 0.1, 0.1, 0.1, 0.1) = ~0.1s
        assert len(cleaning_times) == 5, f"Expected 5 cleaning calls, got {len(cleaning_times)}"
        # Allow some overhead, but should be much faster than serial
        assert total_time < 0.3, f"Parallel execution should be < 0.3s, got {total_time:.2f}s (serial would be ~0.5s)"

        # Verify results
        import json
        result = json.loads(result_json)
        assert "results" in result
        assert len(result["results"]) == 5
        # All results should have cleaned content
        for r in result["results"]:
            assert r["content"].startswith("Cleaned:")

    @pytest.mark.asyncio
    async def test_concurrency_limit(self):
        """Should respect max_concurrent=10 limit"""
        # Mock httpx response with 15 results (more than limit)
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "data": [
                {
                    "title": f"Result {i}",
                    "url": f"https://example.com/{i}",
                    "content": "A" * 3000,
                    "description": f"Description {i}"
                }
                for i in range(15)
            ]
        }
        mock_response.status_code = 200

        # Track concurrent executions
        current_concurrent = 0
        max_concurrent_seen = 0
        lock = asyncio.Lock()

        async def mock_clean(content, processors, context):
            """Mock cleaning that tracks concurrency"""
            nonlocal current_concurrent, max_concurrent_seen

            async with lock:
                current_concurrent += 1
                max_concurrent_seen = max(max_concurrent_seen, current_concurrent)

            await asyncio.sleep(0.05)  # Simulate work

            async with lock:
                current_concurrent -= 1

            return f"Cleaned: {content[:50]}"

        with patch("httpx.Client") as mock_client_class:
            mock_client = MagicMock()
            mock_client.__enter__.return_value = mock_client
            mock_client.post.return_value = mock_response
            mock_client_class.return_value = mock_client

            with patch("generalAgent.tools.content_processors.get_content_cleaner") as mock_get_cleaner:
                mock_cleaner = MagicMock()
                mock_cleaner.should_process.return_value = True
                mock_get_cleaner.return_value = mock_cleaner

                with patch("generalAgent.tools.content_processors.run_content_pipeline", side_effect=mock_clean):
                    with patch.dict("os.environ", {"JINA_API_KEY": "test_key"}):
                        from generalAgent.tools.builtin.jina_search import web_search

                        await web_search.ainvoke({
                            "query": "test query",
                            "num_results": 15
                        })

        # Verify concurrency limit was respected
        assert max_concurrent_seen <= 10, f"Max concurrent should be <= 10, got {max_concurrent_seen}"
        print(f"Max concurrent executions seen: {max_concurrent_seen}")

    @pytest.mark.asyncio
    async def test_error_handling_doesnt_break_other_results(self):
        """If one cleaning fails, others should still complete"""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "data": [
                {
                    "title": f"Result {i}",
                    "url": f"https://example.com/{i}",
                    "content": "A" * 3000,
                    "description": f"Description {i}"
                }
                for i in range(5)
            ]
        }
        mock_response.status_code = 200

        call_count = 0

        async def mock_clean_with_error(content, processors, context):
            """Mock cleaning that fails on 3rd call"""
            nonlocal call_count
            call_count += 1
            if call_count == 3:
                raise ValueError("Simulated cleaning error")
            await asyncio.sleep(0.05)
            return f"Cleaned: {content[:50]}"

        with patch("httpx.Client") as mock_client_class:
            mock_client = MagicMock()
            mock_client.__enter__.return_value = mock_client
            mock_client.post.return_value = mock_response
            mock_client_class.return_value = mock_client

            with patch("generalAgent.tools.content_processors.get_content_cleaner") as mock_get_cleaner:
                mock_cleaner = MagicMock()
                mock_cleaner.should_process.return_value = True
                mock_get_cleaner.return_value = mock_cleaner

                with patch("generalAgent.tools.content_processors.run_content_pipeline", side_effect=mock_clean_with_error):
                    with patch.dict("os.environ", {"JINA_API_KEY": "test_key"}):
                        from generalAgent.tools.builtin.jina_search import web_search

                        # Should not raise exception
                        result_json = await web_search.ainvoke({
                            "query": "test query",
                            "num_results": 5
                        })

        # Verify 5 calls were made (all attempted despite error)
        assert call_count == 5

        # Verify 4 results have cleaned content (1 failed)
        import json
        result = json.loads(result_json)
        cleaned_count = sum(1 for r in result["results"] if r["content"].startswith("Cleaned:"))
        assert cleaned_count == 4, f"Expected 4 cleaned results (1 failed), got {cleaned_count}"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
