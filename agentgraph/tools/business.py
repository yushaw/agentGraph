"""Example domain tools (placeholders to be replaced with production logic)."""

from __future__ import annotations

import json
from typing import Optional

from langchain_core.tools import tool

from agentgraph.skills.weather.toolkit import WeatherError, fetch_weather


@tool
def draft_outline(topic: str, slides: int = 8) -> str:
    """Draft a slide outline for a topic (demo only)."""

    slides = max(1, min(int(slides), 30))
    outline = [f"{topic} — Slide {i + 1}" for i in range(slides)]
    return json.dumps({"topic": topic, "outline": outline}, ensure_ascii=False)


@tool
def generate_pptx(topic: str, outline_json: str) -> str:
    """Simulate PPTX generation (demo; returns fake file path)."""

    return json.dumps({"file": f"/tmp/{topic.replace(' ', '_')}.pptx"}, ensure_ascii=False)


@tool
def http_fetch(url: str) -> str:
    """Fetch an HTML page (stub implementation)."""

    return json.dumps({"url": url, "html": "<html><body>demo</body></html>"}, ensure_ascii=False)


@tool
def extract_links(html: str) -> str:
    """Extract fake links from sample HTML."""

    return json.dumps({"links": ["https://example.com/demo"]}, ensure_ascii=False)


@tool
def ask_vision(question: str, image_ref: Optional[str] = None, region: Optional[str] = None) -> str:
    """Vision perception stub tied to model router (read-only)."""

    payload = {
        "answer": f"(demo) vision says: {question}",
        "objects": [],
        "ocr": "",
        "model": "vision-omni",
        "image_ref": image_ref,
        "region": region,
    }
    return json.dumps(payload, ensure_ascii=False)


@tool
def get_weather(city: str) -> str:
    """Fetch current weather for a city via Open-Meteo."""

    try:
        report = fetch_weather(city)
        return json.dumps({"ok": True, "weather": report.as_dict()}, ensure_ascii=False)
    except WeatherError as exc:
        return json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False)
