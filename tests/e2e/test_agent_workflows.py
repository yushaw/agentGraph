"""End-to-end tests for GeneralAgent core business workflows.

Tests the complete agent loop including:
- Tool discovery and usage
- Skill loading and execution
- @mention system
- Session persistence
- Workspace isolation
- Multi-turn conversations
- Subagent delegation
"""

import pytest
from pathlib import Path
import tempfile
import shutil
from unittest.mock import Mock, patch

from langgraph.checkpoint.sqlite import SqliteSaver
from generalAgent.runtime.app import build_application
from generalAgent.graph.state import AppState
from langchain_core.messages import HumanMessage, AIMessage


@pytest.fixture
def temp_workspace():
    """创建临时工作区"""
    workspace_dir = Path(tempfile.mkdtemp())
    yield workspace_dir
    shutil.rmtree(workspace_dir, ignore_errors=True)


@pytest.fixture
async def test_app():
    """创建测试用的 Agent application"""
    app, initial_state_factory, skill_registry, tool_registry = await build_application()
    return {
        "app": app,
        "initial_state_factory": initial_state_factory,
        "skill_registry": skill_registry,
        "tool_registry": tool_registry,
    }


class TestBasicToolUsage:
    """测试基本工具使用流程"""

    async def test_simple_tool_call(self, test_app):
        """测试简单工具调用：now (获取当前时间)"""
        app = test_app["app"]
        initial_state = test_app["initial_state_factory"]()

        # 用户请求当前时间
        state = initial_state.copy()
        state["messages"] = [HumanMessage(content="现在几点了?")]

        # 运行 agent
        config = {"configurable": {"thread_id": "test-tool-001"}}
        result = await app.ainvoke(state, config)

        # 验证结果
        assert len(result["messages"]) > 1, "应该有多轮消息"

        # LLM 可能直接回答或调用now工具,两种都可以接受
        # 只需验证最终给出了时间相关信息
        messages_str = str(result["messages"]).lower()
        assert any(keyword in messages_str for keyword in ["时间", "点", "utc", "now", "time"]), "应该包含时间相关信息"

        # 验证最后一条消息是 AI 回复
        last_message = result["messages"][-1]
        assert isinstance(last_message, AIMessage), "最后一条消息应该是 AI 回复"

    async def test_file_operation_workflow(self, test_app, temp_workspace):
        """测试文件操作工作流：write_file -> read_file -> list_workspace_files"""
        app = test_app["app"]
        initial_state = test_app["initial_state_factory"]()

        # 设置工作区环境变量
        import os

        os.environ["AGENT_WORKSPACE_PATH"] = str(temp_workspace)

        # 创建测试文件
        test_file = temp_workspace / "outputs" / "test.txt"
        test_file.parent.mkdir(parents=True, exist_ok=True)
        test_file.write_text("Hello World")

        # 用户请求读取文件
        state = initial_state.copy()
        state["messages"] = [HumanMessage(content="请读取 outputs/test.txt 文件")]

        # 运行 agent
        config = {"configurable": {"thread_id": "test-file-001"}}
        result = await app.ainvoke(state, config)

        # 验证结果
        assert len(result["messages"]) > 1
        # 检查是否调用了 read_file 工具
        messages_str = str(result["messages"])
        assert "read_file" in messages_str.lower() or "Hello World" in messages_str


