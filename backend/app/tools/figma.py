"""Figma tool: read a design file so the model can turn it into code.

Needs FIGMA_TOKEN (a personal access token from Figma settings).
"""

import json
import re

import httpx
from langchain_core.tools import tool
from pydantic import BaseModel, Field

from app.core.config import EXTERNAL_API_TIMEOUT_SECONDS, FIGMA_API_URL, FIGMA_TOKEN


_FILE_KEY = re.compile(r"figma\.com/(?:file|design|proto|board)/([A-Za-z0-9]+)")
_NODE_ID = re.compile(r"[?&]node-id=([0-9]+[-:][0-9]+)")
_MAX_NODES = 220


def parse_figma_reference(reference: str) -> tuple[str, str | None]:
    reference = reference.strip()
    match = _FILE_KEY.search(reference)
    key = match.group(1) if match else reference
    if not re.fullmatch(r"[A-Za-z0-9]{10,}", key):
        raise ValueError("Give a Figma file URL or file key.")
    node = _NODE_ID.search(reference)
    return key, node.group(1).replace("-", ":") if node else None


def _color(paint: dict) -> str | None:
    if paint.get("type") != "SOLID" or paint.get("visible") is False:
        return None
    c = paint.get("color") or {}
    alpha = paint.get("opacity", c.get("a", 1))
    rgb = "#{:02x}{:02x}{:02x}".format(
        round(c.get("r", 0) * 255), round(c.get("g", 0) * 255), round(c.get("b", 0) * 255)
    )
    return rgb if alpha >= 0.999 else f"{rgb} @ {alpha:.2f}"


def _summarize(node: dict, depth: int, budget: list[int], lines: list[str]):
    if budget[0] <= 0 or node.get("visible") is False:
        return
    budget[0] -= 1

    parts = [f"{'  ' * depth}- {node.get('type')} \"{node.get('name', '')}\""]
    box = node.get("absoluteBoundingBox") or {}
    if box:
        parts.append(f"{round(box.get('width', 0))}x{round(box.get('height', 0))}")
    if node.get("layoutMode") in ("HORIZONTAL", "VERTICAL"):
        parts.append(
            f"flex-{'row' if node['layoutMode'] == 'HORIZONTAL' else 'col'}"
            f" gap={node.get('itemSpacing', 0)}"
            f" pad={node.get('paddingTop', 0)},{node.get('paddingRight', 0)},"
            f"{node.get('paddingBottom', 0)},{node.get('paddingLeft', 0)}"
        )
    fills = [c for c in (_color(p) for p in node.get("fills", []) or []) if c]
    if fills:
        parts.append("fill=" + ",".join(fills))
    strokes = [c for c in (_color(p) for p in node.get("strokes", []) or []) if c]
    if strokes:
        parts.append(f"border={node.get('strokeWeight', 1)}px {strokes[0]}")
    if node.get("cornerRadius"):
        parts.append(f"radius={node['cornerRadius']}")
    if node.get("type") == "TEXT":
        style = node.get("style") or {}
        parts.append(
            f"font={style.get('fontFamily')} {style.get('fontWeight')} {style.get('fontSize')}px"
        )
        parts.append(f"text={json.dumps((node.get('characters') or '')[:160], ensure_ascii=False)}")
    lines.append(" ".join(parts))

    for child in node.get("children", []) or []:
        _summarize(child, depth + 1, budget, lines)


class FigmaInput(BaseModel):
    file: str = Field(description="Figma file URL (may include ?node-id=) or file key.")


@tool(args_schema=FigmaInput)
def figma_get_design(file: str) -> str:
    """Read a Figma design (frames, layout, colours, typography, text) to turn it into code."""
    if not FIGMA_TOKEN:
        return "Figma is not configured. Add FIGMA_TOKEN (a personal access token) to backend/.env."

    try:
        key, node_id = parse_figma_reference(file)
    except ValueError as exc:
        return str(exc)

    headers = {"X-Figma-Token": FIGMA_TOKEN}
    timeout = max(EXTERNAL_API_TIMEOUT_SECONDS, 30.0)
    try:
        if node_id:
            response = httpx.get(
                f"{FIGMA_API_URL}/files/{key}/nodes",
                params={"ids": node_id, "depth": 6},
                headers=headers,
                timeout=timeout,
            )
            response.raise_for_status()
            data = response.json()
            roots = [n["document"] for n in data.get("nodes", {}).values() if n and n.get("document")]
            title = data.get("name")
        else:
            response = httpx.get(
                f"{FIGMA_API_URL}/files/{key}",
                params={"depth": 4},
                headers=headers,
                timeout=timeout,
            )
            response.raise_for_status()
            data = response.json()
            roots = data.get("document", {}).get("children", [])
            title = data.get("name")

        preview = None
        target = node_id or next(
            (frame.get("id") for page in roots for frame in page.get("children", []) or []),
            None,
        )
        if target:
            images = httpx.get(
                f"{FIGMA_API_URL}/images/{key}",
                params={"ids": target, "format": "png", "scale": 1},
                headers=headers,
                timeout=timeout,
            )
            if images.is_success:
                preview = (images.json().get("images") or {}).get(target)
    except httpx.HTTPStatusError as exc:
        status = exc.response.status_code
        if status in (403, 404):
            return f"Figma refused access ({status}). Check the URL and that the token can open this file."
        return f"Figma request failed ({status})."
    except httpx.HTTPError as exc:
        return f"Figma request failed: {exc}"

    lines: list[str] = []
    budget = [_MAX_NODES]
    for root in roots:
        _summarize(root, 0, budget, lines)

    header = f"Figma file: {title} (key {key})"
    if preview:
        header += f"\nPreview image: {preview}"
    if budget[0] <= 0:
        lines.append("… (design truncated; pass a URL with ?node-id= for one frame)")
    return header + "\n" + "\n".join(lines)


figma_tools = [figma_get_design]
