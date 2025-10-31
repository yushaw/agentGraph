#!/usr/bin/env python3
"""
PRD文档重构脚本
功能：
1. 修复代码块标记（100+处）
2. 统一章节层级和编号（改为阿拉伯数字）
3. 重新组织章节顺序（P0/P1/P2）
4. 统一元数据
"""

import re
from pathlib import Path
from datetime import datetime


def fix_code_blocks(content: str) -> str:
    """修复代码块标记问题"""
    lines = content.split('\n')
    result = []
    in_code_block = False
    code_buffer = []
    code_type = None

    i = 0
    while i < len(lines):
        line = lines[i]

        # 检测代码块开始/结束
        if line.strip().startswith('```'):
            in_code_block = not in_code_block
            if not in_code_block and code_buffer:
                # 代码块结束，清空缓冲
                code_buffer = []
                code_type = None
            result.append(line)
            i += 1
            continue

        if in_code_block:
            # 在代码块内，直接保留
            result.append(line)
            i += 1
            continue

        # 检测误用的代码注释作为标题的情况
        # 特征：# 开头，但后面是代码、命令或文件路径
        if line.startswith('# ') and not line.startswith('## '):
            # 检查是否是真正的标题还是代码注释
            content_after_hash = line[2:].strip()

            # 识别代码注释的模式
            code_patterns = [
                r'^Python\s+\d',  # Python 3.12+
                r'^pip\s+',  # pip install
                r'^uv\s+',  # uv sync
                r'^\w+/\w+/',  # 文件路径 generalAgent/tools/
                r'^[\w-]+\.py$',  # Python文件
                r'^[\w-]+\.yaml$',  # YAML文件
                r'^[\w-]+\.md$',  # Markdown文件
                r'^[A-Z_]+\s*=',  # 环境变量赋值
                r'^Core tools',  # Core tools - Always enabled
                r'^Optional tools',  # Optional tools
                r'^\.mcp-config',  # .mcp-config.json
                r'^没有实际执行',  # 中文注释
                r'^检测到',  # 中文注释
                r'^场景\d+:',  # 场景说明
                r'^所有\w+文件',  # 文件描述
                r'^递归搜索',  # 操作描述
                r'^首次搜索',  # 操作描述
                r'^后续搜索',  # 操作描述
                r'^Token使用率',  # 功能描述
                r'^创建checkpointer',  # 代码注释
                r'^应用绑定',  # 代码注释
                r'^运行时配置',  # 代码注释
                r'^生成唯一',  # 代码注释
                r'^或使用',  # 代码注释
                r'^Base模型',  # 模型说明
                r'^Reasoning模型',  # 模型说明
                r'^Vision模型',  # 模型说明
                r'^Code模型',  # 模型说明
                r'^Chat模型',  # 模型说明
                r'^优先级\d+:',  # 优先级说明
                r'^\.env配置',  # 配置说明
                r'^转换为',  # 操作说明
                r'^resolver调用',  # 代码说明
                r'^返回:',  # 返回值说明
                r'^Planner节点',  # 节点说明
                r'^普通对话',  # 场景说明
                r'^代码生成',  # 场景说明
                r'^复杂推理',  # 场景说明
                r'^Subagent节点',  # 节点说明
                r'^方式\s*\d+:',  # 方式说明
                r'^系统自动',  # 系统说明
                r'^自定义',  # 自定义说明
                r'^完全自定义',  # 完全自定义
                r'^工作方式',  # 工作方式
                r'^加载\s+\w+',  # 加载说明
                r'^当用户',  # 场景说明
                r'^使用astream',  # 使用说明
                r'^策略\d+:',  # 策略说明
                r'^最终:',  # 最终说明
                r'^每个会话',  # 说明
                r'^移除未被',  # 说明
                r'^保留\w+',  # 说明
                r'^启动时生成',  # 说明
                r'^错误做法',  # 说明
                r'^正确做法',  # 说明
                r'^追加到',  # 说明
                r'^Workflow',  # 工作流
                r'^基于\s+\w+',  # 基于说明
                r'^Agent\s+[A-Z]',  # Agent说明
                r'^Manager\s+Agent',  # Manager说明
                r'^workflows/',  # 文件路径
                r'^文档处理',  # 处理说明
                r'^多源信息',  # 信息说明
                r'^项目管理',  # 管理说明
                r'^模型标识',  # 标识说明
                r'^上下文窗口',  # 窗口说明
                r'^自动审批',  # 审批说明
                r'^最大循环',  # 循环说明
                r'^历史消息',  # 消息说明
                r'^LangSmith',  # LangSmith
                r'^日志配置',  # 日志说明
                r'^会话持久化',  # 持久化说明
                r'^启用/禁用',  # 启用说明
                r'^三级阈值',  # 阈值说明
                r'^保留策略',  # 策略说明
                r'^压缩触发',  # 触发说明
                r'^应急回退',  # 回退说明
                r'^文件大小',  # 大小说明
                r'^文档分块',  # 分块说明
                r'^搜索配置',  # 配置说明
                r'^❌\s+',  # 错误标记
                r'^⚠️\s+',  # 警告标记
                r'^✅\s+',  # 成功标记
                r'^从项目根',  # 操作说明
                r'^从子目录',  # 操作说明
                r'^无论从',  # 说明
                r'^加载配置',  # 配置说明
                r'^检查全局',  # 检查说明
                r'^获取\w+',  # 获取说明
                r'^根据文件',  # 根据说明
                r'^检查单个',  # 检查说明
                r'^简洁',  # 简洁说明
                r'^冗长',  # 冗长说明
                r'^=+\s+',  # 分隔线注释
                r'^DeepSeek',  # 模型名
                r'^GLM',  # 模型名
                r'^Moonshot',  # 模型名
                r'^\d+\.',  # 数字列表(在代码块外单独出现)
                r'^参数化',  # 参数说明
                r'^不推荐',  # 建议说明
                r'^字符串',  # 字符串说明
                r'^pyproject',  # 项目文件
                r'^pip-audit',  # 工具名
                r'^safety',  # 工具名
                r'^bandit',  # 工具名
                r'^扫描',  # 操作
                r'^静态代码',  # 代码说明
                r'^CLI\s+命令',  # CLI命令
                r'^生产环境',  # 环境说明
                r'^开发环境',  # 环境说明
                r'^hitl_rules',  # 配置文件
                r'^关闭',  # 操作说明
                r'^限制',  # 限制说明
                r'^防止',  # 防止说明
                r'^查找',  # 查找操作
            ]

            is_code_comment = any(re.match(pattern, content_after_hash) for pattern in code_patterns)

            if is_code_comment:
                # 这是代码注释，需要放入代码块
                # 检查前一行是否已经是代码块
                if result and result[-1].strip().startswith('```'):
                    # 已在代码块内，直接添加
                    result.append(line)
                else:
                    # 需要创建新代码块
                    # 判断代码类型
                    if any(keyword in content_after_hash for keyword in ['python', '.py', 'import', 'def ', 'class ']):
                        code_type = 'python'
                    elif any(keyword in content_after_hash for keyword in ['.yaml', '.yml', 'enabled:', 'patterns:']):
                        code_type = 'yaml'
                    elif any(keyword in content_after_hash for keyword in ['.env', '_API_KEY', '_URL', '=']):
                        code_type = 'bash'
                    else:
                        code_type = 'bash'

                    # 检查下一行是否还是代码注释
                    look_ahead = []
                    j = i + 1
                    while j < len(lines) and lines[j].strip() and not lines[j].strip().startswith('```'):
                        next_line = lines[j]
                        if next_line.startswith('#') or next_line.startswith('- ['):
                            look_ahead.append(next_line)
                            j += 1
                        else:
                            break

                    if look_ahead:
                        # 多行代码，创建代码块
                        result.append(f'```{code_type}')
                        result.append(line)
                        result.extend(look_ahead)
                        result.append('```')
                        i = j
                        continue
                    else:
                        # 单行代码
                        result.append(f'```{code_type}')
                        result.append(line)
                        result.append('```')
                i += 1
                continue

        # 正常行，直接保留
        result.append(line)
        i += 1

    return '\n'.join(result)


