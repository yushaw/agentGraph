"""Context compression and summarization.

This module provides utilities for compressing conversation history
when approaching token limits.
"""

from __future__ import annotations

from typing import List, Literal

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage

from generalAgent.config.settings import ContextManagementSettings
from generalAgent.graph.message_utils import clean_message_history, truncate_messages_safely


# Prompt templates for compression
COMPACT_PROMPT = """Your task is to create a detailed summary of the conversation so far, paying close attention to the user's explicit requests and your previous actions.
This summary should be thorough in capturing technical details, code patterns, and architectural decisions that would be essential for continuing development work without losing context.

Before providing your final summary, wrap your analysis in <analysis> tags to organize your thoughts and ensure you've covered all necessary points. In your analysis process:

1. Chronologically analyze each message and section of the conversation. For each section thoroughly identify:
   - The user's explicit requests and intents
   - Your approach to addressing the user's requests
   - Key decisions, technical concepts and code patterns
   - Specific details like:
     - file names
     - full code snippets
     - function signatures
     - file edits

- Errors that you ran into and how you fixed them
- Pay special attention to specific user feedback that you received, especially if the user told you to do something differently.

2. Double-check for technical accuracy and completeness, addressing each required element thoroughly.

Your summary should include the following sections:

1. Primary Request and Intent: Capture all of the user's explicit requests and intents in detail
2. Key Technical Concepts: List all important technical concepts, technologies, and frameworks discussed.
3. Files and Code Sections: Enumerate specific files and code sections examined, modified, or created. Pay special attention to the most recent messages and include full code snippets where applicable and include a summary of why this file read or edit is important.
4. Errors and fixes: List all errors that you ran into, and how you fixed them. Pay special attention to specific user feedback that you received, especially if the user told you to do something differently.
5. Problem Solving: Document problems solved and any ongoing troubleshooting efforts.
6. All user messages: List ALL user messages that are not tool results. These are critical for understanding the users' feedback and changing intent.
7. Pending Tasks: Outline any pending tasks that you have explicitly been asked to work on.
8. Current Work: Describe in detail precisely what was being worked on immediately before this summary request, paying special attention to the most recent messages from both user and assistant. Include file names and code snippets where applicable.
9. Optional Next Step: List the next step that you will take that is related to the most recent work you were doing. IMPORTANT: ensure that this step is DIRECTLY in line with the user's explicit requests, and the task you were working on immediately before this summary request. If your last task was concluded, then only list next steps if they are explicitly in line with the users request. Do not start on tangential requests without confirming with the user first.
   If there is a next step, include direct quotes from the most recent conversation showing exactly what task you were working on and where you left off. This should be verbatim to ensure there's no drift in task interpretation.

Please provide your summary based on the conversation so far, following this structure and ensuring precision and thoroughness in your response.
Format your response as:

<analysis>
[Your thought process, ensuring all points are covered thoroughly and accurately]
</analysis>

<summary>
1. Primary Request and Intent:
   [Detailed description]

2. Key Technical Concepts:
   - [Concept 1]
   - [Concept 2]
   - [...]

3. Files and Code Sections:
   - [File Name 1]
     - [Summary of why this file is important]
     - [Summary of the changes made to this file, if any]
     - [Important Code Snippet]
   - [File Name 2]
     - [Important Code Snippet]
   - [...]

4. Errors and fixes:
   - [Detailed description of error 1]:
     - [How you fixed the error]
     - [User feedback on the error if any]
   - [...]

5. Problem Solving:
   [Description of solved problems and ongoing troubleshooting]

6. All user messages:
   - [Detailed non tool use user message]
   - [...]

7. Pending Tasks:
   - [Task 1]
   - [Task 2]
   - [...]

8. Current Work:
   [Precise description of current work]

9. Optional Next Step:
   [Optional Next step to take]
</summary>"""


SUMMARIZE_PROMPT = """You are a helpful AI assistant tasked with summarizing conversations.

Summarize this coding conversation in under 290 characters. Capture the main task, key files, problems addressed, and current status.

Format: A single concise paragraph."""