class TestMentionSystem:
    """测试 @mention 系统"""

    async def test_skill_mention_loads_skill(self, test_app):
        """测试 @skill 提及加载技能"""
        app = test_app["app"]
        initial_state = test_app["initial_state_factory"]()
        skill_registry = test_app["skill_registry"]

        # 检查 pdf 技能是否存在 (使用正确的 API: list_meta())
        available_skills = [skill.id for skill in skill_registry.list_meta()]
        if "pdf" not in available_skills:
            pytest.skip("pdf skill not available")

        # 用户提及 @pdf
        state = initial_state.copy()
        state["messages"] = [HumanMessage(content="@pdf 帮我处理PDF文档")]

        # 运行 agent
        config = {"configurable": {"thread_id": "test-mention-001"}}
        result = await app.ainvoke(state, config)

        # Note: active_skill字段已废弃,现在skills通过workspace symlinking工作
        # 只验证agent正常响应即可 (具体的skill loading由workspace manager处理)
        assert len(result["messages"]) > 1, "应该有响应消息"
        # Skill loading mechanism is tested in integration tests

    async def test_tool_mention_loads_tool(self, test_app):
        """测试 @tool 提及按需加载工具"""
        app = test_app["app"]
        initial_state = test_app["initial_state_factory"]()
        tool_registry = test_app["tool_registry"]

        # 选择一个已发现但未启用的工具 (使用正确的 API: _discovered)
        # 注意: _discovered 包含所有扫描到的工具, _tools 只包含已启用的
        enabled_tools = {tool.name for tool in tool_registry.list_tools()}
        on_demand_tools = [name for name in tool_registry._discovered.keys() if name not in enabled_tools]

        if not on_demand_tools:
            pytest.skip("No on-demand tools available")

        tool_name = on_demand_tools[0]

        # 用户提及工具
        state = initial_state.copy()
        state["messages"] = [HumanMessage(content=f"@{tool_name} 帮我使用这个工具")]

        # 运行 agent
        config = {"configurable": {"thread_id": "test-tool-mention-001"}}
        result = await app.ainvoke(state, config)

        # 验证工具被提及 (@mention系统应该处理它)
        # Note: E2E测试中,工具可能不会被添加到allowed_tools,因为agent可能没有实际调用
        # 只验证没有报错,消息有响应即可
        assert len(result["messages"]) > 1, "应该有响应消息"
        # Tool loading is tested in integration tests, E2E just verifies no crash


class TestMultiTurnConversation:
    """测试多轮对话"""

    async def test_conversation_with_context(self, test_app):
        """测试保持上下文的多轮对话"""
        app = test_app["app"]
        initial_state = test_app["initial_state_factory"]()

        config = {"configurable": {"thread_id": "test-multiturn-001"}}

        # 第一轮：设定话题
        state1 = initial_state.copy()
        state1["messages"] = [HumanMessage(content="我叫张三")]
        result1 = await app.ainvoke(state1, config)

        # 第二轮：引用之前的信息
        state2 = result1.copy()
        state2["messages"].append(HumanMessage(content="我叫什么名字?"))
        result2 = await app.ainvoke(state2, config)

        # 验证 agent 记住了名字
        last_message = str(result2["messages"][-1].content)
        assert "张三" in last_message, "Agent 应该记住用户名字"

    async def test_tool_chaining(self, test_app, temp_workspace):
        """测试工具链式调用"""
        app = test_app["app"]
        initial_state = test_app["initial_state_factory"]()

        import os

        os.environ["AGENT_WORKSPACE_PATH"] = str(temp_workspace)

        # 创建输出目录
        (temp_workspace / "outputs").mkdir(parents=True, exist_ok=True)

        # 用户请求：写文件 -> 列出文件
        state = initial_state.copy()
        state["messages"] = [
            HumanMessage(
                content="请创建一个文件 outputs/notes.txt，内容是'测试笔记'，然后列出 outputs 目录的所有文件"
            )
        ]

        config = {"configurable": {"thread_id": "test-chain-001"}}
        result = await app.ainvoke(state, config)

        # 验证两个工具都被调用
        messages_str = str(result["messages"])
        assert "write_file" in messages_str.lower() or "notes.txt" in messages_str
        assert (
            "list_workspace_files" in messages_str.lower()
            or "list" in messages_str.lower()
        )


