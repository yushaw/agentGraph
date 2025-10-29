#!/usr/bin/env python3
"""SimpleAgent Quick Start Example

演示 SimpleAgent 的基本用法
"""
import asyncio
import sys
from pathlib import Path

# 添加项目根目录到 sys.path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from simpleAgent import SimpleAgent


async def example_1_basic_usage():
    """示例 1: 基本用法"""
    print("\n" + "=" * 60)
    print("示例 1: 基本用法")
    print("=" * 60)

    agent = SimpleAgent()

    result = await agent.run(
        template="你是一位友好的 AI 助手。",
        user_message="你好，请介绍一下自己",
    )

    print(f"\n用户> 你好，请介绍一下自己")
    print(f"Agent> {result}\n")


async def example_2_with_template_params():
    """示例 2: 使用模板参数"""
    print("\n" + "=" * 60)
    print("示例 2: 使用模板参数定制角色")
    print("=" * 60)

    agent = SimpleAgent()

    result = await agent.run(
        template="你是一位专业的 {role}，擅长 {skill}。",
        params={"role": "数据分析师", "skill": "从数据中提取洞察"},
        user_message="请简单介绍你的专长",
    )

    print(f"\n用户> 请简单介绍你的专长")
    print(f"Agent> {result}\n")


async def example_3_with_jinja2():
    """示例 3: 使用 Jinja2 模板"""
    print("\n" + "=" * 60)
    print("示例 3: 使用 Jinja2 高级模板")
    print("=" * 60)

    agent = SimpleAgent()

    template = """你是一位 {{ role }}。

{% if urgent %}
⚠️  这是一个紧急任务！
{% endif %}

你的专业领域包括:
{% for skill in skills %}
- {{ skill }}
{% endfor %}
"""

    result = await agent.run(
        template=template,
        params={
            "role": "技术顾问",
            "urgent": True,
            "skills": ["系统架构", "性能优化", "安全评估"],
        },
        user_message="你能帮我做什么？",
        format="jinja2",
    )

    print(f"\n用户> 你能帮我做什么？")
    print(f"Agent> {result}\n")


async def example_4_with_tools():
    """示例 4: 指定可用工具"""
    print("\n" + "=" * 60)
    print("示例 4: 限制可用工具")
    print("=" * 60)

    agent = SimpleAgent()

    result = await agent.run(
        template="你是文件管理助手，可以帮助用户管理文件。",
        user_message="你有哪些能力？",
        tools=["read_file", "write_file", "list_workspace_files"],
    )

    print(f"\n用户> 你有哪些能力？")
    print(f"Agent> {result}\n")


async def example_5_with_template_file():
    """示例 5: 使用模板文件"""
    print("\n" + "=" * 60)
    print("示例 5: 使用预定义模板文件")
    print("=" * 60)

    agent = SimpleAgent(
        template_path="simpleAgent/config/prompt_templates/data_analyst.jinja2"
    )

    result = await agent.run(
        params={"task": "分析用户行为数据"},
        user_message="你好，我需要分析一些用户数据",
    )

    print(f"\n用户> 你好，我需要分析一些用户数据")
    print(f"Agent> {result}\n")


async def main():
    """运行所有示例"""
    print("\n🚀 SimpleAgent 快速入门示例")

    try:
        await example_1_basic_usage()
        await example_2_with_template_params()
        await example_3_with_jinja2()
        await example_4_with_tools()
        await example_5_with_template_file()

        print("\n" + "=" * 60)
        print("✅ 所有示例运行完成！")
        print("=" * 60 + "\n")

    except Exception as e:
        print(f"\n❌ 示例运行失败: {e}\n")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