class ContextCompressor:
    """Compresses conversation history using LLM-based summarization.

    This class implements a layered compression strategy:
    1. Keep recent N messages uncompressed
    2. Compact middle messages (detailed summary)
    3. Summarize old messages (extreme compression)
    """

    def __init__(self, context_settings: ContextManagementSettings):
        self.context_settings = context_settings

    def partition_messages(
        self,
        messages: List[BaseMessage],
        strategy: Literal["compact", "summarize"],
    ) -> dict[str, List[BaseMessage]]:
        """Partition messages into system, old, middle, and recent layers.

        Args:
            messages: Full conversation history
            strategy: Compression strategy to apply

        Returns:
            Dictionary with keys: 'system', 'old', 'middle', 'recent'
        """
        # Separate system messages
        system_msgs = [m for m in messages if isinstance(m, SystemMessage)]
        non_system = [m for m in messages if not isinstance(m, SystemMessage)]

        # Clean message history
        cleaned = clean_message_history(non_system)

        # Keep recent N messages (safely preserving AI-Tool pairs)
        keep_recent = self.context_settings.keep_recent_messages
        recent_messages = truncate_messages_safely(cleaned, keep_recent=keep_recent)

        # Calculate indices
        recent_start_idx = len(cleaned) - len(recent_messages)

        if strategy == "compact":
            # For compact: keep middle messages for detailed summary
            middle_count = self.context_settings.compact_middle_messages
            middle_start_idx = max(0, recent_start_idx - middle_count)
            middle_messages = cleaned[middle_start_idx:recent_start_idx]
            old_messages = cleaned[:middle_start_idx]
        else:
            # For summarize: all non-recent messages are "old"
            middle_messages = []
            old_messages = cleaned[:recent_start_idx]

        return {
            "system": system_msgs,
            "old": old_messages,
            "middle": middle_messages,
            "recent": recent_messages,
        }

    async def compress_messages(
        self,
        messages: List[BaseMessage],
        strategy: Literal["compact", "summarize"],
        model_invoker,  # Callable that invokes LLM
    ) -> List[BaseMessage]:
        """Compress message history using specified strategy.

        Args:
            messages: Full conversation history
            strategy: "compact" (detailed) or "summarize" (extreme)
            model_invoker: Async function to invoke LLM (e.g., invoke_planner)

        Returns:
            Compressed message list
        """
        # Partition messages
        partitions = self.partition_messages(messages, strategy)

        system_msgs = partitions["system"]
        old_msgs = partitions["old"]
        middle_msgs = partitions["middle"]
        recent_msgs = partitions["recent"]

        # Build compressed history
        compressed_history: List[BaseMessage] = []

        # 1. Always keep system messages
        compressed_history.extend(system_msgs)

        # 2. Compress old messages if any
        if old_msgs:
            if strategy == "summarize":
                # Extreme compression
                summary_prompt = SystemMessage(content=SUMMARIZE_PROMPT)
                summary_response = await model_invoker(
                    messages=[summary_prompt] + old_msgs,
                    tools=[],
                )
                compressed_history.append(
                    HumanMessage(
                        content=f"[上下文摘要 - Summarize]\n{summary_response.content}"
                    )
                )
            else:
                # Detailed compression (same as compact for old messages)
                compact_prompt = SystemMessage(content=COMPACT_PROMPT)
                compact_response = await model_invoker(
                    messages=[compact_prompt] + old_msgs,
                    tools=[],
                )
                compressed_history.append(
                    HumanMessage(
                        content=f"[上下文压缩 - Compact Old]\n{compact_response.content}"
                    )
                )

        # 3. Compact middle messages if any (only in compact strategy)
        if middle_msgs and strategy == "compact":
            compact_prompt = SystemMessage(content=COMPACT_PROMPT)
            compact_response = await model_invoker(
                messages=[compact_prompt] + middle_msgs,
                tools=[],
            )
            compressed_history.append(
                HumanMessage(
                    content=f"[上下文压缩 - Compact Middle]\n{compact_response.content}"
                )
            )

        # 4. Keep recent messages uncompressed
        compressed_history.extend(recent_msgs)

        return compressed_history

    def estimate_compression_ratio(
        self,
        messages: List[BaseMessage],
        strategy: Literal["compact", "summarize"],
    ) -> dict:
        """Estimate compression effectiveness before actually compressing.

        Args:
            messages: Full conversation history
            strategy: Compression strategy

        Returns:
            Dictionary with compression statistics
        """
        partitions = self.partition_messages(messages, strategy)

        # Estimate character counts (rough proxy for tokens)
        def char_count(msgs: List[BaseMessage]) -> int:
            return sum(len(m.content) for m in msgs if hasattr(m, "content"))

        total_chars = char_count(messages)
        system_chars = char_count(partitions["system"])
        old_chars = char_count(partitions["old"])
        middle_chars = char_count(partitions["middle"])
        recent_chars = char_count(partitions["recent"])

        # Estimate compressed size
        # Compact: ~10-20% of original, Summarize: ~2-5%
        old_compressed = old_chars * (0.05 if strategy == "summarize" else 0.15)
        middle_compressed = middle_chars * 0.15 if strategy == "compact" else 0

        estimated_final = system_chars + old_compressed + middle_compressed + recent_chars

        return {
            "original_chars": total_chars,
            "estimated_final_chars": int(estimated_final),
            "compression_ratio": estimated_final / total_chars if total_chars > 0 else 1.0,
            "messages_before": len(messages),
            "messages_after_estimate": (
                len(partitions["system"])
                + (1 if old_chars > 0 else 0)  # Old summary message
                + (1 if middle_chars > 0 and strategy == "compact" else 0)  # Middle compact
                + len(partitions["recent"])
            ),
        }
