# Skills Configuration Guide

## Overview

The AgentGraph skills system is configuration-driven, allowing you to control:
- Which skills appear in the SystemMessage catalog
- Which skills auto-load when files are uploaded
- Dynamic file upload hints based on file types

Configuration file: `generalAgent/config/skills.yaml`

## Configuration Structure

```yaml
# Global settings
global:
  enabled: true                    # Enable/disable entire skills system
  auto_load_on_file_upload: true  # Auto-load skills when matching files uploaded

# Core skills - Always loaded at startup
core: []  # Empty by default

# Optional skills - Load on demand
optional:
  pdf:
    enabled: false                           # Show in catalog and load at startup
    always_available: false                  # Keep loaded across all sessions
    description: "PDF processing and form filling"
    auto_load_on_file_types: ["pdf"]        # Auto-load when .pdf files uploaded

  docx:
    enabled: true
    always_available: false
    description: "DOCX file processing"
    auto_load_on_file_types: ["docx"]

  xlsx:
    enabled: true
    always_available: false
    description: "Excel file processing"
    auto_load_on_file_types: ["xlsx", "xls"]

# Skills directories
directories:
  builtin: "generalAgent/skills"
```

## Configuration Options

### Global Settings

- **`global.enabled`**: Master switch for skills system (default: `true`)
- **`global.auto_load_on_file_upload`**: Auto-load skills when user uploads matching files (default: `true`)

### Skill-Level Settings

- **`enabled: true/false`**
  - `true`: Skill appears in SystemMessage catalog, available from startup
  - `false`: Skill hidden from catalog, only loads via @mention or file upload
  - **Use case**: Hide experimental or rarely-used skills to reduce prompt noise

- **`always_available`**: Keep skill loaded across all sessions (not recommended)
  - Default: `false` (skills load per-session)

- **`description`**: Human-readable description shown in catalog

- **`auto_load_on_file_types`**: File extensions that trigger auto-loading
  - Example: `["pdf"]`, `["docx", "doc"]`, `["xlsx", "xls", "csv"]`
  - Uses actual file extensions (not generic types like "office")

## How It Works

### 1. Skills Catalog Filtering

**Code**: `generalAgent/graph/prompts.py:build_skills_catalog()`

Only skills with `enabled: true` appear in the SystemMessage:

```python
def build_skills_catalog(skill_registry, skill_config=None):
    all_skills = skill_registry.list_meta()

    if skill_config:
        enabled_skill_ids = set(skill_config.get_enabled_skills())
        skills = [s for s in all_skills if s.id in enabled_skill_ids]
    else:
        skills = all_skills  # Fallback: show all

    # Build catalog...
```

**Benefits**:
- Reduces SystemMessage size
- Prevents information leakage about disabled skills
- Agent won't try to use skills it doesn't know about

### 2. Dynamic File Upload Hints

**Code**: `generalAgent/utils/file_processor.py:build_file_upload_reminder()`

When user uploads a file, hints are generated based on `auto_load_on_file_types`:

```python
def build_file_upload_reminder(processed_files, skill_config=None):
    for file in documents:
        # Extract file extension (e.g., "docx", "pdf")
        file_ext = Path(filename).suffix.lstrip('.').lower()

        # Find skills that handle this extension
        skills_for_type = skill_config.get_skills_for_file_type(file_ext)

        if skills_for_type:
            skill_mentions = ", ".join([f"@{s}" for s in skills_for_type])
            skill_hint = f" [可用 {skill_mentions} 处理]"
```

**Example output**:
```
用户上传了 3 个文件：
1. report.pdf (PDF, 1.5 MB) → uploads/report.pdf [可用 @pdf 处理]
2. data.xlsx (OFFICE, 500 KB) → uploads/data.xlsx [可用 @xlsx 处理]
3. summary.docx (OFFICE, 300 KB) → uploads/summary.docx [可用 @docx 处理]
```

### 3. Configuration Pipeline

```
build_application()
  ↓ loads skills.yaml
  ↓ returns skill_config
  ↓
build_state_graph(skill_config)
  ↓ passes to planner
  ↓
build_planner_node(skill_config)
  ↓ uses for filtering and hints
  ↓
planner_node() execution
  ├─ build_skills_catalog(skill_config)  → Filter catalog
  └─ build_file_upload_reminder(skill_config)  → Generate hints
```

