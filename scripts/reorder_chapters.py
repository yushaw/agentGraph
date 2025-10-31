#!/usr/bin/env python3
"""
重新排序PRD章节
按照P0/P1/P2优先级重组文档结构
"""

from pathlib import Path
import re


def extract_sections(content: str) -> dict:
    """提取所有一级章节"""
    sections = {}
    lines = content.split('\n')

    current_section = None
    current_content = []

    for i, line in enumerate(lines):
        # 检测一级标题
        if re.match(r'^# \d+\.|^# [^#]', line):
            # 保存前一个章节
            if current_section:
                sections[current_section] = '\n'.join(current_content)

            # 开始新章节
            current_section = line
            current_content = [line]
        elif line.startswith('---') and i < 10:
            # 文档头部的元数据分隔符
            if not current_section:
                current_content.append(line)
        else:
            # 累积当前章节内容
            current_content.append(line)

    # 保存最后一个章节
    if current_section:
        sections[current_section] = '\n'.join(current_content)

    return sections


def reorder_document(doc_path: Path) -> str:
    """重新排序文档"""
    content = doc_path.read_text(encoding='utf-8')

    # 提取文档头部(元数据)
    header_match = re.match(r'^(---.*?---)\n', content, re.DOTALL)
    header = header_match.group(1) if header_match else ''

    # 提取所有章节
    sections = extract_sections(content)

    # 定义新的章节顺序
    new_order = [
        '# 产品架构',  # 总览
        '# 2. Agent 流程与状态管理',  # P0核心
        '# 3. 工具系统',  # P0
        '# 4. 技能系统',  # P0
        '# 5. HITL 人机协同',  # P0
        '# 6. 上下文管理',  # P0
        '# 7. 模型路由系统',  # P1
        '# 8. 多Agent协作',  # P1
        '# 9. Agent 模板系统',  # P1
        '# 10. 工作区管理',  # P1
        '# 11. 文件处理',  # P1
        '# 12. 会话管理',  # P1
        '# Prompt清单',  # 附录
        '# 快速开始',  # 附录
    ]

    # 重组文档
    result_parts = [header, '']

    for section_title in new_order:
        # 查找匹配的章节(允许标题略有不同)
        matched_section = None
        for key in sections.keys():
            if section_title in key or key.startswith(section_title.split('.')[0]):
                matched_section = key
                break

        if matched_section:
            result_parts.append(sections[matched_section])
            result_parts.append('\n---\n')

    return '\n'.join(result_parts)


def main():
    """主函数"""
    doc_path = Path('docs/桌面 AI 框架需求.md')
    output_path = Path('docs/桌面 AI 框架需求_reordered.md')

    print(f"读取文档: {doc_path}")

    # 重新排序
    print("重新排序章节...")
    reordered_content = reorder_document(doc_path)

    # 写入新文件
    print(f"写入新文档: {output_path}")
    output_path.write_text(reordered_content, encoding='utf-8')

    print("\n✅ 章节重排完成！")
    print("请检查 docs/桌面 AI 框架需求_reordered.md")


if __name__ == '__main__':
    main()