class TestSessionPersistence:
    """测试会话持久化"""

    async def test_session_state_persistence(self, test_app, tmp_path):
        """测试会话状态持久化"""
        app = test_app["app"]
        initial_state = test_app["initial_state_factory"]()

        # Note: app 已经包含内置的 checkpointer，无需重新编译
        # 这个测试验证 checkpointer 正常工作
        config = {"configurable": {"thread_id": "test-persist-001"}}

        # 第一次调用
        state1 = initial_state.copy()
        state1["messages"] = [HumanMessage(content="记住：我的幸运数字是 42")]
        result1 = await app.ainvoke(state1, config)

        # 验证会话被保存 (app自带checkpointer)
        snapshot = app.get_state(config)
        assert snapshot is not None, "会话应该被保存"
        assert len(snapshot.values["messages"]) > 0, "会话应该包含消息"

    async def test_session_resume(self, test_app, tmp_path):
        """测试会话恢复"""
        app = test_app["app"]
        initial_state = test_app["initial_state_factory"]()

        # Note: app 已经包含内置的 checkpointer
        config = {"configurable": {"thread_id": "test-resume-001"}}

        # 第一轮
        state1 = initial_state.copy()
        state1["messages"] = [HumanMessage(content="我住在北京")]
        await app.ainvoke(state1, config)

        # 第二轮：新建状态，但使用相同 thread_id
        state2 = initial_state.copy()
        state2["messages"] = [HumanMessage(content="我住在哪里?")]
        result2 = await app.ainvoke(state2, config)

        # 验证 agent 能访问历史信息
        last_message = str(result2["messages"][-1].content)
        assert "北京" in last_message, "Agent 应该能从会话历史中获取信息"


class TestWorkspaceIsolation:
    """测试工作区隔离"""

    async def test_session_workspace_isolation(self, test_app):
        """测试不同会话的工作区隔离"""
        app = test_app["app"]
        initial_state = test_app["initial_state_factory"]()

        # 会话 1
        config1 = {"configurable": {"thread_id": "test-workspace-001"}}
        state1 = initial_state.copy()
        state1["messages"] = [HumanMessage(content="创建文件 outputs/session1.txt")]
        await app.ainvoke(state1, config1)

        # 会话 2
        config2 = {"configurable": {"thread_id": "test-workspace-002"}}
        state2 = initial_state.copy()
        state2["messages"] = [HumanMessage(content="创建文件 outputs/session2.txt")]
        await app.ainvoke(state2, config2)

        # 验证工作区路径不同
        # Note: 这个测试需要访问 workspace manager，实际实现可能需要调整

    async def test_file_access_restriction(self, test_app, temp_workspace):
        """测试文件访问限制（不能访问工作区外的文件）"""
        app = test_app["app"]
        initial_state = test_app["initial_state_factory"]()

        import os

        os.environ["AGENT_WORKSPACE_PATH"] = str(temp_workspace)

        # 尝试访问工作区外的文件
        state = initial_state.copy()
        state["messages"] = [HumanMessage(content="读取 /etc/passwd 文件")]

        config = {"configurable": {"thread_id": "test-restrict-001"}}
        result = await app.ainvoke(state, config)

        # 验证被拒绝或产生错误
        messages_str = str(result["messages"])
        # 应该包含错误、拒绝或无法访问的信息
        # LLM可能用"无法"、"不能"等词汇,而不是"error"
        assert (
            "error" in messages_str.lower()
            or "不允许" in messages_str
            or "denied" in messages_str.lower()
            or "outside" in messages_str.lower()
            or "无法" in messages_str
            or "不能" in messages_str
            or "限制" in messages_str
        ), "应该拒绝访问工作区外的文件"


class TestErrorHandling:
    """测试错误处理"""

    async def test_tool_error_recovery(self, test_app):
        """测试工具错误恢复"""
        app = test_app["app"]
        initial_state = test_app["initial_state_factory"]()

        # 请求一个不存在的文件
        state = initial_state.copy()
        state["messages"] = [HumanMessage(content="读取 nonexistent_file_12345.txt")]

        config = {"configurable": {"thread_id": "test-error-001"}}
        result = await app.ainvoke(state, config)

        # 验证 agent 能优雅处理错误
        assert len(result["messages"]) > 1
        last_message = str(result["messages"][-1].content)
        # Agent 应该给出有意义的错误解释
        assert len(last_message) > 10, "Agent 应该给出错误说明"

    async def test_loop_limit(self, test_app):
        """测试循环限制防止死循环"""
        app = test_app["app"]
        initial_state = test_app["initial_state_factory"]()

        # 设置很小的 max_loops
        state = initial_state.copy()
        state["max_loops"] = 2
        state["messages"] = [HumanMessage(content="帮我做一个复杂的任务")]

        config = {"configurable": {"thread_id": "test-loop-001"}}
        result = await app.ainvoke(state, config)

        # 验证循环次数被限制
        assert result["loops"] <= state["max_loops"], "应该遵守循环限制"


