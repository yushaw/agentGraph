# AgentGraph Documentation

Welcome to the AgentGraph documentation! This guide will help you understand, use, and extend the AgentGraph framework.

## 📚 Documentation Structure

AgentGraph documentation is organized into six core documents, each focused on a specific aspect:

### [ARCHITECTURE.md](ARCHITECTURE.md)
**Core system architecture and design patterns**

- Part 1: Core Architecture (Agent Loop, State, Nodes, Routing)
- Part 2: Tool System (Three-tier architecture, Discovery, Configuration, TODO tools)
- Part 3: Skill System (Knowledge packages, Registry, Dependencies)
- Part 4: Best Practices (Path handling, Prompt engineering, Error handling)

**When to read**: Understanding system internals, implementing new features, architectural decisions

---

### [FEATURES.md](FEATURES.md)
**User-facing features and capabilities**

- Part 1: Workspace Isolation (File operations, Security, Sessions)
- Part 2: @Mention System (Tool/Skill/Agent loading)
- Part 3: File Upload System (Type detection, Processing)
- Part 4: Message History Management
- Part 5: Delegated agent System (Delegation, Context isolation)
- Part 6: MCP Integration (Protocol support, Configuration)
- Part 7: HITL (ask_human, Tool approval)

**When to read**: Using AgentGraph features, configuring system behavior, understanding workflows

---

### [DEVELOPMENT.md](DEVELOPMENT.md)
**Practical development guides**

- Part 1: Environment Setup (Installation, .env configuration)
- Part 2: Developing Tools (Creation, Configuration, Testing)
- Part 3: Developing Skills (Structure, Scripts, Dependencies)
- Part 4: Extending the System (Custom nodes, Routing, Services)
- Part 5: Development Best Practices
- Part 6: Debugging and Troubleshooting
- Part 7: Contributing

**When to read**: Setting up development environment, creating tools/skills, contributing code

---

### [OPTIMIZATION.md](OPTIMIZATION.md)
**Performance optimization techniques**

- Part 1: Context Management & KV Cache (70-90% cache reuse)
- Part 2: Document Search Optimization (Chunking, BM25, jieba)
- Part 3: Text Indexer (SQLite FTS5, Architecture, Performance)
- Part 4: Other Optimizations (Message history, Tool visibility, Delegated agent isolation)

**When to read**: Improving performance, understanding cache strategies, optimizing search

---

### [TESTING.md](TESTING.md)
**Comprehensive testing guide**

- Part 1: Testing Overview (Four-tier architecture)
- Part 2: Smoke Tests (Quick validation)
- Part 3: Unit Tests (Module testing, Fixtures)
- Part 4: Integration Tests (@mention, Tools, Skills)
- Part 5: E2E Tests (Business scenarios, SOPs)
- Part 6: HITL Testing (Approval, Evaluation framework)
- Part 7: Test Development Guidelines
- Part 8: CI/CD and Performance

**When to read**: Writing tests, running test suites, CI/CD setup, quality assurance

---

### [archive/](archive/)
**Archived documentation**

Contains previous versions of documentation that have been reorganized. See [archive/README.md](archive/README.md) for details.

---

## 🚀 Quick Start

