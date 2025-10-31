#!/usr/bin/env python3
"""
文档重构脚本 - 自动化PRD文档的章节重组和格式修复
"""
import re
from pathlib import Path

def read_file(path):
    """读取文件"""
    with open(path, 'r', encoding='utf-8') as f:
        return f.read()

def extract_sections(content):
    """提取所有主要章节"""
    sections = {}

    # 定义所有需要提取的章节的标识模式
    patterns = {
        'header': (0, 9),  # 文档头部(元数据)
        'product_arch': (9, 1083),  # 产品架构 + 快速开始 + Prompt清单
        'tool_system': (1083, 2212),  # 一、工具系统
        'skill_system': (2212, 2543),  # 二、技能系统
        'agent_flow': (2543, 3190),  # 四、Agent流程与状态管理
        'hitl': (3190, 3846),  # 五、HITL人机协同
        'context_mgmt': (6028, 6460),  # 六、上下文管理
        'model_routing': (4102, 4606),  # 七、模型路由系统
        'multi_agent': (5402, 6028),  # 八、多Agent协作
        'agent_template': (4606, 5402),  # 三、Agent模板系统
        'workspace': (3846, 3888),  # 九、工作区管理
        'file_handling': (3888, 4102),  # 十、文件处理
        'session_mgmt': (6460, 6862),  # 会话管理(需要找到)
        'config_system': (6862, 7842),  # 配置系统汇总
        'security': (7842, 8770),  # 安全与合规
    }

    lines = content.split('\n')

    for key, (start, end) in patterns.items():
        sections[key] = '\n'.join(lines[start:end])

    return sections

def fix_code_blocks(text):
    """修复代码块标记问题"""
    # 修复 # Python 3.12+ 这类注释标记
    text = re.sub(r'^# (Python|Bash|Shell|JavaScript|TypeScript|Go|Rust|Java).*$',
                  r'```\1\n\n```', text, flags=re.MULTILINE)

    # 修复其他常见的注释式代码块
    text = re.sub(r'^# (DeepSeek|OpenAI|GLM|Kimi|Base|Reasoning|Vision|Code|Chat).*$',
                  r'```bash\n\n```', text, flags=re.MULTILINE)

    return text

def unify_chapter_headers(text, chapter_num, title):
    """统一章节标题为 # {num}. {title}"""
    # 移除旧的编号(中文数字或阿拉伯数字)
    old_patterns = [
        rf'^#+ [一二三四五六七八九十]+、{re.escape(title)}',
        rf'^#+ {chapter_num}[.、]{re.escape(title)}',
        rf'^## {re.escape(title)}',
        rf'^# {re.escape(title)}',
    ]

    for pattern in old_patterns:
        text = re.sub(pattern, f'# {chapter_num}. {title}', text, flags=re.MULTILINE)

    return text

def main():
    """主函数"""
    doc_path = Path(__file__).parent / '桌面 AI 框架需求.md'
    output_path = Path(__file__).parent / '桌面 AI 框架需求_restructured.md'

    print("读取原文档...")
    content = read_file(doc_path)

    print("提取章节...")
    sections = extract_sections(content)

    print("重组文档...")
    # 按照新的顺序组织章节
    new_order = [
        ('header', None, None),  # 元数据头部
        ('product_arch', None, None),  # 产品架构(保持原样)
        ('agent_flow', 2, 'Agent流程与状态管理'),  # P0
        ('tool_system', 3, '工具系统'),  # P0
        ('skill_system', 4, '技能系统'),  # P0
        ('hitl', 5, 'HITL人机协同'),  # P0
        ('context_mgmt', 6, '上下文管理'),  # P0
        ('model_routing', 7, '模型路由系统'),  # P1
        ('multi_agent', 8, '多Agent协作'),  # P1
        ('agent_template', 9, 'Agent模板系统'),  # P1
        ('workspace', 10, '工作区管理'),  # P1
        ('file_handling', 11, '文件处理'),  # P1
        ('session_mgmt', 12, '会话管理'),  # P1
        ('config_system', 13, '配置系统汇总'),  # P2 - Appendix
        ('security', 14, '安全与合规'),  # P2
    ]

    result_parts = []

    for key, num, title in new_order:
        if key not in sections:
            print(f"警告: 未找到章节 {key}")
            continue

        section_content = sections[key]

        if num is not None and title is not None:
            # 统一章节标题
            section_content = unify_chapter_headers(section_content, num, title)

        # 修复代码块
        section_content = fix_code_blocks(section_content)

        result_parts.append(section_content)

    # 合并所有章节
    final_content = '\n\n---\n\n'.join(result_parts)

    print(f"写入新文档: {output_path}")
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(final_content)

    print("完成!")
    print(f"原文档行数: {len(content.split(chr(10)))}")
    print(f"新文档行数: {len(final_content.split(chr(10)))}")

if __name__ == '__main__':
    main()
