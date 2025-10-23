"""Plan schema for decomposition results."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class StepModel(BaseModel):
    """Single executable step."""

    id: str = Field(min_length=1)
    description: str = Field(min_length=1)
    agent: Optional[str] = None
    skill_id: Optional[str] = None
    inputs: Dict[str, Any] = Field(default_factory=dict)
    deliverables: List[str] = Field(default_factory=list)
    success_criteria: Optional[str] = None
    max_calls: int = Field(default=3, ge=1, le=10)


class PlanModel(BaseModel):
    """Structured plan with ordered steps."""

    steps: List[StepModel]


def default_plan() -> PlanModel:
    """Return a conservative fallback plan."""

    return PlanModel(
        steps=[
            StepModel(
                id="step-1",
                description="Perform initial analysis for the request.",
                deliverables=["analysis_notes"],
                success_criteria="analysis_notes is non-empty",
            )
        ]
    )


def plan_for_skill(skill_id: str) -> PlanModel:
    """Return a best-effort plan tailored to a known skill."""

    if skill_id == "weather":
        return PlanModel(
            steps=[
                StepModel(
                    id="weather-1",
                    description="Use the weather skill to fetch current conditions for the requested city.",
                    agent="weather",
                    skill_id="weather",
                    inputs={"city": "auto"},
                    deliverables=["weather_report"],
                    success_criteria="weather_report deliverable returned",
                )
            ]
        )
    return default_plan()
