"""System prompts shared across nodes - Charlie MVP Edition.

使用 Jinja2 模板系统加载 Prompt，支持自定义模板。
"""

from datetime import datetime, timezone
from generalAgent.utils.prompt_builder import PromptBuilder


def get_current_datetime_tag() -> str:
    """Get current date and time in XML tag format.

    Returns:
        String like "<current_datetime>2025-01-24 15:30:45 UTC</current_datetime>"
    """
    now = datetime.now(timezone.utc)
    datetime_str = now.strftime("%Y-%m-%d %H:%M:%S UTC")
    return f"<current_datetime>{datetime_str}</current_datetime>"


# ========== Load System Prompts from Jinja2 Templates ==========

# Charlie Base Identity
CHARLIE_BASE_IDENTITY = PromptBuilder.load_charlie_identity()

# Planner System Prompt
PLANNER_SYSTEM_PROMPT = PromptBuilder.load_planner_prompt()

# Subagent System Prompt
SUBAGENT_SYSTEM_PROMPT = PromptBuilder.load_subagent_prompt()

# Finalize System Prompt
FINALIZE_SYSTEM_PROMPT = PromptBuilder.load_finalize_prompt()


# ========== Dynamic System Reminders ==========
def build_skills_catalog(skill_registry, skill_config=None) -> str:
    """Build skills catalog for model-invoked pattern.

    Returns a formatted list of available skills with descriptions and paths.
    This allows the model to autonomously decide when to use skills.

    Args:
        skill_registry: SkillRegistry instance
        skill_config: SkillConfig instance (optional, for filtering)

    Returns:
        Formatted skills catalog string
    """
    all_skills = skill_registry.list_meta()

    # Filter skills based on config (only show enabled skills or those mentioned)
    if skill_config:
        enabled_skill_ids = set(skill_config.get_enabled_skills())
        # Include core skills and enabled optional skills
        skills = [s for s in all_skills if s.id in enabled_skill_ids]
    else:
        # Fallback: show all skills if no config provided
        skills = all_skills

    if not skills:
        return ""

    lines = ["# 可用技能（Skills）"]
    lines.append("")

    for skill in skills:
        lines.append(f"## {skill.name} (#{skill.id})")
        lines.append(f"{skill.description}")
        # Use workspace-relative path (skills are symlinked to workspace/skills/)
        lines.append(f"📁 路径: `skills/{skill.id}/SKILL.md`")
        lines.append("")

    return "\n".join(lines)


def build_dynamic_reminder(
    *,
    active_skill: str = None,
    mentioned_agents: list = None,
    mentioned_tools: list = None,
    mentioned_skills: list = None,
    has_images: bool = False,
    has_code: bool = False,
    agent_registry = None,  # NEW: For showing agent details
) -> str:
    """Build dynamic system reminder based on context.

    Args:
        active_skill: Currently activated skill name
        mentioned_agents: List of @mentioned agents (for handoff)
        mentioned_tools: List of @mentioned tools (already loaded into visible_tools)
        mentioned_skills: List of @mentioned skills (need to read SKILL.md)
        has_images: Whether user input contains images
        has_code: Whether user input contains code blocks
        agent_registry: AgentRegistry for showing detailed agent info

    Returns:
        Dynamic reminder string to be injected into system prompt
    """
    reminders = []

    if active_skill:
        reminders.append(f"<system_reminder>当前激活的技能：{active_skill}。优先使用该技能的工具完成任务。</system_reminder>")

    # Legacy support: if mentioned_agents is provided but not separated by type
    if mentioned_agents and not mentioned_tools and not mentioned_skills:
        agents_str = "、".join(mentioned_agents)
        reminders.append(f"<system_reminder>用户提到了：{agents_str}。这些是用户希望使用的工具、技能或代理。</system_reminder>")

    # New: separated by type
    if mentioned_tools:
        tools_str = "、".join(mentioned_tools)
        reminders.append(f"<system_reminder>用户提到了工具：{tools_str}。请优先使用这些工具完成任务。</system_reminder>")

    if mentioned_skills:
        skills_str = "、".join(mentioned_skills)
        reminders.append(f"<system_reminder>用户提到了技能：{skills_str}。请先使用 Read 工具读取对应的 SKILL.md 文件（位于 skills/{'{skill_id}'}/SKILL.md），然后根据文档指导执行操作。</system_reminder>")

    # NEW: Show detailed agent info when @mentioned (Handoff Pattern)
    if mentioned_agents and agent_registry:
        agent_details = []
        for agent_id in mentioned_agents:
            card = agent_registry.get(agent_id)
            if card:
                # Show detailed agent card
                agent_details.append(card.get_catalog_text())

        if agent_details:
            agents_catalog = "\n\n".join(agent_details)
            reminders.append(f"<system_reminder>用户提到了以下 agents，你可以使用 transfer_to_{{agent_id}} 工具将任务完全移交给该 agent 处理：\n\n{agents_catalog}\n</system_reminder>")
    elif mentioned_agents:
        # Fallback: no agent_registry
        agents_str = "、".join(mentioned_agents)
        reminders.append(f"<system_reminder>用户提到了 agents：{agents_str}。</system_reminder>")

    # if has_images:
    #     reminders.append("<system_reminder>用户分享了图片。使用 vision 能力理解图片内容。</system_reminder>")

    # DISABLED: Code detection is too broad and not reliable
    # if has_code:
    #     reminders.append("<system_reminder>用户输入包含代码。使用代码分析能力处理。</system_reminder>")

    return "\n\n".join(reminders) if reminders else ""
