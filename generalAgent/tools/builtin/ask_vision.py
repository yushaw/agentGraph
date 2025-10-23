"""Vision perception tool."""

import json
from typing import Optional
from langchain_core.tools import tool


@tool
def ask_vision(question: str, image_ref: Optional[str] = None, region: Optional[str] = None) -> str:
    """Ask questions about images using vision model (stub implementation).

    NOTE: This is a placeholder. In production, integrate with actual vision model.

    Args:
        question: Question about the image
        image_ref: Reference to image (file path, URL, etc.)
        region: Specific region of image to analyze (optional)

    Returns:
        JSON with vision analysis results

    Example:
        ask_vision("What's in this image?", "image.jpg") -> {
            "answer": "(demo) vision says: What's in this image?",
            "objects": [],
            "ocr": "",
            "model": "vision-omni",
            "image_ref": "image.jpg",
            "region": null
        }

    TODO: Implement actual vision model integration
    """
    payload = {
        "answer": f"(demo) vision says: {question}",
        "objects": [],
        "ocr": "",
        "model": "vision-omni",
        "image_ref": image_ref,
        "region": region,
    }
    return json.dumps(payload, ensure_ascii=False)


__all__ = ["ask_vision"]
