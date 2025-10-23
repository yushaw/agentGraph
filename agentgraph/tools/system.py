"""Tools that depend on runtime registries."""

from __future__ import annotations

import json
from typing import List

from langchain_core.tools import tool

from agentgraph.skills import SkillRegistry


def build_skill_tools(skill_registry: SkillRegistry) -> List:
    """Create discovery tools bound to the skill registry."""

    @tool
    def list_skills() -> str:
        """List discoverable skills."""

        items = [item.model_dump() for item in skill_registry.list_meta()]
        return json.dumps(items, ensure_ascii=False)

    @tool
    def select_skill(skill_id: str) -> str:
        """Select a skill and surface its metadata."""

        meta = skill_registry.get(skill_id)
        if not meta:
            return json.dumps({"ok": False, "error": f"Unknown skill: {skill_id}"}, ensure_ascii=False)
        payload = {
            "ok": True,
            "skill": {"id": meta.id, "name": meta.name, "version": meta.version},
            "allowed_tools": meta.allowed_tools or [],
            "inputs_schema": meta.inputs_schema or {},
        }
        return json.dumps(payload, ensure_ascii=False)

    @tool
    def create_plan(steps: str) -> str:
        """Create a multi-step execution plan for complex tasks.

        Args:
            steps: JSON string containing an array of step objects. Each step must have:
                - id (str): Unique step identifier
                - description (str): What this step does
                - agent (str, optional): Subagent type (research/writer/generic)
                - skill_id (str, optional): Skill to activate for this step
                - inputs (object): Input parameters for the step
                - deliverables (array): List of expected outputs (e.g., ["outline_json", "file"])
                - success_criteria (str, optional): How to verify success
                - max_calls (int, optional): Max tool calls for this step (default: 3)

        Returns:
            JSON object with {ok: true, plan: {...}} on success, or {ok: false, error: str} on failure.

        Example:
            create_plan('''[
                {
                    "id": "weather-query",
                    "description": "Query Beijing weather",
                    "agent": "research",
                    "deliverables": ["weather_report"],
                    "inputs": {"city": "Beijing"}
                },
                {
                    "id": "generate-ppt",
                    "description": "Generate weather report PPT",
                    "agent": "writer",
                    "skill_id": "pptx",
                    "deliverables": ["file"],
                    "inputs": {"weather_data": "from_previous_step"}
                }
            ]''')
        """
        try:
            steps_list = json.loads(steps)
            if not isinstance(steps_list, list):
                return json.dumps({"ok": False, "error": "steps must be a JSON array"}, ensure_ascii=False)

            # Validate each step has required fields
            for i, step in enumerate(steps_list):
                if not isinstance(step, dict):
                    return json.dumps({"ok": False, "error": f"Step {i} must be an object"}, ensure_ascii=False)
                if "id" not in step or not step["id"]:
                    return json.dumps({"ok": False, "error": f"Step {i} missing 'id'"}, ensure_ascii=False)
                if "description" not in step or not step["description"]:
                    return json.dumps({"ok": False, "error": f"Step {i} missing 'description'"}, ensure_ascii=False)
                if "deliverables" not in step:
                    return json.dumps({"ok": False, "error": f"Step {i} missing 'deliverables'"}, ensure_ascii=False)

                # Set defaults
                step.setdefault("inputs", {})
                step.setdefault("max_calls", 3)

            plan = {
                "steps": steps_list
            }

            return json.dumps({"ok": True, "plan": plan}, ensure_ascii=False)

        except json.JSONDecodeError as e:
            return json.dumps({"ok": False, "error": f"Invalid JSON: {str(e)}"}, ensure_ascii=False)
        except Exception as e:
            return json.dumps({"ok": False, "error": f"Plan creation failed: {str(e)}"}, ensure_ascii=False)

    return [list_skills, select_skill, create_plan]
