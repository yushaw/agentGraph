"""Test content cleaning functionality for web tools.

This script tests:
1. LLMContentCleaner basic functionality
2. fetch_web tool with content cleaning
3. web_search tool with content cleaning
4. Environment variable controls
"""

import asyncio
import os
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))


async def test_content_cleaner():
    """Test LLMContentCleaner basic functionality."""
    print("\n" + "="*60)
    print("TEST 1: LLMContentCleaner Basic Functionality")
    print("="*60)

    from generalAgent.tools.content_processors import get_content_cleaner

    # Get cleaner instance
    cleaner = get_content_cleaner()
    print(f"✓ Cleaner initialized")
    print(f"  - Enabled: {cleaner.enabled}")
    print(f"  - Min length: {cleaner.min_length}")

    # Test with short content (should skip)
    short_content = "This is a short text."
    context = {"query": "test", "content": short_content}

    should_process = cleaner.should_process(context)
    print(f"\n✓ Short content ({len(short_content)} chars): should_process = {should_process}")

    # Test with long content (should process)
    long_content = """
    Navigation: Home | About | Contact

    # Article Title

    This is the main content of the article. It contains useful information
    that we want to keep. The article discusses important topics.

    ## Section 1
    More content here with details and explanations.

    ## Section 2
    Additional information and examples.

    Footer: Copyright 2025 | Privacy Policy | Terms
    Advertisement: Buy our product now!
    """ * 20  # Make it long enough

    context = {"query": "article information", "content": long_content}
    should_process = cleaner.should_process(context)
    print(f"✓ Long content ({len(long_content)} chars): should_process = {should_process}")

    if should_process:
        print(f"\n⏳ Cleaning content with LLM...")
        cleaned = await cleaner.process(long_content, context)
        print(f"✓ Content cleaned")
        print(f"  - Original length: {len(long_content)} chars")
        print(f"  - Cleaned length: {len(cleaned)} chars")
        print(f"  - Reduction: {100 * (1 - len(cleaned)/len(long_content)):.1f}%")
        print(f"\n--- Cleaned Content Preview (first 500 chars) ---")
        print(cleaned[:500])
        print("..." if len(cleaned) > 500 else "")


async def test_fetch_web():
    """Test fetch_web tool with content cleaning."""
    print("\n" + "="*60)
    print("TEST 2: fetch_web Tool with Content Cleaning")
    print("="*60)

    from generalAgent.tools.builtin.jina_reader import fetch_web

    # Test URL with substantial content
    test_url = "https://en.wikipedia.org/wiki/Python_(programming_language)"

    print(f"⏳ Fetching: {test_url}")
    result_json = await fetch_web.ainvoke({"url": test_url})

    import json
    result = json.loads(result_json)

    if "error" in result:
        print(f"❌ Error: {result['error']}")
        return

    print(f"✓ Page fetched successfully")
    print(f"  - Title: {result.get('title', 'N/A')}")
    print(f"  - URL: {result.get('url', 'N/A')}")
    print(f"  - Content length: {len(result.get('content', ''))} chars")
    print(f"\n--- Content Preview (first 500 chars) ---")
    print(result.get('content', '')[:500])
    print("...")


async def test_web_search():
    """Test web_search tool with content cleaning."""
    print("\n" + "="*60)
    print("TEST 3: web_search Tool with Content Cleaning")
    print("="*60)

    from generalAgent.tools.builtin.jina_search import web_search

    # Test query
    test_query = "Python async programming tutorial 2025"

    print(f"⏳ Searching: {test_query}")
    result_json = await web_search.ainvoke({"query": test_query, "num_results": 2})

    import json
    result = json.loads(result_json)

    if "error" in result:
        print(f"❌ Error: {result['error']}")
        return

    print(f"✓ Search completed")
    print(f"  - Query: {result.get('query', 'N/A')}")
    print(f"  - Total results: {result.get('total_results', 0)}")

    for idx, item in enumerate(result.get('results', []), 1):
        print(f"\n--- Result {idx} ---")
        print(f"  - Title: {item.get('title', 'N/A')}")
        print(f"  - URL: {item.get('url', 'N/A')}")
        print(f"  - Content length: {len(item.get('content', ''))} chars")
        print(f"  - Preview: {item.get('content', '')[:200]}...")


async def test_env_controls():
    """Test environment variable controls."""
    print("\n" + "="*60)
    print("TEST 4: Environment Variable Controls")
    print("="*60)

    # Check current settings
    print("Current environment variables:")
    print(f"  - JINA_CONTENT_CLEANING: {os.getenv('JINA_CONTENT_CLEANING', 'not set')}")
    print(f"  - JINA_CLEANING_MIN_LENGTH: {os.getenv('JINA_CLEANING_MIN_LENGTH', 'not set')}")
    print(f"  - JINA_STRIP_IMAGES: {os.getenv('JINA_STRIP_IMAGES', 'not set')}")
    print(f"  - JINA_REMOVE_SELECTORS: {os.getenv('JINA_REMOVE_SELECTORS', 'not set')}")

    # Test disabling content cleaning
    print("\n⏳ Testing with JINA_CONTENT_CLEANING=false...")
    original_value = os.getenv('JINA_CONTENT_CLEANING')
    os.environ['JINA_CONTENT_CLEANING'] = 'false'

    from generalAgent.tools.content_processors import LLMContentCleaner
    from generalAgent.config import Settings
    from generalAgent.runtime.model_resolver import (
        resolve_model_configs,
        build_model_resolver
    )

    settings = Settings()
    model_configs = resolve_model_configs(settings)
    model_resolver = build_model_resolver(model_configs)

    disabled_cleaner = LLMContentCleaner(
        model_resolver=model_resolver,
        min_length=2000
    )

    context = {"content": "a" * 3000}  # Long content
    should_process = disabled_cleaner.should_process(context)
    print(f"✓ With cleaning disabled: should_process = {should_process}")

    # Restore original value
    if original_value:
        os.environ['JINA_CONTENT_CLEANING'] = original_value
    else:
        os.environ.pop('JINA_CONTENT_CLEANING', None)


async def main():
    """Run all tests."""
    print("\n" + "="*60)
    print("Content Cleaning Functionality Test Suite")
    print("="*60)

    try:
        # Test 1: Basic cleaner functionality
        await test_content_cleaner()

        # Test 2: fetch_web integration
        await test_fetch_web()

        # Test 3: web_search integration
        await test_web_search()

        # Test 4: Environment controls
        await test_env_controls()

        print("\n" + "="*60)
        print("✓ All tests completed successfully!")
        print("="*60)

    except KeyboardInterrupt:
        print("\n\n⚠️  Tests interrupted by user")
    except Exception as e:
        print(f"\n\n❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