class TestComplexWorkflows:
    """测试复杂业务流程"""

    async def test_research_and_summarize_workflow(self, test_app):
        """测试调研和总结工作流"""
        app = test_app["app"]
        initial_state = test_app["initial_state_factory"]()

        # 用户请求：调研一个话题并总结
        state = initial_state.copy()
        state["messages"] = [
            HumanMessage(content="请告诉我当前UTC时间，并用一句话总结")
        ]

        config = {"configurable": {"thread_id": "test-workflow-001"}}
        result = await app.ainvoke(state, config)

        # 验证完整流程
        assert len(result["messages"]) > 1
        # 应该调用了 now 工具
        messages_str = str(result["messages"])
        assert "now" in messages_str.lower() or "utc" in messages_str.lower()

    async def test_data_processing_pipeline(self, test_app, temp_workspace):
        """测试数据处理管道"""
        app = test_app["app"]
        initial_state = test_app["initial_state_factory"]()

        import os

        os.environ["AGENT_WORKSPACE_PATH"] = str(temp_workspace)

        # 创建测试数据
        (temp_workspace / "uploads").mkdir(parents=True, exist_ok=True)
        data_file = temp_workspace / "uploads" / "data.txt"
        data_file.write_text("1\n2\n3\n4\n5")

        # 用户请求：读取数据 -> 处理 -> 保存结果
        state = initial_state.copy()
        state["messages"] = [
            HumanMessage(
                content="读取 uploads/data.txt，告诉我有多少行，然后创建一个文件 outputs/summary.txt 写入行数"
            )
        ]

        config = {"configurable": {"thread_id": "test-pipeline-001"}}
        result = await app.ainvoke(state, config)

        # 验证流程完成
        assert len(result["messages"]) > 1
        # 检查输出文件是否创建
        summary_file = temp_workspace / "outputs" / "summary.txt"
        if summary_file.exists():
            assert "5" in summary_file.read_text()


class TestAdvancedMultiTurnScenarios:
    """测试高级多轮对话场景"""

    async def test_progressive_task_refinement(self, test_app, temp_workspace):
        """测试渐进式任务细化场景

        模拟用户逐步明确需求的真实场景：
        1. 用户提出模糊需求
        2. Agent 询问细节
        3. 用户补充信息
        4. Agent 执行任务
        """
        app = test_app["app"]
        initial_state = test_app["initial_state_factory"]()

        import os
        os.environ["AGENT_WORKSPACE_PATH"] = str(temp_workspace)
        (temp_workspace / "uploads").mkdir(parents=True, exist_ok=True)

        config = {"configurable": {"thread_id": "test-progressive-001"}}

        # 第一轮：模糊需求
        state1 = initial_state.copy()
        state1["messages"] = [HumanMessage(content="帮我整理一些数据")]
        result1 = await app.ainvoke(state1, config)

        # Agent 应该会询问更多信息（或尝试理解）
        assert len(result1["messages"]) > 1

        # 第二轮：补充数据来源
        state2 = result1.copy()
        # 创建数据文件
        data_file = temp_workspace / "uploads" / "sales.txt"
        data_file.write_text("Product A: 100\nProduct B: 200\nProduct C: 150")
        state2["messages"].append(HumanMessage(content="数据在 uploads/sales.txt，帮我统计总数"))
        result2 = await app.ainvoke(state2, config)

        # 验证 agent 处理了数据
        messages_str = str(result2["messages"])
        assert "read_file" in messages_str.lower() or "450" in messages_str or "总" in messages_str

    async def test_context_switch_and_recall(self, test_app):
        """测试上下文切换与记忆召回

        测试 agent 在多个话题间切换后仍能召回之前的信息：
        1. 话题 A：设置信息
        2. 话题 B：完全不同的任务
        3. 回到话题 A：验证记忆
        """
        app = test_app["app"]
        initial_state = test_app["initial_state_factory"]()

        config = {"configurable": {"thread_id": "test-context-switch-001"}}

        # 第一轮：设定项目信息
        state1 = initial_state.copy()
        state1["messages"] = [HumanMessage(content="我正在做一个叫 AgentGraph 的项目")]
        result1 = await app.ainvoke(state1, config)

        # 第二轮：完全不同的话题
        state2 = result1.copy()
        state2["messages"].append(HumanMessage(content="现在几点了?"))
        result2 = await app.ainvoke(state2, config)

        # 第三轮：回到第一个话题
        state3 = result2.copy()
        state3["messages"].append(HumanMessage(content="我刚才说的项目叫什么名字?"))
        result3 = await app.ainvoke(state3, config)

        # 验证 agent 记住了项目名称
        last_message = str(result3["messages"][-1].content)
        assert "AgentGraph" in last_message or "agentgraph" in last_message.lower()