## Use Cases

### Use Case 1: Hide Experimental Skills

You have a new `experimental-ocr` skill that's not ready for production:

```yaml
optional:
  experimental-ocr:
    enabled: false  # Hidden from catalog
    description: "Experimental OCR processing"
    auto_load_on_file_types: ["png", "jpg"]
```

**Result**:
- Skill not shown in SystemMessage
- User can still access via `@experimental-ocr`
- Auto-loads when image files uploaded

### Use Case 2: Default Skills for Common Tasks

Enable commonly-used skills by default:

```yaml
optional:
  pdf:
    enabled: true  # Always visible
    auto_load_on_file_types: ["pdf"]

  docx:
    enabled: true
    auto_load_on_file_types: ["docx"]

  xlsx:
    enabled: true
    auto_load_on_file_types: ["xlsx"]
```

**Result**:
- Skills always in catalog
- Agent knows about them from start
- Auto-load on file upload

### Use Case 3: Progressive Disclosure

Start with minimal skills, add more as needed:

```yaml
# Default config: Most skills disabled
optional:
  pdf:
    enabled: false
  docx:
    enabled: false
  xlsx:
    enabled: false
  # ... all disabled

# User workflow:
# 1. Uploads a PDF → pdf skill auto-loads
# 2. Agent sees skill in workspace, can use it
# 3. Or user types @pdf to load explicitly
```

## Testing

### Unit Test

Run skills filtering tests:

```bash
pytest tests/unit/test_skills_filtering.py -v
```

**Expected output**:
```
============================================================
测试 1: Skills Catalog 只显示已启用的技能
============================================================

✓ 从配置读取的已启用技能: ['docx', 'xlsx', 'pptx']
✓ 文件系统扫描到的所有技能: ['xlsx', 'pdf', 'skill-creator', 'pptx', 'artifacts-builder', 'docx']

✓ 启用的技能数量: 3
✓ 扫描到的技能数量: 6
✓ 过滤成功: 只有部分技能被启用

============================================================
测试 2: 文件上传提示根据配置动态生成
============================================================

✓ 找到 @docx 提示
✓ 找到 @pptx 提示
✓ 回退模式正常: 只提示 PDF (硬编码)

============================================================
测试完成!
============================================================
```

### Integration Test

Check application logs:

```bash
python main.py <<EOF
你好
/quit
EOF

# Check log
grep "enabled skills" logs/agentgraph_*.log
# Should show: "Using MAIN AGENT prompt with 3 enabled skills"
```

## Migration Notes

### Before (Hardcoded)

- `FILE_TYPE_TO_SKILL` constant in `file_processor.py`
- Skills catalog showed all scanned skills
- File hints hardcoded for PDF only

### After (Config-Driven)

- `FILE_TYPE_TO_SKILL` removed
- Skills catalog filtered by `enabled: true`
- File hints generated from `auto_load_on_file_types`

### Breaking Changes

**None** - The system is backward compatible:
- If `skill_config` is not provided, falls back to old behavior (show all skills)
- Existing skills work without modification

## Related Files

- **Config**: `generalAgent/config/skills.yaml`
- **Loader**: `generalAgent/config/skill_config_loader.py`
- **Catalog**: `generalAgent/graph/prompts.py:build_skills_catalog()`
- **Hints**: `generalAgent/utils/file_processor.py:build_file_upload_reminder()`
- **Application**: `generalAgent/runtime/app.py:build_application()`
- **Test**: `test_skills_filtering.py`

## Troubleshooting

### Issue: Skills not showing in catalog

**Check**:
1. Is `enabled: true` in `skills.yaml`?
2. Does the skill directory exist in `generalAgent/skills/`?
3. Check logs for "enabled skills" count

### Issue: File upload hints not working

**Check**:
1. Is `auto_load_on_file_upload: true` in global settings?
2. Does `auto_load_on_file_types` include the file extension?
3. Use actual extension (e.g., `"docx"`) not generic type (e.g., `"office"`)

### Issue: All skills showing despite config

**Check**:
1. Is `skill_config` being passed to `build_skills_catalog()`?
2. Check if `build_application()` returns `skill_config`
3. Verify `build_planner_node()` receives and uses `skill_config`