### For New Users
1. Read the main [README.md](../README.md) in the project root
2. Follow installation instructions in [DEVELOPMENT.md - Part 1](DEVELOPMENT.md#part-1-environment-setup)
3. Understand core concepts in [ARCHITECTURE.md - Part 1](ARCHITECTURE.md#part-1-core-architecture)
4. Explore features in [FEATURES.md](FEATURES.md)

### For Developers
1. Set up environment: [DEVELOPMENT.md - Part 1](DEVELOPMENT.md#part-1-environment-setup)
2. Learn tool development: [DEVELOPMENT.md - Part 2](DEVELOPMENT.md#part-2-developing-tools)
3. Learn skill development: [DEVELOPMENT.md - Part 3](DEVELOPMENT.md#part-3-developing-skills)
4. Write tests: [TESTING.md](TESTING.md)

### For Performance Tuning
1. Understand KV Cache: [OPTIMIZATION.md - Part 1](OPTIMIZATION.md#part-1-context-management--kv-cache-optimization)
2. Optimize search: [OPTIMIZATION.md - Part 2-3](OPTIMIZATION.md#part-2-document-search-optimization)
3. Monitor metrics: [OPTIMIZATION.md - Performance sections](OPTIMIZATION.md)

---

## 📖 Documentation Maintenance Guide

### When to Update Documentation

Update documentation when:
- Adding new features or changing existing ones
- Fixing bugs that affect documented behavior
- Improving performance or changing optimization strategies
- Adding new tools, skills, or extending the system
- Changing configuration options or .env variables

### How to Update Documentation

#### 1. Identify Affected Documents

| Change Type | Affected Documents |
|-------------|-------------------|
| New architecture/design pattern | ARCHITECTURE.md |
| New feature (workspace, @mention, MCP, HITL) | FEATURES.md |
| New tool or skill | DEVELOPMENT.md + ARCHITECTURE.md |
| Performance improvement | OPTIMIZATION.md |
| New test or testing approach | TESTING.md |
| Environment/setup change | DEVELOPMENT.md |

#### 2. Update Process

**Step 1**: Update the relevant document
```bash
# Open the document
vim docs/ARCHITECTURE.md  # or FEATURES.md, etc.

# Add/modify content following existing structure
# - Keep file paths and line numbers accurate
# - Include code examples
# - Add design rationale
# - Update table of contents if needed
```

**Step 2**: Update cross-references
```bash
# If you added a new section, update cross-references in:
# - docs/README.md (this file)
# - Related sections in other docs
# - Main README.md
# - CLAUDE.md
```

**Step 3**: Update CHANGELOG
```bash
# Add entry to CHANGELOG.md
vim ../CHANGELOG.md

# Include:
# - Date
# - Type (Added/Changed/Fixed/Removed)
# - Brief description
# - Link to relevant docs section
```

**Step 4**: Verify
```bash
# Check all links work
# Verify code examples are accurate
# Ensure file paths are correct
# Test commands and examples
```

#### 3. Document Structure Guidelines

**Format**:
- Use clear hierarchical headers (## Part X, ### X.Y Section)
- Include table of contents at the top
- Add file paths in code blocks: `# path/to/file.py:line-numbers`
- Use code fences with language tags: \`\`\`python, \`\`\`bash, \`\`\`yaml

**Content**:
- **What**: Describe the feature/concept
- **Why**: Explain design rationale
- **How**: Show implementation with code examples
- **Where**: Provide file paths and line numbers
- **When**: Describe use cases and scenarios

**Examples**:
```markdown
### 2.3 Tool Configuration

**What**: Tools are configured via `generalAgent/config/tools.yaml`

**Why**: Declarative configuration allows enabling/disabling tools without code changes

**How**:
\`\`\`yaml
# generalAgent/config/tools.yaml
optional:
  my_tool:
    enabled: true
    available_to_subagent: false
    category: "utility"
\`\`\`

**Where**: 
- Configuration: `generalAgent/config/tools.yaml`
- Loader: `generalAgent/config/tool_config_loader.py:45-67`
- Registry: `generalAgent/tools/registry.py:89-102`

**When**: Use when you need to control tool availability at startup
```

#### 4. Keeping Documentation in Sync

**After Code Changes**:

1. **Architecture changes** → Update ARCHITECTURE.md
   ```bash
   # Example: Changed state management
   vim docs/ARCHITECTURE.md
   # Update Part 1: Core Architecture → 1.2 State Management
   ```

2. **New feature** → Update FEATURES.md + DEVELOPMENT.md
   ```bash
   # Example: Added new @mention type
   vim docs/FEATURES.md  # Part 2: @Mention System
   vim docs/DEVELOPMENT.md  # If it requires development guide
   ```

3. **Performance optimization** → Update OPTIMIZATION.md + CHANGELOG.md
   ```bash
   # Example: Improved cache strategy
   vim docs/OPTIMIZATION.md  # Part 1: Context Management
   vim CHANGELOG.md  # Add entry
   ```

4. **New test approach** → Update TESTING.md
   ```bash
   # Example: Added new test tier
   vim docs/TESTING.md  # Update Part 1: Testing Overview
   ```

**Regular Maintenance**:
- Monthly: Review for outdated information
- Per release: Verify all examples work
- After refactoring: Update file paths and line numbers

---

## 🔍 Finding Information

### By Topic

| Topic | Document | Section |
|-------|----------|---------|
| Agent Loop | ARCHITECTURE.md | Part 1.1 |
| State Management | ARCHITECTURE.md | Part 1.2 |
| Tools | ARCHITECTURE.md | Part 2 |
| Skills | ARCHITECTURE.md | Part 3 |
| TODO Tool | ARCHITECTURE.md | Part 2.7 |
| Workspace | FEATURES.md | Part 1 |
| @Mentions | FEATURES.md | Part 2 |
| File Upload | FEATURES.md | Part 3 |
| MCP | FEATURES.md | Part 6 |
| HITL | FEATURES.md | Part 7 |
| Environment Setup | DEVELOPMENT.md | Part 1 |
| Tool Development | DEVELOPMENT.md | Part 2 |
| Skill Development | DEVELOPMENT.md | Part 3 |
| KV Cache | OPTIMIZATION.md | Part 1 |
| Search | OPTIMIZATION.md | Part 2-3 |
| Testing | TESTING.md | All parts |

### By File Path

Use grep to find documentation for specific files:
```bash
# Find docs mentioning a specific file
grep -r "generalAgent/tools/registry.py" docs/*.md

# Find docs for a specific function
grep -r "build_planner_node" docs/*.md
```

---

## 📊 Documentation Statistics

| Document | Size | Lines | Last Updated |
|----------|------|-------|--------------|
| ARCHITECTURE.md | ~1500 lines | ~60 KB | 2025-10-27 |
| FEATURES.md | ~1200 lines | ~50 KB | 2025-10-27 |
| DEVELOPMENT.md | ~800 lines | ~35 KB | 2025-10-27 |
| OPTIMIZATION.md | ~1000 lines | ~65 KB | 2025-10-27 |
| TESTING.md | ~600 lines | ~25 KB | 2025-10-27 |
| **Total** | **~5100 lines** | **~235 KB** | - |

---

## 🤝 Contributing to Documentation

### Documentation Standards

1. **Accuracy**: All code examples must be tested and working
2. **Completeness**: Include file paths, line numbers, and context
3. **Clarity**: Write for both beginners and experts
4. **Maintainability**: Use consistent formatting and structure

### Pull Request Checklist

- [ ] Updated relevant documentation files
- [ ] Added code examples with file paths
- [ ] Updated table of contents if structure changed
- [ ] Updated cross-references in other docs
- [ ] Added entry to CHANGELOG.md
- [ ] Verified all links work
- [ ] Tested all code examples

### Review Process

Documentation changes are reviewed for:
- Technical accuracy
- Completeness of information
- Clarity and readability
- Consistency with existing docs
- Proper cross-references

---

## 📅 Recent Updates

- **2025-10-27**: Documentation reorganization (14 docs → 6 core docs)
- **2025-10-27**: Added TODO tool documentation (ARCHITECTURE.md Part 2.7)
- **2025-10-27**: Added SQLite FTS5 documentation (OPTIMIZATION.md Part 3)
- **2025-10-27**: Consolidated testing documentation (TESTING.md)

See [CHANGELOG.md](../CHANGELOG.md) for complete history.

---

## 📞 Getting Help

- **Questions**: Check relevant documentation first using the topic index
- **Issues**: Report at [GitHub Issues](https://github.com/yourusername/agentgraph/issues)
- **Discussions**: Use GitHub Discussions for Q&A
- **Documentation bugs**: Submit PR or open issue with "docs" label

---

**Last Updated**: 2025-10-27  
**Documentation Version**: 2.0 (Reorganized)