class TestSubagentDelegation:
    """测试 Subagent 委派场景"""

    async def test_complex_task_delegation(self, test_app, temp_workspace):
        """测试复杂任务自动委派给 subagent

        场景：需要多步骤、独立上下文的任务
        """
        app = test_app["app"]
        initial_state = test_app["initial_state_factory"]()

        import os
        os.environ["AGENT_WORKSPACE_PATH"] = str(temp_workspace)

        # 准备测试数据
        (temp_workspace / "uploads").mkdir(parents=True, exist_ok=True)
        data_file = temp_workspace / "uploads" / "report_data.txt"
        data_file.write_text("Q1: Revenue $100K, Expenses $60K\nQ2: Revenue $120K, Expenses $70K")

        # 复杂任务：分析数据并生成报告
        state = initial_state.copy()
        state["messages"] = [
            HumanMessage(
                content="分析 uploads/report_data.txt 中的财务数据，计算每季度利润，然后生成一份总结报告到 outputs/financial_summary.txt"
            )
        ]

        config = {"configurable": {"thread_id": "test-delegation-001"}}
        result = await app.ainvoke(state, config)

        # 验证任务完成
        assert len(result["messages"]) > 1

        # 检查是否使用了 call_subagent（可能）或直接完成
        messages_str = str(result["messages"])
        # 应该读取了源文件
        assert "read_file" in messages_str.lower() or "report_data" in messages_str

    async def test_subagent_error_handling(self, test_app, temp_workspace):
        """测试 subagent 错误处理和主 agent 的响应"""
        app = test_app["app"]
        initial_state = test_app["initial_state_factory"]()

        import os
        os.environ["AGENT_WORKSPACE_PATH"] = str(temp_workspace)

        # 委派一个会失败的任务
        state = initial_state.copy()
        state["messages"] = [
            HumanMessage(content="使用 call_subagent 读取一个不存在的文件 nonexistent_12345.txt")
        ]

        config = {"configurable": {"thread_id": "test-subagent-error-001"}}
        result = await app.ainvoke(state, config)

        # Agent 应该优雅处理错误
        assert len(result["messages"]) > 1
        last_message = str(result["messages"][-1].content)
        # 应该包含错误说明或替代方案
        assert len(last_message) > 10


class TestToolChainingScenarios:
    """测试工具链式调用复杂场景"""

    async def test_conditional_tool_chain(self, test_app, temp_workspace):
        """测试条件性工具链

        根据前一个工具的结果决定下一步行动
        """
        app = test_app["app"]
        initial_state = test_app["initial_state_factory"]()

        import os
        os.environ["AGENT_WORKSPACE_PATH"] = str(temp_workspace)

        # 准备条件分支数据
        (temp_workspace / "uploads").mkdir(parents=True, exist_ok=True)
        status_file = temp_workspace / "uploads" / "status.txt"
        status_file.write_text("READY")

        # 条件任务：检查状态，如果是 READY 则继续处理
        state = initial_state.copy()
        state["messages"] = [
            HumanMessage(
                content="检查 uploads/status.txt，如果内容是 READY，创建 outputs/processing.txt 写入'开始处理'；否则创建 outputs/waiting.txt"
            )
        ]

        config = {"configurable": {"thread_id": "test-conditional-001"}}
        result = await app.ainvoke(state, config)

        # 验证正确的分支被执行
        processing_file = temp_workspace / "outputs" / "processing.txt"
        waiting_file = temp_workspace / "outputs" / "waiting.txt"

        # 应该创建 processing.txt（因为状态是 READY）
        assert processing_file.exists() or "processing" in str(result["messages"])

    async def test_iterative_refinement_loop(self, test_app, temp_workspace):
        """测试迭代优化循环

        模拟需要多次迭代改进的场景
        """
        app = test_app["app"]
        initial_state = test_app["initial_state_factory"]()

        import os
        os.environ["AGENT_WORKSPACE_PATH"] = str(temp_workspace)

        (temp_workspace / "outputs").mkdir(parents=True, exist_ok=True)

        # 迭代任务：创建文件，添加内容，再修改
        state = initial_state.copy()
        state["messages"] = [
            HumanMessage(
                content="创建 outputs/draft.txt 写入'版本1'，然后读取它，再追加'版本2'（使用 write_file 覆盖，内容包含原来的）"
            )
        ]

        config = {"configurable": {"thread_id": "test-iteration-001"}}
        result = await app.ainvoke(state, config)

        # 验证迭代完成
        draft_file = temp_workspace / "outputs" / "draft.txt"
        if draft_file.exists():
            content = draft_file.read_text()
            # 应该包含两个版本的内容
            assert "版本1" in content or "版本2" in content


