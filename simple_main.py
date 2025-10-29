#!/usr/bin/env python3
"""SimpleAgent CLI Entrypoint

启动 SimpleAgent 的命令行接口

使用方式:
    # 交互式模式（默认）
    python simple_main.py

    # 使用自定义模板
    python simple_main.py --template "你是{role}。任务: {task}" \\
        --params '{"role": "分析师", "task": "分析数据"}'

    # 使用模板文件
    python simple_main.py --template-file simpleAgent/config/prompt_templates/data_analyst.jinja2 \\
        --params '{"task": "分析销售数据"}'

    # 指定可用工具
    python simple_main.py --tools read_file,write_file,ask_human

    # 单次运行（非交互）
    python simple_main.py --message "你好，请介绍一下自己" --no-interactive
"""
import argparse
import asyncio
import json
import logging
import sys
from pathlib import Path

# 添加项目根目录到 sys.path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from generalAgent.config.project_root import resolve_project_path
from shared.session.manager import SessionManager
from simpleAgent.simple_agent import SimpleAgent
from simpleAgent.cli import SimpleCLI

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.FileHandler("logs/simple_agent.log"),
        logging.StreamHandler(sys.stdout),
    ],
)
LOGGER = logging.getLogger(__name__)


def parse_args():
    """解析命令行参数"""
    parser = argparse.ArgumentParser(
        description="SimpleAgent - 轻量级垂直领域 Agent",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    # Prompt 模板
    parser.add_argument(
        "--template",
        type=str,
        help="Prompt 模板字符串（支持 {param} 占位符）",
    )
    parser.add_argument(
        "--template-file",
        type=str,
        help="Prompt 模板文件路径（Jinja2 格式）",
    )
    parser.add_argument(
        "--params",
        type=str,
        help="模板参数（JSON 格式字符串）",
    )

    # 工具配置
    parser.add_argument(
        "--tools",
        type=str,
        help="允许的工具列表（逗号分隔，例如: read_file,write_file）",
    )

    # 模型配置
    parser.add_argument(
        "--model-type",
        type=str,
        choices=["base", "reasoning", "vision", "code", "chat"],
        default="base",
        help="使用的模型类型（默认: base）",
    )

    # 运行控制
    parser.add_argument(
        "--max-iterations",
        type=int,
        default=15,
        help="最大迭代次数（默认: 15）",
    )

    # 交互模式
    parser.add_argument(
        "--interactive",
        action="store_true",
        default=True,
        help="交互式模式（默认）",
    )
    parser.add_argument(
        "--no-interactive",
        action="store_true",
        help="非交互模式（单次运行）",
    )
    parser.add_argument(
        "--message",
        type=str,
        help="用户消息（在非交互模式下使用）",
    )

    return parser.parse_args()


async def main():
    """主函数"""
    args = parse_args()

    # 解析参数
    template = args.template
    template_file = args.template_file
    params = json.loads(args.params) if args.params else {}
    tools = args.tools.split(",") if args.tools else None
    interactive = not args.no_interactive

    LOGGER.info("Starting SimpleAgent CLI")

    # 1. 创建 SimpleAgent
    agent = SimpleAgent(template_path=template_file)
    agent.settings.model_type = args.model_type
    agent.settings.max_iterations = args.max_iterations

    # 2. 非交互模式：单次运行
    if not interactive:
        if not args.message:
            print("❌ 非交互模式需要提供 --message 参数")
            sys.exit(1)

        print(f"\n用户> {args.message}\n")
        response = await agent.run(
            template=template,
            params=params,
            user_message=args.message,
            tools=tools,
        )
        print(f"Agent> {response}\n")
        return

    # 3. 交互模式：启动 CLI
    # 创建 SessionManager（SimpleAgent 无状态，但复用基础设施）
    session_manager = SessionManager(
        db_path=resolve_project_path("data/simple_sessions.db"),
        workspace_root=resolve_project_path("data/simple_workspace"),
        skills_root=resolve_project_path("skills"),  # SimpleAgent 暂不支持 skills
    )

    # 创建 CLI
    cli = SimpleCLI(
        session_manager=session_manager,
        agent=agent,
        template=template,
        params=params,
        tools=tools,
    )

    # 运行 CLI
    await cli.run()


if __name__ == "__main__":
    asyncio.run(main())