def unify_chapter_numbering(content: str) -> str:
    """统一章节编号为阿拉伯数字"""
    # 中文数字到阿拉伯数字的映射
    chinese_to_arabic = {
        '一': '1', '二': '2', '三': '3', '四': '4', '五': '5',
        '六': '6', '七': '7', '八': '8', '九': '9', '十': '10',
        '十一': '11', '十二': '12', '十三': '13', '十四': '14', '十五': '15'
    }

    lines = content.split('\n')
    result = []

    for line in lines:
        # 匹配模式: ## 四、Agent 流程 -> # 4. Agent 流程
        match = re.match(r'^##\s+([一二三四五六七八九十]+)、\s*(.+)$', line)
        if match:
            chinese_num, title = match.groups()
            arabic_num = chinese_to_arabic.get(chinese_num, chinese_num)
            result.append(f'# {arabic_num}. {title}')
            continue

        # 匹配模式: # 一、工具系统 -> # 1. 工具系统
        match = re.match(r'^#\s+([一二三四五六七八九十]+)、\s*(.+)$', line)
        if match:
            chinese_num, title = match.groups()
            arabic_num = chinese_to_arabic.get(chinese_num, chinese_num)
            result.append(f'# {arabic_num}. {title}')
            continue

        result.append(line)

    return '\n'.join(result)


def main():
    """主函数"""
    doc_path = Path('docs/桌面 AI 框架需求.md')

    # 读取原文档
    print(f"读取文档: {doc_path}")
    content = doc_path.read_text(encoding='utf-8')

    # 1. 修复代码块
    print("步骤 1/2: 修复代码块标记...")
    content = fix_code_blocks(content)

    # 2. 统一章节编号
    print("步骤 2/2: 统一章节编号...")
    content = unify_chapter_numbering(content)

    # 写入临时文件
    temp_path = Path('docs/桌面 AI 框架需求_temp.md')
    print(f"写入临时文件: {temp_path}")
    temp_path.write_text(content, encoding='utf-8')

    print("\n✅ 步骤 1-2 完成！")
    print("下一步需要手动重组章节顺序（步骤3-6）")


if __name__ == '__main__':
    main()