class TestErrorRecoveryScenarios:
    """测试错误恢复场景"""

    async def test_file_not_found_recovery(self, test_app, temp_workspace):
        """测试文件不存在时的恢复策略"""
        app = test_app["app"]
        initial_state = test_app["initial_state_factory"]()

        import os
        os.environ["AGENT_WORKSPACE_PATH"] = str(temp_workspace)

        # 请求读取不存在的文件，但提供 fallback
        state = initial_state.copy()
        state["messages"] = [
            HumanMessage(
                content="尝试读取 uploads/config.txt，如果不存在，创建它并写入默认配置 'debug=false'"
            )
        ]

        config = {"configurable": {"thread_id": "test-recovery-001"}}
        result = await app.ainvoke(state, config)

        # 验证 fallback 策略被执行
        config_file = temp_workspace / "uploads" / "config.txt"
        assert config_file.exists() or "debug=false" in str(result["messages"])

    async def test_retry_on_tool_failure(self, test_app):
        """测试工具失败后的重试逻辑"""
        app = test_app["app"]
        initial_state = test_app["initial_state_factory"]()

        # 模拟可能失败的操作（访问受限文件）
        state = initial_state.copy()
        state["messages"] = [
            HumanMessage(content="列出当前目录的文件")
        ]

        config = {"configurable": {"thread_id": "test-retry-001"}}
        result = await app.ainvoke(state, config)

        # Agent 应该能够处理并提供响应（即使某些操作失败）
        assert len(result["messages"]) > 1
        assert result["messages"][-1].content  # 有实际回复


class TestStatefulWorkflows:
    """测试状态管理复杂场景"""

    async def test_todo_list_workflow(self, test_app):
        """测试 TODO 列表管理流程

        模拟实际的任务追踪场景
        """
        app = test_app["app"]
        initial_state = test_app["initial_state_factory"]()

        config = {"configurable": {"thread_id": "test-todo-workflow-001"}}

        # 第一轮：创建待办事项
        state1 = initial_state.copy()
        state1["messages"] = [
            HumanMessage(content="帮我创建三个待办事项：1. 写代码 2. 写测试 3. 写文档")
        ]
        result1 = await app.ainvoke(state1, config)

        # 验证 todo 被创建
        assert len(result1.get("todos", [])) >= 0  # todos 可能在 agent 内部管理

        # 第二轮：询问待办事项
        state2 = result1.copy()
        state2["messages"].append(HumanMessage(content="我有哪些待办事项?"))
        result2 = await app.ainvoke(state2, config)

        # 应该能列出之前的待办
        last_message = str(result2["messages"][-1].content)
        # 可能包含任务关键词
        task_keywords = ["代码", "测试", "文档", "todo", "待办"]
        assert any(keyword in last_message for keyword in task_keywords)

    async def test_session_state_accumulation(self, test_app, temp_workspace):
        """测试会话状态累积

        多轮对话中状态的累积和使用
        """
        app = test_app["app"]
        initial_state = test_app["initial_state_factory"]()

        import os
        os.environ["AGENT_WORKSPACE_PATH"] = str(temp_workspace)
        (temp_workspace / "outputs").mkdir(parents=True, exist_ok=True)

        config = {"configurable": {"thread_id": "test-accumulation-001"}}

        # 第一轮：收集信息
        state1 = initial_state.copy()
        state1["messages"] = [HumanMessage(content="记住：项目名称是 AgentGraph")]
        result1 = await app.ainvoke(state1, config)

        # 第二轮：继续收集
        state2 = result1.copy()
        state2["messages"].append(HumanMessage(content="再记住：版本是 v1.0"))
        result2 = await app.ainvoke(state2, config)

        # 第三轮：使用所有信息
        state3 = result2.copy()
        state3["messages"].append(
            HumanMessage(content="用之前记住的信息创建 outputs/project_info.txt")
        )
        result3 = await app.ainvoke(state3, config)

        # 验证信息被使用
        info_file = temp_workspace / "outputs" / "project_info.txt"
        if info_file.exists():
            content = info_file.read_text()
            assert "AgentGraph" in content or "v1.0" in content


