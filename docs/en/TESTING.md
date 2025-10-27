# Testing Documentation

**Version**: 2.0
**Date**: 2025-10-27
**Status**: Consolidated from TESTING_GUIDE, E2E_TESTING_SOP, and HITL_TESTING_SOP

> **Note**: This document consolidates all testing documentation into a single comprehensive guide covering smoke, unit, integration, and E2E tests, with special focus on HITL (Human-in-the-Loop) testing.

---

## Table of Contents

1. [Part 1: Testing Overview](#part-1-testing-overview)
   - [1.1 Four-Tier Test Architecture](#11-four-tier-test-architecture)
   - [1.2 Test Organization](#12-test-organization)
   - [1.3 Running Tests](#13-running-tests)
   - [1.4 Test Coverage Requirements](#14-test-coverage-requirements)

2. [Part 2: Smoke Tests](#part-2-smoke-tests)
   - [2.1 Purpose and Scope](#21-purpose-and-scope)
   - [2.2 What to Test](#22-what-to-test)
   - [2.3 Examples](#23-examples)

3. [Part 3: Unit Tests](#part-3-unit-tests)
   - [3.1 Writing Unit Tests](#31-writing-unit-tests)
   - [3.2 Mocks and Fixtures](#32-mocks-and-fixtures)
   - [3.3 Module-Specific Tests](#33-module-specific-tests)
   - [3.4 HITL Unit Tests](#34-hitl-unit-tests)

4. [Part 4: Integration Tests](#part-4-integration-tests)
   - [4.1 @mention System Tests](#41-mention-system-tests)
   - [4.2 Tool Integration Tests](#42-tool-integration-tests)
   - [4.3 Skill Integration Tests](#43-skill-integration-tests)
   - [4.4 Examples](#44-examples)

5. [Part 5: E2E Tests](#part-5-e2e-tests)
   - [5.1 E2E Testing Philosophy](#51-e2e-testing-philosophy)
   - [5.2 Business Scenario Tests](#52-business-scenario-tests)
   - [5.3 Standard Operating Procedures](#53-standard-operating-procedures)
   - [5.4 Verification Checklists](#54-verification-checklists)
   - [5.5 Test Examples](#55-test-examples)

6. [Part 6: HITL Testing](#part-6-hitl-testing)
   - [6.1 HITL Testing Approach](#61-hitl-testing-approach)
   - [6.2 ask_human Tool Testing](#62-ask_human-tool-testing)
   - [6.3 Tool Approval Testing](#63-tool-approval-testing)
   - [6.4 Reflective Evaluation Framework](#64-reflective-evaluation-framework)
   - [6.5 Test Procedures](#65-test-procedures)

7. [Part 7: Test Development Guidelines](#part-7-test-development-guidelines)
   - [7.1 Writing Good Tests](#71-writing-good-tests)
   - [7.2 Test Naming Conventions](#72-test-naming-conventions)
   - [7.3 Assertion Best Practices](#73-assertion-best-practices)
   - [7.4 Common Patterns](#74-common-patterns)

8. [Part 8: CI/CD and Performance](#part-8-cicd-and-performance)
   - [8.1 CI/CD Integration](#81-cicd-integration)
   - [8.2 Performance Benchmarks](#82-performance-benchmarks)
   - [8.3 Troubleshooting](#83-troubleshooting)

---

## Part 1: Testing Overview

### 1.1 Four-Tier Test Architecture

AgentGraph uses a four-tier testing strategy to ensure code quality at different levels:

```
Level 1: Smoke Tests (< 30s)
         ↓ Quick validation before commits
Level 2: Unit Tests (< 2min)
         ↓ Module-level functionality
Level 3: Integration Tests (< 5min)
         ↓ Module interaction verification
Level 4: E2E Tests (< 10min)
         ↓ Complete business workflows
```

**Testing Goals**:
1. **Safety**: Correctly intercept all dangerous operations
2. **Accuracy**: Minimize false positives and false negatives
3. **Usability**: Don't impact normal workflows
4. **Performance**: Testing overhead should be negligible

### 1.2 Test Organization

```
tests/
├── run_tests.py                    # Unified test entry point ⭐
│
├── smoke/                          # Smoke tests (< 30s)
│   └── test_smoke.py              # Fast critical-path validation
│
├── unit/                          # Unit tests (module-level)
│   ├── test_hitl_approval.py      # HITL approval rules
│   ├── test_hitl_unit.py          # HITL scenario tests
│   ├── test_hitl_reflective.py    # HITL reflective tests
│   ├── test_hitl_evaluation.py    # HITL evaluation tests
│   ├── hitl_evaluation_framework.py
│   ├── test_mcp/                   # MCP connection and integration
│   ├── test_file_ops.py           # File operations
│   ├── test_document_extractors.py # Document extraction (PDF/DOCX/XLSX/PPTX)
│   ├── test_text_indexer.py       # Text indexing and search
│   ├── test_find_search_tools.py  # File finding and content search tools
│   ├── test_tool_scanner.py       # Tool scanning
│   ├── test_tool_config.py        # Tool configuration
│   ├── test_workspace_manager.py  # Workspace management
│   └── ...
│
├── integration/                   # Integration tests (module interaction)
│   ├── test_mention_types.py      # @Mention system
│   ├── test_registry_on_demand.py # On-demand loading
│   ├── test_delegated agent_simple.py    # Delegated agent system
│   └── test_real_scenarios.py     # Real-world scenarios
│
└── e2e/                           # End-to-end tests (business workflows)
    ├── test_agent_workflows.py    # Core business flows
    └── reports/                    # Test report outputs
```

### 1.3 Running Tests

#### Unified Test Entry Point

```bash
# View help
python tests/run_tests.py

# Run smoke tests (fastest)
python tests/run_tests.py smoke

# Run unit tests
python tests/run_tests.py unit

# Run integration tests
python tests/run_tests.py integration

# Run E2E tests
python tests/run_tests.py e2e

# Run all tests
python tests/run_tests.py all

# Run tests with coverage report
python tests/run_tests.py coverage
```

#### Direct pytest Usage

```bash
# Run specific test file
pytest tests/unit/test_hitl_approval.py -v

# Run specific test class
pytest tests/unit/test_hitl_approval.py::TestGlobalRiskPatterns -v

# Run specific test method
pytest tests/unit/test_hitl_approval.py::TestGlobalRiskPatterns::test_critical_password_detection -v

# Run with detailed output
pytest tests/e2e/ -v -s

# Run with coverage
pytest tests/ --cov=generalAgent --cov-report=html
```

### 1.4 Test Coverage Requirements

| Test Type | Target Time | Test Count | Pass Rate | Coverage |
|-----------|-------------|------------|-----------|----------|
| **Smoke** | < 30s | ~10 | 100% | N/A |
| **Unit** | < 2min | ~50 | 100% | >= 80% |
| **Integration** | < 5min | ~20 | >= 95% | >= 70% |
| **E2E** | < 10min | ~15 | >= 90% | >= 60% |

---

## Part 2: Smoke Tests

### 2.1 Purpose and Scope

**Purpose**: Fast validation of system basic functionality to catch obvious breakage before commits.

**Characteristics**:
- ⚡ Fast execution (< 30 seconds)
- 🎯 Critical path only
- ✅ Must pass before commit

**When to Run**: Before every commit

### 2.2 What to Test

Smoke tests cover:
- Configuration loading (`.env`, `settings.py`)
- Model registry initialization
- Tool system basic functionality
- Skill system basic functionality
- Application build process
- Project structure integrity

### 2.3 Examples

```python
# tests/smoke/test_smoke.py

class TestBasicSetup:
    """Basic setup and configuration tests"""

    def test_settings_load(self):
        """Test that settings load from .env"""
        settings = get_settings()
        assert settings is not None
        assert settings.models is not None

    def test_model_registry_initialization(self):
        """Test that model registry initializes correctly"""
        registry = get_model_registry()
        assert registry is not None
        assert registry.base is not None

    def test_tool_system_loads(self):
        """Test that tool system initializes"""
        tool_registry = ToolRegistry()
        tools = tool_registry.get_enabled_tools()
        assert len(tools) > 0

    def test_application_builds(self):
        """Test that application builds without errors"""
        app, initial_state_factory, skill_registry, tool_registry = build_application()
        assert app is not None
        assert initial_state_factory is not None
```

**Running Smoke Tests**:

```bash
# Using unified entry point (recommended)
python tests/run_tests.py smoke

# Direct pytest
pytest tests/smoke/ -v

# Expected output:
# ================================================================================
# 🔥 Running Smoke Tests (Quick Validation)
# ================================================================================
# Purpose: Fast critical-path tests to catch obvious breakage
# Expected time: < 30 seconds
#
# tests/smoke/test_smoke.py::TestBasicSetup::test_settings_load PASSED
# tests/smoke/test_smoke.py::TestBasicSetup::test_model_registry_initialization PASSED
# ...
# ==================== 8 passed in 5.23s ====================
```

---

## Part 3: Unit Tests

### 3.1 Writing Unit Tests

**Purpose**: Test individual modules to ensure each component works correctly in isolation.

**Characteristics**:
- 🔬 Fine-grained testing
- 🚀 Fast execution
- 🎯 Specific functionality focus

**When to Run**: After modifying specific modules

### 3.2 Mocks and Fixtures

#### Using Fixtures

```python
import pytest
from generalAgent.runtime.app import build_application

@pytest.fixture
def test_app():
    """Create test Agent application"""
    app, initial_state_factory, skill_registry, tool_registry = build_application()
    return {
        "app": app,
        "initial_state_factory": initial_state_factory,
        "skill_registry": skill_registry,
        "tool_registry": tool_registry
    }

@pytest.fixture
def temp_workspace(tmp_path):
    """Create temporary workspace for tests"""
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (workspace / "uploads").mkdir()
    (workspace / "outputs").mkdir()
    (workspace / "temp").mkdir()
    return workspace

def test_simple_invoke(test_app):
    """Test using fixture"""
    app = test_app["app"]
    initial_state = test_app["initial_state_factory"]()
    # ... test code
```

#### Conditional Test Skipping

```python
@pytest.mark.skipif(
    not get_settings().models.reason_api_key,
    reason="Requires reason model API key"
)
def test_reflective_analysis(self):
    """Reflective analysis test"""
    pass
```

### 3.3 Module-Specific Tests

#### Document Processing Module

**File Operations** (`test_file_ops.py`):
```python
class TestFileOperations:
    """Test file reading, writing, and listing"""

    def test_read_file_text(self, temp_workspace):
        """Test reading text files"""
        test_file = temp_workspace / "test.txt"
        test_file.write_text("Hello World")

        result = read_file(str(test_file))
        assert "Hello World" in result

    def test_write_file(self, temp_workspace):
        """Test writing files"""
        output_path = temp_workspace / "outputs" / "result.txt"
        write_file(str(output_path), "Test content")

        assert output_path.exists()
        assert "Test content" in output_path.read_text()
```

**Document Extraction** (`test_document_extractors.py`):
```python
class TestDocumentExtractors:
    """Test document content extraction"""

    def test_pdf_extraction(self):
        """Test PDF content extraction"""
        content = extract_pdf_content("test.pdf", max_chars=10000)
        assert content is not None
        assert len(content) > 0

    def test_docx_extraction(self):
        """Test DOCX content extraction"""
        content = extract_docx_content("test.docx")
        assert content is not None

    def test_xlsx_extraction(self):
        """Test Excel content extraction"""
        content = extract_xlsx_content("test.xlsx")
        assert content is not None

    def test_pptx_extraction(self):
        """Test PowerPoint content extraction"""
        content = extract_pptx_content("test.pptx")
        assert content is not None
```

**Text Indexing** (`test_text_indexer.py`):
```python
class TestTextIndexer:
    """Test text indexing and search"""

    def test_md5_calculation(self):
        """Test MD5 hash calculation"""
        hash1 = calculate_md5("test.pdf")
        hash2 = calculate_md5("test.pdf")
        assert hash1 == hash2

    def test_index_creation(self):
        """Test index creation and storage"""
        create_index("test.pdf", chunks)
        index_path = get_index_path("test.pdf")
        assert index_path.exists()

    def test_multi_strategy_search(self):
        """Test multi-strategy search and scoring"""
        results = search_in_index("test.pdf", "Q3 revenue")
        assert len(results) > 0
        assert results[0]["score"] > 0

    def test_orphan_cleanup(self):
        """Test orphan index cleanup"""
        # Create index for file
        create_index("old.pdf", chunks)
        # Replace file with different content
        create_index("old.pdf", new_chunks)
        # Old index should be cleaned
        cleanup_old_indexes()
```

**File Search Tools** (`test_find_search_tools.py`):
```python
class TestFindSearchTools:
    """Test file finding and content search tools"""

    def test_find_files_glob(self, temp_workspace):
        """Test find_files with glob patterns"""
        # Create test files
        (temp_workspace / "uploads" / "report.pdf").touch()
        (temp_workspace / "uploads" / "data.xlsx").touch()

        # Test glob pattern
        results = find_files("*.pdf", path="uploads")
        assert "report.pdf" in results

    def test_read_file_large_document(self):
        """Test read_file with large documents"""
        result = read_file("large_report.pdf")
        assert "Preview" in result
        assert "search_file" in result  # Should suggest search

    def test_search_file_text(self, temp_workspace):
        """Test search_file in text files"""
        log_file = temp_workspace / "error.log"
        log_file.write_text("ERROR: Connection failed\nINFO: Retrying\nERROR: Timeout")

        results = search_file(str(log_file), "ERROR", max_results=10)
        assert len(results) >= 2

    def test_search_file_document(self):
        """Test search_file in documents"""
        results = search_file("report.pdf", "Q3 revenue")
        assert len(results) > 0
        assert "Q3 revenue" in results[0]["text"]

    def test_path_safety(self, temp_workspace):
        """Test path safety validation"""
        with pytest.raises(ValueError):
            read_file("../../etc/passwd")
```

#### Workspace Management

**Workspace Manager** (`test_workspace_manager.py`):
```python
class TestWorkspaceManager:
    """Test workspace isolation and management"""

    def test_session_workspace_creation(self):
        """Test creating isolated workspace for session"""
        workspace = WorkspaceManager.create_workspace("session-001")
        assert (workspace / "uploads").exists()
        assert (workspace / "outputs").exists()
        assert (workspace / "temp").exists()

    def test_skill_symlink(self):
        """Test symlinking skills to workspace"""
        workspace = WorkspaceManager.create_workspace("session-002")
        WorkspaceManager.link_skill(workspace, "pdf")
        assert (workspace / "skills" / "pdf" / "SKILL.md").exists()

    def test_workspace_isolation(self):
        """Test workspace isolation between sessions"""
        ws1 = WorkspaceManager.create_workspace("session-001")
        ws2 = WorkspaceManager.create_workspace("session-002")

        (ws1 / "uploads" / "file1.txt").write_text("content1")
        (ws2 / "uploads" / "file2.txt").write_text("content2")

        assert not (ws2 / "uploads" / "file1.txt").exists()
        assert not (ws1 / "uploads" / "file2.txt").exists()
```

### 3.4 HITL Unit Tests

#### Approval Rules Tests (`test_hitl_approval.py`)

```python
class TestGlobalRiskPatterns:
    """Test global risk pattern detection"""

    def test_critical_password_detection(self):
        """Test password detection in various formats"""
        checker = ApprovalChecker()

        # URL format
        decision = checker.check(
            tool_name="http_fetch",
            arguments={"url": "https://user:password123@api.example.com"}
        )
        assert decision.needs_approval is True
        assert decision.risk_level == "critical"

        # Key-value format
        decision = checker.check(
            tool_name="run_bash_command",
            arguments={"command": "mysql -p password='secret123'"}
        )
        assert decision.needs_approval is True
        assert decision.risk_level == "critical"

    def test_api_key_detection(self):
        """Test API key detection"""
        checker = ApprovalChecker()
        decision = checker.check(
            tool_name="http_fetch",
            arguments={"headers": {"Authorization": "Bearer sk-abc123"}}
        )
        assert decision.needs_approval is True
        assert decision.risk_level == "critical"

    def test_secret_token_detection(self):
        """Test secret/token detection"""
        checker = ApprovalChecker()
        decision = checker.check(
            tool_name="run_bash_command",
            arguments={"command": "export SECRET_TOKEN='xyz789'"}
        )
        assert decision.needs_approval is True
        assert decision.risk_level == "critical"


class TestPriorityLevels:
    """Test four-layer priority system"""

    def test_custom_checker_priority(self):
        """Test that custom checkers have highest priority"""
        # Custom checker should override config rules
        pass

    def test_global_pattern_priority(self):
        """Test global patterns take precedence over tool rules"""
        pass

    def test_tool_specific_rules(self):
        """Test tool-specific rules from hitl_rules.yaml"""
        checker = ApprovalChecker()
        decision = checker.check(
            tool_name="run_bash_command",
            arguments={"command": "rm -rf /tmp/test"}
        )
        assert decision.needs_approval is True
        assert decision.risk_level == "high"


class TestCrossToolDetection:
    """Test cross-tool risk detection"""

    def test_password_in_http_fetch(self):
        """Test password detection in http_fetch tool"""
        checker = ApprovalChecker()
        decision = checker.check(
            tool_name="http_fetch",
            arguments={"url": "https://user:pass@example.com"}
        )
        assert decision.needs_approval is True

    def test_password_in_bash_command(self):
        """Test password detection in bash command"""
        checker = ApprovalChecker()
        decision = checker.check(
            tool_name="run_bash_command",
            arguments={"command": "curl -u user:pass https://example.com"}
        )
        assert decision.needs_approval is True

    def test_system_file_in_multiple_tools(self):
        """Test system file detection across tools"""
        checker = ApprovalChecker()

        # In read_file
        decision = checker.check(
            tool_name="read_file",
            arguments={"path": "/etc/passwd"}
        )
        assert decision.needs_approval is True

        # In run_bash_command
        decision = checker.check(
            tool_name="run_bash_command",
            arguments={"command": "cat /etc/passwd"}
        )
        assert decision.needs_approval is True
```

**Running Unit Tests**:

```bash
# Using unified entry point
python tests/run_tests.py unit

# Run specific module
pytest tests/unit/test_hitl_approval.py -v

# Run specific test class
pytest tests/unit/test_hitl_approval.py::TestGlobalRiskPatterns -v

# Run with coverage
pytest tests/unit/ --cov=generalAgent --cov-report=html
```

---

## Part 4: Integration Tests

### 4.1 @mention System Tests

**Purpose**: Test the @mention system's ability to dynamically load resources.

**File**: `tests/integration/test_mention_types.py`

```python
class TestMentionSystem:
    """Test @mention classification and loading"""

    def test_tool_mention_loading(self, test_app):
        """Test @tool mention loads tool on demand"""
        tool_registry = test_app["tool_registry"]

        # Tool not loaded initially
        assert "http_fetch" not in tool_registry.get_enabled_tools()

        # Mention @http_fetch
        tool_registry.load_on_demand("http_fetch")

        # Tool should now be loaded
        assert "http_fetch" in tool_registry.get_enabled_tools()

    def test_skill_mention_loading(self, test_app):
        """Test @skill mention generates reminder"""
        skill_registry = test_app["skill_registry"]

        # Load pdf skill
        reminder = skill_registry.get_skill_reminder("pdf")

        assert "SKILL.md" in reminder
        assert "pdf" in reminder

    def test_agent_mention_loading(self, test_app):
        """Test @agent mention loads delegated agent tool"""
        tool_registry = test_app["tool_registry"]

        # Mention @research
        tool_registry.load_on_demand("delegate_task")

        assert "delegate_task" in tool_registry.get_enabled_tools()
```

### 4.2 Tool Integration Tests

**File**: `tests/integration/test_registry_on_demand.py`

```python
class TestToolOnDemandLoading:
    """Test tool on-demand loading system"""

    def test_load_single_tool(self):
        """Test loading a single tool on demand"""
        registry = ToolRegistry()
        initial_count = len(registry.get_enabled_tools())

        registry.load_on_demand("http_fetch")

        assert len(registry.get_enabled_tools()) == initial_count + 1

    def test_load_multiple_tools(self):
        """Test loading multiple tools"""
        registry = ToolRegistry()

        registry.load_on_demand("http_fetch")
        registry.load_on_demand("extract_links")

        enabled = registry.get_enabled_tools()
        assert "http_fetch" in enabled
        assert "extract_links" in enabled

    def test_tool_already_loaded(self):
        """Test loading already-loaded tool (should be idempotent)"""
        registry = ToolRegistry()

        registry.load_on_demand("http_fetch")
        count_after_first = len(registry.get_enabled_tools())

        registry.load_on_demand("http_fetch")
        count_after_second = len(registry.get_enabled_tools())

        assert count_after_first == count_after_second
```

### 4.3 Skill Integration Tests

**File**: `tests/integration/test_skills_integration.py`

```python
class TestSkillsIntegration:
    """Test skills catalog filtering and loading"""

    def test_enabled_skills_only_in_catalog(self):
        """Test that only enabled skills appear in catalog"""
        skill_config = load_skill_config()
        catalog = build_skills_catalog(skill_config)

        # Only enabled skills should be in catalog
        for skill_id, skill_info in skill_config.get("optional", {}).items():
            if skill_info.get("enabled", False):
                assert skill_id in catalog
            else:
                assert skill_id not in catalog

    def test_auto_load_on_file_upload(self):
        """Test auto-loading skill when matching file uploaded"""
        skill_config = load_skill_config()

        # Upload PDF file
        uploaded_files = [{"name": "report.pdf", "type": "pdf"}]

        # Should trigger pdf skill loading if configured
        auto_load_skills = get_auto_load_skills(uploaded_files, skill_config)

        pdf_skill = skill_config.get("optional", {}).get("pdf", {})
        if "pdf" in pdf_skill.get("auto_load_on_file_types", []):
            assert "pdf" in auto_load_skills

    def test_dynamic_file_upload_hints(self):
        """Test dynamic hint generation based on file type"""
        skill_config = load_skill_config()

        # Upload DOCX file
        uploaded_files = [{"name": "document.docx", "path": "/path/to/document.docx"}]

        reminder = build_file_upload_reminder(uploaded_files, skill_config)

        # Should include hint if docx skill configured
        docx_skill = skill_config.get("optional", {}).get("docx", {})
        if "docx" in docx_skill.get("auto_load_on_file_types", []):
            assert "@docx" in reminder
```

### 4.4 Examples

#### Delegated agent Integration Test

**File**: `tests/integration/test_delegated agent_simple.py`

```python
class TestDelegated agentSystem:
    """Test delegated agent context isolation and communication"""

    def test_delegated agent_context_isolation(self, test_app):
        """Test that delegated agent has isolated context"""
        app = test_app["app"]
        initial_state = test_app["initial_state_factory"]()

        # Set up parent context
        state = initial_state.copy()
        state["messages"] = [HumanMessage(content="Call delegated agent for research")]
        state["context_id"] = "parent-001"

        # Invoke with delegate_task
        config = {"configurable": {"thread_id": "test-delegated agent-001"}}
        result = app.invoke(state, config)

        # Check that delegated agent had different context_id
        assert "context_id" in result
        # Delegated agent should return to parent context

    def test_delegated agent_message_passing(self, test_app):
        """Test message passing to/from delegated agent"""
        app = test_app["app"]
        initial_state = test_app["initial_state_factory"]()

        state = initial_state.copy()
        state["messages"] = [
            HumanMessage(content="@research Please research Python 3.12 features")
        ]

        config = {"configurable": {"thread_id": "test-delegated agent-002"}}
        result = app.invoke(state, config)

        # Delegated agent should have processed request and returned result
        messages_str = str(result["messages"])
        assert "research" in messages_str.lower()
```

**Running Integration Tests**:

```bash
# Using unified entry point
python tests/run_tests.py integration

# Run specific integration test
pytest tests/integration/test_mention_types.py -v

# Run all integration tests with output
pytest tests/integration/ -v -s
```

---

## Part 5: E2E Tests

### 5.1 E2E Testing Philosophy

**Purpose**: Test complete business workflows from the user's perspective.

**Characteristics**:
- 🚀 Complete workflow testing
- 👤 User perspective
- 🎯 Business value verification

**When to Run**: Before releases, after major feature changes

### 5.2 Business Scenario Tests

#### Core Business Workflows

**File**: `tests/e2e/test_agent_workflows.py`

##### 1. Basic Tool Usage Flow
```python
class TestBasicToolUsage:
    """Test basic tool usage workflows"""

    def test_now_tool(self, test_app):
        """Test getting current time

        Scenario:
        User: "What time is it?"

        Expected flow:
        1. Agent calls now tool
        2. Returns current UTC time
        """
        app = test_app["app"]
        initial_state = test_app["initial_state_factory"]()

        state = initial_state.copy()
        state["messages"] = [HumanMessage(content="What time is it?")]

        config = {"configurable": {"thread_id": "test-now-001"}}
        result = app.invoke(state, config)

        # Verify tool was called
        messages_str = str(result["messages"])
        assert "now" in messages_str

        # Verify time was returned
        last_message = result["messages"][-1]
        assert isinstance(last_message, AIMessage)

    def test_file_operations(self, test_app, temp_workspace):
        """Test file read/write operations

        Scenario:
        User: "Write 'Hello World' to test.txt"

        Expected flow:
        1. Agent calls write_file
        2. File is created in outputs/
        3. Agent confirms success
        """
        app = test_app["app"]
        initial_state = test_app["initial_state_factory"]()

        state = initial_state.copy()
        state["messages"] = [
            HumanMessage(content="Write 'Hello World' to outputs/test.txt")
        ]

        config = {"configurable": {"thread_id": "test-file-001"}}
        result = app.invoke(state, config)

        # Verify write_file was called
        messages_str = str(result["messages"])
        assert "write_file" in messages_str

        # Verify file was created
        output_file = temp_workspace / "outputs" / "test.txt"
        assert output_file.exists()
        assert "Hello World" in output_file.read_text()
```

##### 2. @Mention System
```python
class TestMentionWorkflows:
    """Test @mention system workflows"""

    def test_skill_mention_workflow(self, test_app, temp_workspace):
        """Test @skill mention and usage

        Scenario:
        User: "@pdf help me fill this form"

        Expected flow:
        1. Detect @pdf mention
        2. Load pdf skill
        3. Read SKILL.md
        4. Follow instructions
        5. Execute script
        """
        app = test_app["app"]
        initial_state = test_app["initial_state_factory"]()

        # Create test PDF
        test_pdf = temp_workspace / "uploads" / "form.pdf"
        test_pdf.touch()

        state = initial_state.copy()
        state["messages"] = [
            HumanMessage(content="@pdf help me fill this form")
        ]
        state["mentioned_agents"] = ["pdf"]

        config = {"configurable": {"thread_id": "test-skill-001"}}
        result = app.invoke(state, config)

        # Verify skill was loaded
        messages_str = str(result["messages"])
        assert "pdf" in messages_str.lower()

    def test_tool_mention_workflow(self, test_app):
        """Test @tool mention and usage

        Scenario:
        User: "@http_fetch get content from example.com"

        Expected flow:
        1. Detect @http_fetch mention
        2. Load tool on demand
        3. Call tool with URL
        4. Return content
        """
        app = test_app["app"]
        initial_state = test_app["initial_state_factory"]()

        state = initial_state.copy()
        state["messages"] = [
            HumanMessage(content="@http_fetch get content from https://example.com")
        ]
        state["mentioned_agents"] = ["http_fetch"]

        config = {"configurable": {"thread_id": "test-tool-001"}}
        result = app.invoke(state, config)

        # Verify tool was loaded and called
        messages_str = str(result["messages"])
        assert "http_fetch" in messages_str
```

##### 3. Multi-Turn Conversations
```python
class TestMultiTurnConversations:
    """Test multi-turn conversation with context retention"""

    def test_context_memory(self, test_app):
        """Test context retention across turns

        Scenario:
        Turn 1: User: "My name is Alice"
        Turn 2: User: "What's my name?"

        Expected:
        Agent should remember "Alice" from turn 1
        """
        app = test_app["app"]
        initial_state = test_app["initial_state_factory"]()
        config = {"configurable": {"thread_id": "test-memory-001"}}

        # Turn 1
        state = initial_state.copy()
        state["messages"] = [HumanMessage(content="My name is Alice")]
        result = app.invoke(state, config)

        # Turn 2
        state = result.copy()
        state["messages"].append(HumanMessage(content="What's my name?"))
        result = app.invoke(state, config)

        # Verify agent remembers name
        last_message = result["messages"][-1]
        assert "Alice" in last_message.content

    def test_tool_chaining(self, test_app, temp_workspace):
        """Test chaining multiple tool calls

        Scenario:
        User: "Read data.txt, process it, and save to result.txt"

        Expected flow:
        1. read_file("data.txt")
        2. Process data
        3. write_file("result.txt")
        """
        app = test_app["app"]
        initial_state = test_app["initial_state_factory"]()

        # Create input file
        input_file = temp_workspace / "uploads" / "data.txt"
        input_file.write_text("raw data")

        state = initial_state.copy()
        state["messages"] = [
            HumanMessage(content="Read uploads/data.txt, convert to uppercase, save to outputs/result.txt")
        ]

        config = {"configurable": {"thread_id": "test-chain-001"}}
        result = app.invoke(state, config)

        # Verify both tools were called
        messages_str = str(result["messages"])
        assert "read_file" in messages_str
        assert "write_file" in messages_str

        # Verify result
        output_file = temp_workspace / "outputs" / "result.txt"
        assert output_file.exists()
        assert "RAW DATA" in output_file.read_text()
```

##### 4. Session Persistence
```python
class TestSessionPersistence:
    """Test session save and restore"""

    def test_session_save_and_restore(self, test_app):
        """Test saving session state and restoring it

        Scenario:
        1. User has conversation
        2. Session is saved
        3. System restarts
        4. Session is restored
        5. Context is preserved
        """
        app = test_app["app"]
        initial_state = test_app["initial_state_factory"]()
        thread_id = "test-persist-001"
        config = {"configurable": {"thread_id": thread_id}}

        # Initial conversation
        state = initial_state.copy()
        state["messages"] = [HumanMessage(content="Remember: my favorite color is blue")]
        result = app.invoke(state, config)

        # Simulate session save (checkpoint system handles this)

        # New conversation in same session
        state = initial_state.copy()
        state["messages"] = [HumanMessage(content="What's my favorite color?")]
        result = app.invoke(state, config)

        # Should remember from previous conversation
        last_message = result["messages"][-1]
        assert "blue" in last_message.content.lower()
```

##### 5. Workspace Isolation
```python
class TestWorkspaceIsolation:
    """Test workspace isolation between sessions"""

    def test_session_file_isolation(self):
        """Test that sessions cannot access each other's files

        Scenario:
        1. Session A creates file
        2. Session B tries to access it
        3. Access should be denied
        """
        # Create workspace for session A
        ws_a = WorkspaceManager.create_workspace("session-A")
        file_a = ws_a / "uploads" / "secret.txt"
        file_a.write_text("Session A data")

        # Create workspace for session B
        ws_b = WorkspaceManager.create_workspace("session-B")

        # Session B should not see Session A's file
        assert not (ws_b / "uploads" / "secret.txt").exists()

    def test_path_safety_validation(self, test_app):
        """Test that path traversal is prevented

        Scenario:
        User: "Read ../../etc/passwd"

        Expected:
        Tool should reject with security error
        """
        app = test_app["app"]
        initial_state = test_app["initial_state_factory"]()

        state = initial_state.copy()
        state["messages"] = [
            HumanMessage(content="Read file ../../etc/passwd")
        ]

        config = {"configurable": {"thread_id": "test-security-001"}}
        result = app.invoke(state, config)

        # Should contain error about path safety
        messages_str = str(result["messages"])
        assert "security" in messages_str.lower() or "denied" in messages_str.lower()
```

##### 6. Error Handling
```python
class TestErrorHandling:
    """Test error handling and recovery"""

    def test_tool_failure_recovery(self, test_app):
        """Test graceful handling of tool failures

        Scenario:
        User: "Read nonexistent.txt"

        Expected:
        1. Tool fails with FileNotFoundError
        2. Agent receives error message
        3. Agent responds with helpful message
        """
        app = test_app["app"]
        initial_state = test_app["initial_state_factory"]()

        state = initial_state.copy()
        state["messages"] = [
            HumanMessage(content="Read uploads/nonexistent.txt")
        ]

        config = {"configurable": {"thread_id": "test-error-001"}}
        result = app.invoke(state, config)

        # Agent should handle error gracefully
        last_message = result["messages"][-1]
        assert "not found" in last_message.content.lower() or "does not exist" in last_message.content.lower()

    def test_loop_limit_prevention(self, test_app):
        """Test that infinite loops are prevented

        Scenario:
        Agent gets stuck in loop

        Expected:
        System stops after max_loops threshold
        """
        app = test_app["app"]
        initial_state = test_app["initial_state_factory"]()

        state = initial_state.copy()
        state["messages"] = [HumanMessage(content="Test loop limit")]
        state["loops"] = 0
        state["max_loops"] = 5

        config = {"configurable": {"thread_id": "test-loop-001"}}
        result = app.invoke(state, config)

        # Should not exceed max_loops
        assert result.get("loops", 0) <= state["max_loops"]
```

##### 7. Complex Workflows
```python
class TestComplexWorkflows:
    """Test complex multi-step workflows"""

    def test_research_and_summarize(self, test_app, temp_workspace):
        """Test research and summarization workflow

        Scenario:
        User: "Research Python 3.12 features and write a summary"

        Expected flow:
        1. @web_search for Python 3.12
        2. http_fetch to get details
        3. Analyze and summarize
        4. write_file to save report
        """
        app = test_app["app"]
        initial_state = test_app["initial_state_factory"]()

        state = initial_state.copy()
        state["messages"] = [
            HumanMessage(content="Research Python 3.12 features and write summary to outputs/python312.md")
        ]

        config = {"configurable": {"thread_id": "test-research-001"}}
        result = app.invoke(state, config)

        # Verify workflow completed
        messages_str = str(result["messages"])
        assert "write_file" in messages_str

        # Verify output file exists
        output_file = temp_workspace / "outputs" / "python312.md"
        assert output_file.exists()

    def test_document_processing_pipeline(self, test_app, temp_workspace):
        """Test document processing pipeline

        Scenario:
        User: "Process all PDFs in uploads/ and extract key information"

        Expected flow:
        1. find_files("*.pdf")
        2. For each PDF:
           - read_file (get preview)
           - search_file (find key info)
        3. Compile results
        4. write_file (save report)
        """
        app = test_app["app"]
        initial_state = test_app["initial_state_factory"]()

        # Create test PDFs
        (temp_workspace / "uploads" / "doc1.pdf").touch()
        (temp_workspace / "uploads" / "doc2.pdf").touch()

        state = initial_state.copy()
        state["messages"] = [
            HumanMessage(content="Find all PDFs in uploads/ and list them")
        ]

        config = {"configurable": {"thread_id": "test-pipeline-001"}}
        result = app.invoke(state, config)

        # Verify find_files was called
        messages_str = str(result["messages"])
        assert "find_files" in messages_str or "doc1.pdf" in messages_str
```

### 5.3 Standard Operating Procedures

#### Running E2E Tests

```bash
# Run all E2E tests
python tests/run_tests.py e2e

# Or directly with pytest
pytest tests/e2e/ -v -s

# Run specific workflow
pytest tests/e2e/test_agent_workflows.py -v

# Run specific test class
pytest tests/e2e/test_agent_workflows.py::TestBasicToolUsage -v

# Run with detailed output
pytest tests/e2e/test_agent_workflows.py::TestBasicToolUsage::test_now_tool -v -s
```

### 5.4 Verification Checklists

#### Flow Completion Checklist

For each E2E test, verify:

- [ ] User input is correctly parsed
- [ ] Expected tools are called
- [ ] Tool arguments are correct
- [ ] Tool execution succeeds
- [ ] Results are returned to agent
- [ ] Agent provides appropriate response
- [ ] Output files are created (if applicable)
- [ ] No unexpected errors occur

#### Context Retention Checklist

For multi-turn tests, verify:

- [ ] Previous messages are preserved
- [ ] Agent remembers user information
- [ ] Tool results are accessible in subsequent turns
- [ ] Session state is consistent

#### Error Recovery Checklist

For error handling tests, verify:

- [ ] Error is caught gracefully
- [ ] Error message is user-friendly
- [ ] System continues to function
- [ ] No data corruption
- [ ] Logs contain error details

### 5.5 Test Examples

#### Real-World Scenario Tests

**File**: `tests/e2e/test_real_world_scenarios.py`

```python
class TestDocumentProcessingScenario:
    """Real-world scenario: PDF form filling"""

    def test_pdf_form_filling_workflow(self, test_app, temp_workspace):
        """Test complete PDF form filling workflow

        User scenario:
        User: "@pdf help me fill this form"

        Complete flow:
        1. Detect @pdf mention
        2. Load pdf skill (+ dependencies)
        3. Read SKILL.md for instructions
        4. Use read_file to inspect PDF
        5. Use run_bash_command to execute fill script
        6. Output filled PDF to outputs/
        """
        app = test_app["app"]
        initial_state = test_app["initial_state_factory"]()

        # Create test PDF form
        test_form = temp_workspace / "uploads" / "application_form.pdf"
        test_form.touch()

        state = initial_state.copy()
        state["messages"] = [
            HumanMessage(content="@pdf fill the form at uploads/application_form.pdf with name='Alice' and save to outputs/")
        ]
        state["mentioned_agents"] = ["pdf"]

        config = {"configurable": {"thread_id": "test-pdf-scenario-001"}}
        result = app.invoke(state, config)

        # Verify workflow
        messages_str = str(result["messages"])

        # Should read SKILL.md
        assert "read_file" in messages_str

        # Should execute script
        assert "run_bash_command" in messages_str

        # Should create output file
        output_files = list((temp_workspace / "outputs").glob("*.pdf"))
        assert len(output_files) > 0


class TestCodeAnalysisScenario:
    """Real-world scenario: Code analysis"""

    def test_code_complexity_analysis(self, test_app, temp_workspace):
        """Test code analysis workflow

        User scenario:
        User: "Analyze main.py complexity and write report"

        Complete flow:
        1. read_file("main.py")
        2. Analyze code structure
        3. Calculate metrics
        4. write_file("analysis_report.md")
        """
        app = test_app["app"]
        initial_state = test_app["initial_state_factory"]()

        # Create test code file
        test_code = temp_workspace / "uploads" / "main.py"
        test_code.write_text("""
def hello():
    print("Hello")

def world():
    print("World")
""")

        state = initial_state.copy()
        state["messages"] = [
            HumanMessage(content="Analyze uploads/main.py complexity and write report to outputs/analysis.md")
        ]

        config = {"configurable": {"thread_id": "test-analysis-001"}}
        result = app.invoke(state, config)

        # Verify workflow
        messages_str = str(result["messages"])
        assert "read_file" in messages_str
        assert "write_file" in messages_str

        # Verify report was created
        report = temp_workspace / "outputs" / "analysis.md"
        assert report.exists()


class TestCollaborativeTaskScenario:
    """Real-world scenario: Collaborative task with ask_human"""

    def test_document_collaboration(self, test_app, temp_workspace):
        """Test collaborative document creation

        User scenario:
        User: "Help me write technical documentation"

        Complete flow:
        1. Agent uses ask_human to gather requirements
        2. Generate outline
        3. write_file draft
        4. ask_human for feedback
        5. Revise and finalize
        """
        app = test_app["app"]
        initial_state = test_app["initial_state_factory"]()

        state = initial_state.copy()
        state["messages"] = [
            HumanMessage(content="Help me write technical documentation for the authentication module")
        ]

        config = {"configurable": {"thread_id": "test-collab-001"}}

        # This test requires interrupt handling
        # In real usage, CLI would handle interrupts
        # For testing, we simulate the workflow

        result = app.invoke(state, config)

        # Should have asked for input or created draft
        messages_str = str(result["messages"])
        assert ("ask_human" in messages_str) or ("write_file" in messages_str)
```

**Running Real-World Scenario Tests**:

```bash
# Run all scenarios
pytest tests/e2e/test_real_world_scenarios.py -v -s

# Run specific scenario
pytest tests/e2e/test_real_world_scenarios.py::TestDocumentProcessingScenario -v -s
```

---

## Part 6: HITL Testing

### 6.1 HITL Testing Approach

HITL (Human-in-the-Loop) testing uses a four-layer strategy:

```
Layer 1: Unit Tests
         ↓ Test individual approval rules
Layer 2: E2E Scenario Tests
         ↓ Test real usage scenarios
Layer 3: Reflective Tests
         ↓ Use reasoning model to analyze decisions
Layer 4: Evaluation Tests
         ↓ Quantify system performance metrics
```

**Testing Goals**:
1. **Safety**: Correctly intercept all dangerous operations
2. **Accuracy**: Minimize false positives and false negatives
3. **Usability**: Don't impact normal workflows
4. **Performance**: Approval checks should be fast

### 6.2 ask_human Tool Testing

**Purpose**: Test agent's ability to request information from users.

```python
class TestAskHumanTool:
    """Test ask_human tool functionality"""

    def test_simple_question(self, test_app):
        """Test asking simple question

        Scenario:
        Agent needs to know user's city to search hotels
        """
        app = test_app["app"]
        initial_state = test_app["initial_state_factory"]()

        state = initial_state.copy()
        state["messages"] = [
            HumanMessage(content="Help me book a hotel")
        ]

        config = {"configurable": {"thread_id": "test-ask-001"}}

        # First invoke - agent should ask for city
        result = app.invoke(state, config)

        # Check for interrupt
        state_snapshot = app.get_state(config)
        if state_snapshot.next:
            # Should have interrupt for user_input_request
            assert "user_input_request" in str(state_snapshot.tasks)

    def test_question_with_default(self, test_app):
        """Test question with default value"""
        # Test that default values are properly handled
        pass

    def test_required_vs_optional(self, test_app):
        """Test required vs optional questions"""
        # Test that required questions block, optional don't
        pass
```

### 6.3 Tool Approval Testing

#### Four-Layer Approval Rules

**Priority 1 - Tool Custom Checkers** (highest priority):
```python
def check_bash_command(args: dict) -> ApprovalDecision:
    """Custom checker for bash commands"""
    command = args.get("command", "")
    if re.search(r"rm\s+-rf", command):
        return ApprovalDecision(
            needs_approval=True,
            reason="Deletion command may affect system files",
            risk_level="high"
        )
```

**Priority 2 - Global Risk Patterns** (cross-tool):
```yaml
# generalAgent/config/hitl_rules.yaml
global:
  risk_patterns:
    critical:
      patterns:
        - "password\\s*[=:]\\s*['\"]?\\w+"
        - "api[_-]?key\\s*[=:]\\s*"
        - "secret\\s*[=:]\\s*"
      action: require_approval
      reason: "Detected sensitive information (password/key/token)"
```

**Priority 3 - Tool-Specific Config Rules**:
```yaml
tools:
  run_bash_command:
    enabled: true
    patterns:
      high_risk:
        - "rm\\s+-rf"
        - "sudo"
      medium_risk:
        - "curl"
        - "wget"
    actions:
      high_risk: require_approval
      medium_risk: require_approval
```

**Priority 4 - Built-in Default Rules** (fallback):
```python
SAFE_COMMANDS = ["ls", "pwd", "cat", "grep", ...]
```

#### E2E Approval Tests

**File**: `tests/e2e/test_hitl_e2e.py`

```python
class TestE2EPasswordLeakScenarios:
    """Test password leak detection across scenarios"""

    def test_url_password_in_http_fetch(self):
        """Test: Password in URL format

        Scenario:
        User: "@http_fetch get https://user:pass123@api.example.com/data"

        Expected:
        System detects password, requires approval
        """
        checker = ApprovalChecker()
        decision = checker.check(
            tool_name="http_fetch",
            arguments={"url": "https://user:pass123@api.example.com/data"}
        )

        assert decision.needs_approval is True
        assert decision.risk_level == "critical"
        assert "password" in decision.reason.lower()

    def test_password_in_bash_command(self):
        """Test: Password in bash command

        Scenario:
        User: "@run_bash_command curl -u user:pass123 https://api.example.com"

        Expected:
        Global pattern detects password, requires approval
        """
        checker = ApprovalChecker()
        decision = checker.check(
            tool_name="run_bash_command",
            arguments={"command": "curl -u user:pass123 https://api.example.com"}
        )

        assert decision.needs_approval is True
        assert decision.risk_level == "critical"

    def test_env_var_password(self):
        """Test: Password in environment variable

        Scenario:
        User: "export PASSWORD='secret123'"

        Expected:
        Global pattern detects, requires approval
        """
        checker = ApprovalChecker()
        decision = checker.check(
            tool_name="run_bash_command",
            arguments={"command": "export PASSWORD='secret123'"}
        )

        assert decision.needs_approval is True
        assert decision.risk_level == "critical"


class TestE2ESystemFileScenarios:
    """Test system file access detection"""

    def test_etc_passwd_access(self):
        """Test: /etc/passwd access

        Scenario:
        User: "Read /etc/passwd"

        Expected:
        System file pattern triggers approval
        """
        checker = ApprovalChecker()
        decision = checker.check(
            tool_name="read_file",
            arguments={"path": "/etc/passwd"}
        )

        assert decision.needs_approval is True
        assert decision.risk_level in ["high", "critical"]

    def test_etc_shadow_access(self):
        """Test: /etc/shadow access"""
        checker = ApprovalChecker()
        decision = checker.check(
            tool_name="run_bash_command",
            arguments={"command": "cat /etc/shadow"}
        )

        assert decision.needs_approval is True


class TestE2EDangerousOperations:
    """Test dangerous operation detection"""

    def test_rm_rf_command(self):
        """Test: rm -rf detection

        Scenario:
        User: "Clean up with rm -rf /tmp/old"

        Expected:
        Tool-specific rule triggers approval
        """
        checker = ApprovalChecker()
        decision = checker.check(
            tool_name="run_bash_command",
            arguments={"command": "rm -rf /tmp/old"}
        )

        assert decision.needs_approval is True
        assert decision.risk_level == "high"

    def test_sudo_command(self):
        """Test: sudo command detection"""
        checker = ApprovalChecker()
        decision = checker.check(
            tool_name="run_bash_command",
            arguments={"command": "sudo apt-get install package"}
        )

        assert decision.needs_approval is True

    def test_sql_drop_table(self):
        """Test: SQL DROP TABLE detection

        Scenario:
        User: "Execute: DROP TABLE users"

        Expected:
        Global pattern detects dangerous SQL
        """
        checker = ApprovalChecker()
        decision = checker.check(
            tool_name="run_bash_command",
            arguments={"command": "mysql -e 'DROP TABLE users'"}
        )

        assert decision.needs_approval is True
        assert decision.risk_level in ["high", "critical"]


class TestE2ECrossToolDetection:
    """Test that global patterns work across all tools"""

    def test_password_across_multiple_tools(self):
        """Test password detection in different tools"""
        checker = ApprovalChecker()

        # In http_fetch
        decision1 = checker.check(
            tool_name="http_fetch",
            arguments={"url": "https://user:pass@example.com"}
        )
        assert decision1.needs_approval is True

        # In run_bash_command
        decision2 = checker.check(
            tool_name="run_bash_command",
            arguments={"command": "curl https://user:pass@example.com"}
        )
        assert decision2.needs_approval is True

        # Both should detect the same risk
        assert decision1.risk_level == decision2.risk_level


class TestE2EPriorityInteraction:
    """Test priority system interaction"""

    def test_custom_checker_overrides_config(self):
        """Test that custom checker takes priority over config rules"""
        # Custom checker should be evaluated first
        pass

    def test_global_pattern_overrides_tool_rule(self):
        """Test that global patterns override tool-specific rules"""
        # Global critical pattern should take priority
        pass

    def test_safe_operation_no_approval(self):
        """Test that safe operations don't trigger approval

        Scenario:
        User: "List files with ls -la"

        Expected:
        No approval needed (safe command)
        """
        checker = ApprovalChecker()
        decision = checker.check(
            tool_name="run_bash_command",
            arguments={"command": "ls -la"}
        )

        assert decision.needs_approval is False
```

**Running HITL E2E Tests**:

```bash
# Run all HITL E2E tests
pytest tests/e2e/test_hitl_e2e.py -v

# Run specific scenario
pytest tests/e2e/test_hitl_e2e.py::TestE2EPasswordLeakScenarios -v

# Run with detailed output
pytest tests/e2e/test_hitl_e2e.py::TestE2EPasswordLeakScenarios::test_url_password_in_http_fetch -v -s
```

### 6.4 Reflective Evaluation Framework

**Purpose**: Use reasoning model to analyze decision quality and suggest improvements.

**File**: `tests/unit/test_hitl_reflective.py`

#### Reflective Test Process

```mermaid
graph TD
    A[Run test case] --> B[ApprovalChecker makes decision]
    B --> C[Reason model analyzes decision]
    C --> D{Decision reasonable?}
    D -->|Yes| E[Record correct decision]
    D -->|No| F[Record error type]
    F --> G[Generate improvement suggestions]
    G --> H[Generate boundary cases]
    H --> I[Output analysis report]
```

#### Reflective Test Examples

```python
@pytest.mark.skipif(
    not get_settings().models.reason_api_key,
    reason="Requires reason model API key"
)
class TestReflectivePasswordDetection:
    """Reflective test: Password detection quality"""

    def test_reflective_url_password_analysis(self):
        """Test reasoning model's analysis of URL password detection

        Process:
        1. ApprovalChecker evaluates case
        2. Reason model analyzes the decision
        3. Provides feedback and suggestions
        """
        checker = ApprovalChecker()

        # Test case
        tool_name = "run_bash_command"
        arguments = {"command": "curl https://user:pass123@api.example.com/data"}

        # Get decision
        decision = checker.check(tool_name, arguments)

        # Ask reason model to analyze
        analysis_prompt = f"""
Analyze this HITL approval decision:

Tool: {tool_name}
Arguments: {arguments}
Decision: needs_approval={decision.needs_approval}, risk={decision.risk_level}
Reason: {decision.reason}

Questions:
1. Is this decision reasonable? Why or why not?
2. Are there any edge cases this rule might miss?
3. Could this rule cause false positives? If so, what cases?
4. Suggestions for improving the rule?
5. Generate 3-5 boundary test cases to validate the rule.

Provide analysis in JSON format:
{{
    "reasonable": true/false,
    "reasoning": "explanation",
    "edge_cases": ["case1", "case2", ...],
    "false_positive_risk": "explanation",
    "suggestions": ["suggestion1", "suggestion2", ...],
    "boundary_cases": [
        {{"description": "...", "input": "...", "expected": "..."}},
        ...
    ]
}}
"""

        # Call reason model
        reason_model = get_model_registry().reason
        response = reason_model.invoke(analysis_prompt)

        # Parse and validate response
        analysis = json.loads(response.content)

        print("\n" + "="*80)
        print(f"Tool: {tool_name}")
        print(f"Arguments: {arguments}")
        print(f"Decision: needs_approval={decision.needs_approval}, risk={decision.risk_level}")
        print(f"\nAnalysis: {analysis['reasoning']}")
        print(f"Suggestions: {analysis['suggestions']}")
        print(f"Boundary Cases: {len(analysis['boundary_cases'])}")
        print("="*80)

        # Assertions
        assert "reasonable" in analysis
        assert "reasoning" in analysis
        assert len(analysis["suggestions"]) > 0
        assert len(analysis["boundary_cases"]) >= 3


@pytest.mark.skipif(
    not get_settings().models.reason_api_key,
    reason="Requires reason model API key"
)
class TestReflectiveSystemFileDetection:
    """Reflective test: System file access detection quality"""

    def test_reflective_etc_passwd_analysis(self):
        """Analyze /etc/passwd detection quality"""
        checker = ApprovalChecker()

        tool_name = "read_file"
        arguments = {"path": "/etc/passwd"}

        decision = checker.check(tool_name, arguments)

        # Similar analysis process as above
        # ...

        assert decision.needs_approval is True


@pytest.mark.skipif(
    not get_settings().models.reason_api_key,
    reason="Requires reason model API key"
)
class TestReflectiveFalsePositiveAnalysis:
    """Reflective test: Analyze potential false positives"""

    def test_reflective_safe_password_word_usage(self):
        """Analyze: Does the word 'password' in comments trigger false positive?

        Example:
        command = "# Set password in config file"

        Should this trigger approval?
        """
        checker = ApprovalChecker()

        tool_name = "run_bash_command"
        arguments = {"command": "# Remember to set password in config file"}

        decision = checker.check(tool_name, arguments)

        # Get reason model's opinion
        analysis_prompt = f"""
Analyze this potential false positive:

Tool: {tool_name}
Arguments: {arguments}
Decision: needs_approval={decision.needs_approval}

Is this a false positive? The word "password" appears but no actual password is present.
Should the rule be adjusted to avoid this?
"""

        reason_model = get_model_registry().reason
        response = reason_model.invoke(analysis_prompt)

        print("\n" + "="*80)
        print(f"Potential False Positive Analysis:")
        print(f"Command: {arguments['command']}")
        print(f"Decision: {decision.needs_approval}")
        print(f"Analysis: {response.content}")
        print("="*80)
```

**Running Reflective Tests**:

```bash
# Ensure reason model is configured
grep MODEL_REASON .env

# Run reflective tests
pytest tests/unit/test_hitl_reflective.py -v -s

# Run specific reflective test
pytest tests/unit/test_hitl_reflective.py::TestReflectivePasswordDetection -v -s
```

**Expected Output**:

```
================================================================================
Tool: run_bash_command
Arguments: {'command': 'curl https://user:pass123@api.example.com/data'}
Decision: needs_approval=True, risk=critical

Analysis: The decision is reasonable. The URL contains a plaintext password
(user:pass123) which should trigger approval. This prevents credential leakage.

Suggestions: ['Consider distinguishing between real passwords and example passwords',
'Add detection for common placeholder patterns like "password", "pass", "secret"',
'Consider context (comments vs actual usage)']

Boundary Cases: 5
================================================================================
```

### 6.5 Test Procedures

#### HITL Unit Test SOP

**File**: `tests/unit/test_hitl_approval.py`

```bash
# 1. Run all unit tests
pytest tests/unit/test_hitl_approval.py -v

# 2. Run specific test class
pytest tests/unit/test_hitl_approval.py::TestGlobalRiskPatterns -v

# 3. Check coverage
pytest tests/unit/test_hitl_approval.py --cov=generalAgent.hitl --cov-report=html

# Acceptance criteria:
# ✅ All tests pass (13/13)
# ✅ No skipped tests
# ✅ Code coverage >= 90%
```

**If tests fail**:
1. Check `hitl_rules.yaml` regex patterns
2. Verify four-layer priority logic
3. Update test cases if requirements changed

#### HITL E2E Test SOP

```bash
# 1. Run all E2E HITL tests
pytest tests/e2e/test_hitl_e2e.py -v

# 2. Run by scenario
pytest tests/e2e/test_hitl_e2e.py::TestE2EPasswordLeakScenarios -v
pytest tests/e2e/test_hitl_e2e.py::TestE2ESystemFileScenarios -v
pytest tests/e2e/test_hitl_e2e.py::TestE2EDangerousOperations -v

# 3. Detailed output
pytest tests/e2e/test_hitl_e2e.py -v -s

# Acceptance criteria:
# ✅ All scenario tests pass
# ✅ Password leak scenarios: 100% detection
# ✅ System file access: 100% detection
# ✅ SQL dangerous operations: 100% detection
# ✅ Safe operations: 0% false positive rate
```

**If tests fail**:
1. Identify which scenario failed
2. Check corresponding risk patterns
3. Analyze boundary cases
4. Update rules or tests

#### HITL Reflective Test SOP

```bash
# 1. Confirm model configuration
grep MODEL_REASON .env

# 2. Run reflective tests
pytest tests/unit/test_hitl_reflective.py -v -s

# 3. View detailed analysis
pytest tests/unit/test_hitl_reflective.py::TestReflectivePasswordDetection -v -s

# Acceptance criteria:
# ✅ Reason model successfully called
# ✅ At least 90% of decisions judged reasonable
# ✅ All false positives have improvement suggestions
# ✅ At least 5 boundary cases generated
```

**If tests fail**:
1. Model call failure → Check API key and network
2. Unexpected analysis → Check JSON format
3. Unreasonable decision → Record and review

#### HITL Evaluation Test SOP

**File**: `tests/unit/test_hitl_evaluation.py` and `tests/unit/hitl_evaluation_framework.py`

```bash
# 1. Run standard evaluation
pytest tests/unit/test_hitl_evaluation.py::TestStandardEvaluationCases::test_run_standard_evaluation -v -s

# 2. Generate evaluation report
python tests/unit/hitl_evaluation_framework.py

# 3. View reports
cat tests/e2e/reports/evaluation_report.md
cat tests/e2e/reports/evaluation_results.json
```

**Evaluation Metrics**:

| Metric | Description | Target | Formula |
|--------|-------------|--------|---------|
| **Accuracy** | Correct decisions | >= 85% | (TP + TN) / Total |
| **Precision** | Approval correctness | >= 90% | TP / (TP + FP) |
| **Recall** | Risk detection rate | >= 80% | TP / (TP + FN) |
| **F1 Score** | Harmonic mean | >= 85% | 2 * (P * R) / (P + R) |
| **False Positive** | False alarms | <= 10% | FP / Total |
| **False Negative** | Missed risks | <= 5% | FN / Total |

**Standard Evaluation Cases**:

```python
# tests/unit/hitl_evaluation_framework.py

STANDARD_EVALUATION_CASES = [
    # Password leak cases
    EvaluationCase(
        case_id="pwd_001",
        category="password_leak",
        tool_name="http_fetch",
        arguments={"url": "https://user:pass123@api.example.com"},
        expected_approval=True,
        expected_risk="critical",
        description="Password in URL"
    ),
    EvaluationCase(
        case_id="pwd_002",
        category="password_leak",
        tool_name="run_bash_command",
        arguments={"command": "export PASSWORD='secret123'"},
        expected_approval=True,
        expected_risk="critical",
        description="Password in env var"
    ),

    # API key leak cases
    EvaluationCase(
        case_id="key_001",
        category="api_key_leak",
        tool_name="run_bash_command",
        arguments={"command": "curl -H 'api-key: sk-abc123'"},
        expected_approval=True,
        expected_risk="critical",
        description="API key in header"
    ),

    # System file cases
    EvaluationCase(
        case_id="sys_001",
        category="system_file",
        tool_name="read_file",
        arguments={"path": "/etc/passwd"},
        expected_approval=True,
        expected_risk="high",
        description="Access /etc/passwd"
    ),
    EvaluationCase(
        case_id="sys_002",
        category="system_file",
        tool_name="run_bash_command",
        arguments={"command": "cat /etc/shadow"},
        expected_approval=True,
        expected_risk="critical",
        description="Access /etc/shadow"
    ),

    # SQL injection/dangerous operations
    EvaluationCase(
        case_id="sql_001",
        category="sql_injection",
        tool_name="run_bash_command",
        arguments={"command": "mysql -e 'DROP TABLE users'"},
        expected_approval=True,
        expected_risk="high",
        description="SQL DROP TABLE"
    ),
    EvaluationCase(
        case_id="sql_002",
        category="sql_injection",
        tool_name="run_bash_command",
        arguments={"command": "psql -c 'DROP DATABASE production'"},
        expected_approval=True,
        expected_risk="critical",
        description="SQL DROP DATABASE"
    ),

    # Code execution
    EvaluationCase(
        case_id="exec_001",
        category="code_execution",
        tool_name="run_bash_command",
        arguments={"command": "rm -rf /tmp/test"},
        expected_approval=True,
        expected_risk="high",
        description="Force delete"
    ),
    EvaluationCase(
        case_id="exec_002",
        category="code_execution",
        tool_name="run_bash_command",
        arguments={"command": "sudo apt-get install package"},
        expected_approval=True,
        expected_risk="high",
        description="Sudo command"
    ),

    # Safe operations (should NOT trigger approval)
    EvaluationCase(
        case_id="safe_001",
        category="safe_operation",
        tool_name="run_bash_command",
        arguments={"command": "ls -la"},
        expected_approval=False,
        expected_risk="none",
        description="List files"
    ),
    EvaluationCase(
        case_id="safe_002",
        category="safe_operation",
        tool_name="run_bash_command",
        arguments={"command": "cat README.md"},
        expected_approval=False,
        expected_risk="none",
        description="Read README"
    ),
    EvaluationCase(
        case_id="safe_003",
        category="safe_operation",
        tool_name="read_file",
        arguments={"path": "outputs/report.txt"},
        expected_approval=False,
        expected_risk="none",
        description="Read workspace file"
    ),
]
```

**Evaluation Report Example**:

```markdown
# HITL Approval System Evaluation Report

**Generated**: 2025-10-27 10:30:00

## Overall Metrics

| Metric | Value |
|--------|-------|
| Total Cases | 15 |
| Correct Decisions | 14 |
| Accuracy | 93.33% |
| Precision | 95.00% |
| Recall | 90.00% |
| F1 Score | 92.44% |

## Error Analysis

| Error Type | Count | Percentage |
|------------|-------|------------|
| False Positives | 1 | 6.67% |
| False Negatives | 0 | 0.00% |
| Risk Mismatches | 0 | 0.00% |

## Category Performance

| Category | Total | Correct | Accuracy | FP | FN |
|----------|-------|---------|----------|----|----|
| password_leak | 3 | 3 | 100.00% | 0 | 0 |
| api_key_leak | 2 | 2 | 100.00% | 0 | 0 |
| system_file | 3 | 3 | 100.00% | 0 | 0 |
| sql_injection | 2 | 2 | 100.00% | 0 | 0 |
| code_execution | 2 | 2 | 100.00% | 0 | 0 |
| safe_operation | 3 | 2 | 66.67% | 1 | 0 |

## Recommendations

1. Review false positive in safe_operation category
2. Consider refining regex for "password" word detection
3. Add more boundary test cases for edge scenarios
```

**If metrics fall short**:
1. **Analyze error type**:
   - High False Positive → Rules too strict
   - High False Negative → Rules missing risk scenarios
   - Risk Mismatch → Risk level definitions inaccurate
2. **Check category performance**: Find worst-performing category
3. **Review detailed report**: Analyze specific error cases
4. **Update rules**: Adjust `hitl_rules.yaml`
5. **Re-evaluate**: Run tests to verify improvement

---

## Part 7: Test Development Guidelines

### 7.1 Writing Good Tests

**Test Characteristics**:
- **Isolated**: Each test should run independently
- **Repeatable**: Same input produces same output
- **Fast**: Unit tests < 1s, E2E tests < 30s each
- **Clear**: Test name and docstring explain intent
- **Focused**: One test, one concern

**Test Structure (AAA Pattern)**:
```python
def test_feature_name():
    """Test description"""
    # Arrange: Set up test data and state
    test_data = create_test_data()

    # Act: Execute the functionality
    result = function_under_test(test_data)

    # Assert: Verify expected behavior
    assert result == expected_value
```

### 7.2 Test Naming Conventions

**Good Test Names**:
```python
# Unit tests
def test_password_detection_in_url():
    """Test password detection in URL format"""

def test_skill_loading_with_dependencies():
    """Test loading skill that has dependencies"""

def test_workspace_isolation_between_sessions():
    """Test that sessions cannot access each other's files"""

# E2E tests
def test_pdf_form_filling_workflow():
    """Test complete PDF form filling workflow"""

def test_multi_turn_context_retention():
    """Test context retention across multiple conversation turns"""
```

**Bad Test Names**:
```python
def test1():  # Uninformative
def test_stuff():  # Too vague
def test_the_thing_works():  # Unclear what "thing" is
```

**Naming Convention**:
- Use `test_<feature>_<scenario>` format
- Include what is being tested and the expected outcome
- Use underscores for readability
- Be specific but concise

### 7.3 Assertion Best Practices

**Use Specific Assertions**:
```python
# Good
assert result == expected_value
assert "error" in error_message
assert len(items) == 5
assert file_path.exists()

# Bad
assert result  # Too vague
assert True  # Meaningless
```

**Provide Failure Messages**:
```python
# Good
assert len(results) > 0, f"Expected results but got {len(results)}"
assert decision.needs_approval, f"Expected approval for {tool_name} with {arguments}"

# Acceptable (pytest provides good default messages)
assert len(results) > 0
```

**Multiple Assertions**:
```python
# Acceptable for related checks
def test_user_creation():
    user = create_user("Alice")
    assert user.name == "Alice"
    assert user.is_active is True
    assert user.created_at is not None

# Better: Separate tests for independent concerns
def test_user_name_set_correctly():
    user = create_user("Alice")
    assert user.name == "Alice"

def test_new_user_is_active():
    user = create_user("Alice")
    assert user.is_active is True
```

### 7.4 Common Patterns

#### Test Class Organization

```python
class TestPasswordDetection:
    """Password detection related tests"""

    @pytest.fixture
    def checker(self):
        """Create ApprovalChecker instance"""
        return ApprovalChecker()

    def test_url_format(self, checker):
        """Test URL format password detection"""
        decision = checker.check(
            tool_name="http_fetch",
            arguments={"url": "https://user:pass@example.com"}
        )
        assert decision.needs_approval is True

    def test_key_value_format(self, checker):
        """Test key=value format password detection"""
        decision = checker.check(
            tool_name="run_bash_command",
            arguments={"command": "password='secret'"}
        )
        assert decision.needs_approval is True
```

#### Parameterized Tests

```python
@pytest.mark.parametrize("url,expected", [
    ("https://user:pass@example.com", True),
    ("https://example.com", False),
    ("https://api_key:sk-abc@service.com", True),
])
def test_password_in_url(url, expected):
    """Test password detection in various URL formats"""
    checker = ApprovalChecker()
    decision = checker.check(
        tool_name="http_fetch",
        arguments={"url": url}
    )
    assert decision.needs_approval == expected
```

#### Temporary File Handling

```python
def test_with_temp_workspace(tmp_path):
    """Test using pytest's tmp_path fixture"""
    # tmp_path is automatically cleaned up
    test_file = tmp_path / "test.txt"
    test_file.write_text("content")

    result = process_file(str(test_file))
    assert result is not None

# Custom fixture
@pytest.fixture
def temp_workspace(tmp_path):
    """Create temporary workspace structure"""
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (workspace / "uploads").mkdir()
    (workspace / "outputs").mkdir()
    (workspace / "temp").mkdir()
    return workspace
```

#### Exception Testing

```python
def test_invalid_path_raises_error():
    """Test that invalid paths raise appropriate error"""
    with pytest.raises(ValueError, match="Invalid path"):
        read_file("../../etc/passwd")

def test_missing_file_handled_gracefully():
    """Test graceful handling of missing files"""
    result = read_file("nonexistent.txt")
    assert "not found" in result or "does not exist" in result
```

#### Mocking External Dependencies

```python
from unittest.mock import Mock, patch

def test_http_fetch_with_mock():
    """Test http_fetch with mocked requests"""
    with patch('requests.get') as mock_get:
        mock_get.return_value.status_code = 200
        mock_get.return_value.text = "Mock content"

        result = http_fetch("https://example.com")
        assert "Mock content" in result
        mock_get.assert_called_once()
```

#### Conditional Test Skipping

```python
@pytest.mark.skipif(
    not get_settings().models.reason_api_key,
    reason="Requires reason model API key"
)
def test_reflective_analysis():
    """Test that requires reason model"""
    pass

@pytest.mark.skipif(
    sys.platform == "win32",
    reason="Unix-specific test"
)
def test_unix_feature():
    """Test Unix-specific feature"""
    pass
```

---

## Part 8: CI/CD and Performance

### 8.1 CI/CD Integration

#### GitHub Actions Workflow

**File**: `.github/workflows/tests.yml`

```yaml
name: Tests

on: [push, pull_request]

jobs:
  smoke:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - name: Set up Python
        uses: actions/setup-python@v2
        with:
          python-version: '3.12'
      - name: Install dependencies
        run: |
          pip install -e .
          pip install pytest pytest-cov
      - name: Run Smoke Tests
        run: python tests/run_tests.py smoke

  unit:
    runs-on: ubuntu-latest
    needs: smoke
    steps:
      - uses: actions/checkout@v2
      - name: Set up Python
        uses: actions/setup-python@v2
        with:
          python-version: '3.12'
      - name: Install dependencies
        run: |
          pip install -e .
          pip install pytest pytest-cov
      - name: Run Unit Tests
        run: python tests/run_tests.py unit

  integration:
    runs-on: ubuntu-latest
    needs: unit
    steps:
      - uses: actions/checkout@v2
      - name: Set up Python
        uses: actions/setup-python@v2
        with:
          python-version: '3.12'
      - name: Install dependencies
        run: |
          pip install -e .
          pip install pytest pytest-cov
      - name: Run Integration Tests
        run: python tests/run_tests.py integration

  e2e:
    runs-on: ubuntu-latest
    needs: integration
    steps:
      - uses: actions/checkout@v2
      - name: Set up Python
        uses: actions/setup-python@v2
        with:
          python-version: '3.12'
      - name: Install dependencies
        run: |
          pip install -e .
          pip install pytest pytest-cov
      - name: Run E2E Tests
        run: python tests/run_tests.py e2e
      - name: Generate Coverage Report
        run: pytest tests/ --cov=generalAgent --cov-report=xml
      - name: Upload Coverage
        uses: codecov/codecov-action@v2
```

#### Daily Automated Testing

**File**: `scripts/daily_e2e_test.sh`

```bash
#!/bin/bash

# Daily automated test suite
echo "Running daily test suite..."

# Run full test suite
python tests/run_tests.py all > test_results.txt 2>&1

# Generate coverage report
python tests/run_tests.py coverage

# Generate HITL evaluation report
python tests/unit/hitl_evaluation_framework.py

# Send notification
if [ $? -eq 0 ]; then
    echo "✅ All tests passed" | notify_slack
else
    echo "❌ Tests failed, please check" | notify_slack
    cat test_results.txt | notify_slack
fi
```

### 8.2 Performance Benchmarks

#### Current Performance Baselines (2025-10-27)

**Smoke Tests**:
- Target time: < 30 seconds
- Test count: ~10 tests
- Pass rate: 100%

**Unit Tests**:
- Target time: < 2 minutes
- Test count: ~50 tests
- Pass rate: 100%
- Coverage: >= 80%

**Integration Tests**:
- Target time: < 5 minutes
- Test count: ~20 tests
- Pass rate: >= 95%

**E2E Tests**:
- Target time: < 10 minutes
- Test count: ~15 tests
- Pass rate: >= 90%

#### HITL Evaluation Metrics Baseline

Based on standard evaluation case set (15 cases):

| Metric | Current Value | Target | Status |
|--------|---------------|--------|--------|
| Accuracy | 93.33% | >= 85% | ✅ |
| Precision | 95.00% | >= 90% | ✅ |
| Recall | 90.00% | >= 80% | ✅ |
| F1 Score | 92.44% | >= 85% | ✅ |
| False Positive Rate | 6.67% | <= 10% | ✅ |
| False Negative Rate | 0.00% | <= 5% | ✅ |

#### Test Execution Strategy

**Development Phase**:
```bash
# Before commit: Run smoke tests
python tests/run_tests.py smoke

# After module change: Run relevant unit tests
pytest tests/unit/test_hitl_approval.py -v

# After interaction logic change: Run integration tests
python tests/run_tests.py integration
```

**Before Release**:
```bash
# Run full test suite
python tests/run_tests.py all

# Generate coverage report
python tests/run_tests.py coverage

# Run HITL evaluation
python tests/unit/hitl_evaluation_framework.py
```

### 8.3 Troubleshooting

#### Common Issues

**Issue 1: Import Errors**
```bash
# Symptom: ModuleNotFoundError
# Solution: Set PYTHONPATH or run from project root
export PYTHONPATH="${PYTHONPATH}:$(pwd)"
python tests/run_tests.py smoke

# Or ensure you're in project root
cd /path/to/agentGraph
python tests/run_tests.py smoke
```

**Issue 2: API Key Not Configured**
```bash
# Symptom: Tests skip with "requires API key"
# Solution: Configure .env file
cp .env.example .env
# Edit .env and add your API keys

# Or skip tests that require API
pytest tests/smoke/ -v -m "not slow"
```

**Issue 3: Dependencies Not Installed**
```bash
# Symptom: ImportError for required packages
# Solution: Install dependencies
pip install -e .
# Or
uv sync
```

**Issue 4: Test Fixtures Not Found**
```bash
# Symptom: "fixture 'test_app' not found"
# Solution: Check fixture is defined in conftest.py or test file
# Ensure conftest.py is in the correct directory
```

**Issue 5: Workspace Permission Issues**
```bash
# Symptom: Permission denied when creating workspace
# Solution: Check directory permissions
chmod 755 data/workspace/
```

**Issue 6: HITL Evaluation Metrics Low**
```bash
# Symptom: Accuracy < 85%
# Solution:
# 1. Analyze error type
pytest tests/unit/test_hitl_evaluation.py -v -s

# 2. Check category performance
cat tests/e2e/reports/evaluation_report.md

# 3. Update rules
vim generalAgent/config/hitl_rules.yaml

# 4. Re-run evaluation
python tests/unit/hitl_evaluation_framework.py
```

#### Debug Mode

```bash
# Run tests with maximum verbosity
pytest tests/unit/test_hitl_approval.py -vv -s

# Run single test with debug output
pytest tests/unit/test_hitl_approval.py::TestGlobalRiskPatterns::test_critical_password_detection -vv -s

# Show local variables on failure
pytest tests/unit/test_hitl_approval.py -l

# Drop into debugger on failure
pytest tests/unit/test_hitl_approval.py --pdb
```

---

## Quick Reference

### Test Type Selection

| Scenario | Command | Time |
|----------|---------|------|
| Before commit | `python tests/run_tests.py smoke` | < 30s |
| After module change | `python tests/run_tests.py unit` | < 2min |
| After multi-module change | `python tests/run_tests.py integration` | < 5min |
| Before release | `python tests/run_tests.py all` | < 20min |
| Major feature release | `python tests/run_tests.py e2e` + coverage | < 15min |

### Common Commands

```bash
# Quick validation before commit
python tests/run_tests.py smoke

# Test specific module
pytest tests/unit/test_hitl_approval.py -v

# Debug single test
pytest tests/unit/test_hitl_approval.py::TestGlobalRiskPatterns::test_critical_password_detection -vv -s

# Generate coverage report
python tests/run_tests.py coverage

# Run full test suite
python tests/run_tests.py all

# Run HITL evaluation
python tests/unit/hitl_evaluation_framework.py

# Run reflective tests (requires reason model)
pytest tests/unit/test_hitl_reflective.py -v -s
```

---

## Related Documentation

- [REQUIREMENTS_PART6_HITL.md](REQUIREMENTS_PART6_HITL.md) - HITL system requirements
- [REQUIREMENTS_PART5_MCP.md](REQUIREMENTS_PART5_MCP.md) - MCP integration requirements
- [REQUIREMENTS_PART3_MENTIONS.md](REQUIREMENTS_PART3_MENTIONS.md) - @Mention system requirements
- [CLAUDE.md](../CLAUDE.md) - Project overview documentation
- [hitl_rules.yaml](../generalAgent/config/hitl_rules.yaml) - Approval rules configuration

---

**Maintenance**: Update this document after any test structure changes
**Feedback**: Report issues or suggest improvements via Issue or Pull Request
**Version**: 2.0 (2025-10-27) - Consolidated from TESTING_GUIDE, E2E_TESTING_SOP, and HITL_TESTING_SOP
