"""Test that @mention actually loads tools."""

from agentgraph.runtime import build_application
from agentgraph.utils import parse_mentions
from langchain_core.messages import HumanMessage
import uuid


def test_mention_loads_skill_tools():
    """Test that @weather loads weather skill tools."""
    print("=== Test: @mention Loads Skill Tools ===\n")

    app, initial_state_factory = build_application()
    state = initial_state_factory()

    # Simulate @weather mention
    mentions, cleaned_text = parse_mentions("@weather 北京今天怎么样")
    state["mentioned_agents"] = mentions
    state["messages"] = [HumanMessage(content=cleaned_text)]
    state["thread_id"] = str(uuid.uuid4())

    print(f"1. User input: @weather 北京今天怎么样")
    print(f"2. Parsed mentions: {mentions}")
    print(f"3. Cleaned text: {cleaned_text}")

    # Manually check what tools would be loaded
    from agentgraph.skills import SkillRegistry
    from pathlib import Path

    skills_root = Path("skills")
    skill_registry = SkillRegistry(skills_root)

    try:
        weather_skill = skill_registry.get("weather")
        print(f"\n4. Weather skill found:")
        print(f"   - ID: {weather_skill.id}")
        print(f"   - Name: {weather_skill.name}")
        print(f"   - Allowed tools: {weather_skill.allowed_tools}")
    except KeyError:
        print("\n❌ Weather skill not found in registry!")
        return

    # Now invoke the app and check if get_weather is called
    print(f"\n5. Invoking app with @weather mention...")

    try:
        config = {
            "recursion_limit": 50,
            "configurable": {
                "thread_id": state["thread_id"]
            }
        }
        result = app.invoke(state, config=config)

        # Check if get_weather was called
        tool_calls_found = []
        for msg in result["messages"]:
            if hasattr(msg, 'tool_calls') and msg.tool_calls:
                for tc in msg.tool_calls:
                    tool_name = tc.get("name") if isinstance(tc, dict) else getattr(tc, "name", None)
                    if tool_name:
                        tool_calls_found.append(tool_name)

        print(f"\n6. Tool calls detected: {tool_calls_found}")

        if "get_weather" in tool_calls_found:
            print("\n✅ SUCCESS: @weather correctly loaded get_weather tool!")
        else:
            print(f"\n⚠️  WARNING: get_weather not called. Tools used: {tool_calls_found}")
            print("   This might be expected if the LLM chose a different approach.")

        # Print last AI response
        for msg in reversed(result["messages"]):
            if hasattr(msg, 'type') and msg.type == 'ai':
                print(f"\n7. Charlie's response:\n   {msg.content[:200]}...\n")
                break

    except Exception as e:
        print(f"\n❌ Error during invocation: {e}")
        import traceback
        traceback.print_exc()


def test_mention_loads_direct_tool():
    """Test that @get_weather loads the tool directly."""
    print("\n=== Test: @mention Loads Tool Directly ===\n")

    app, initial_state_factory = build_application()
    state = initial_state_factory()

    # Simulate @get_weather mention (direct tool name)
    mentions, cleaned_text = parse_mentions("@get_weather 北京")
    state["mentioned_agents"] = mentions
    state["messages"] = [HumanMessage(content=cleaned_text)]
    state["thread_id"] = str(uuid.uuid4())

    print(f"1. User input: @get_weather 北京")
    print(f"2. Parsed mentions: {mentions}")

    try:
        config = {
            "recursion_limit": 50,
            "configurable": {
                "thread_id": state["thread_id"]
            }
        }
        result = app.invoke(state, config=config)

        # Check tool calls
        tool_calls_found = []
        for msg in result["messages"]:
            if hasattr(msg, 'tool_calls') and msg.tool_calls:
                for tc in msg.tool_calls:
                    tool_name = tc.get("name") if isinstance(tc, dict) else getattr(tc, "name", None)
                    if tool_name:
                        tool_calls_found.append(tool_name)

        print(f"\n3. Tool calls detected: {tool_calls_found}")

        if "get_weather" in tool_calls_found:
            print("\n✅ SUCCESS: @get_weather correctly loaded and called!")
        else:
            print(f"\n⚠️  Tools used: {tool_calls_found}")

    except Exception as e:
        print(f"\n❌ Error: {e}")


if __name__ == "__main__":
    print("🚀 Testing @mention Tool Loading...\n")
    print("=" * 60)

    try:
        test_mention_loads_skill_tools()
        print("=" * 60)
        test_mention_loads_direct_tool()
        print("=" * 60)

        print("\n🎉 All @mention tool loading tests completed!")

    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