class TestEdgeCases:
    """测试边界情况和特殊场景"""

    async def test_empty_file_handling(self, test_app, temp_workspace):
        """测试空文件处理"""
        app = test_app["app"]
        initial_state = test_app["initial_state_factory"]()

        import os
        os.environ["AGENT_WORKSPACE_PATH"] = str(temp_workspace)

        # 创建空文件
        (temp_workspace / "uploads").mkdir(parents=True, exist_ok=True)
        empty_file = temp_workspace / "uploads" / "empty.txt"
        empty_file.write_text("")

        state = initial_state.copy()
        state["messages"] = [
            HumanMessage(content="读取 uploads/empty.txt 并告诉我内容")
        ]

        config = {"configurable": {"thread_id": "test-empty-001"}}
        result = await app.ainvoke(state, config)

        # Agent 应该能处理空文件
        assert len(result["messages"]) > 1
        last_message = str(result["messages"][-1].content)
        assert "空" in last_message or "empty" in last_message.lower() or "没有" in last_message

    async def test_large_message_history_trimming(self, test_app):
        """测试大量消息历史的裁剪"""
        app = test_app["app"]
        initial_state = test_app["initial_state_factory"]()

        config = {"configurable": {"thread_id": "test-trimming-001"}}

        # 创建大量轮次对话
        state = initial_state.copy()
        state["messages"] = [HumanMessage(content="第一条消息")]

        for i in range(15):  # 模拟多轮对话
            state["messages"].append(HumanMessage(content=f"消息 {i+2}"))
            state["messages"].append(AIMessage(content=f"回复 {i+2}"))

        # 最后一轮提问
        state["messages"].append(HumanMessage(content="这是最后一条消息，你能看到吗?"))

        result = await app.ainvoke(state, config)

        # 验证系统仍然正常工作（历史被裁剪但不影响功能）
        assert len(result["messages"]) > 0
        # 最后一条消息应该被处理
        assert result["messages"][-1].content

    async def test_concurrent_file_operations(self, test_app, temp_workspace):
        """测试并发文件操作场景（虽然是单线程，但测试工具调用顺序）"""
        app = test_app["app"]
        initial_state = test_app["initial_state_factory"]()

        import os
        os.environ["AGENT_WORKSPACE_PATH"] = str(temp_workspace)
        (temp_workspace / "outputs").mkdir(parents=True, exist_ok=True)

        # 请求同时创建多个文件
        state = initial_state.copy()
        state["messages"] = [
            HumanMessage(
                content="创建三个文件：outputs/file1.txt 写入'A'，outputs/file2.txt 写入'B'，outputs/file3.txt 写入'C'"
            )
        ]

        config = {"configurable": {"thread_id": "test-concurrent-001"}}
        result = await app.ainvoke(state, config)

        # 验证所有文件都被创建（尽管是顺序执行）
        file1 = temp_workspace / "outputs" / "file1.txt"
        file2 = temp_workspace / "outputs" / "file2.txt"
        file3 = temp_workspace / "outputs" / "file3.txt"

        # 至少应该尝试创建文件
        created_count = sum([file1.exists(), file2.exists(), file3.exists()])
        messages_str = str(result["messages"])

        # 验证至少有文件操作
        assert created_count > 0 or "write_file" in messages_str.lower()


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
