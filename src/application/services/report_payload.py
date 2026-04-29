from __future__ import annotations

import json
import re
from typing import Any


def extract_json_payload(raw_report: str) -> dict[str, Any] | None:
    """Claude 응답에서 JSON 객체를 안전하게 추출한다.

    운영에서는 JSON만 오도록 프롬프트를 강제하지만, 모델이 ```json fenced block```으로
    감싸는 경우가 있어 그 형태까지 허용한다. 실패하면 기존 Markdown 파서가 이어받는다.
    """

    text = raw_report.strip()
    if not text:
        return None

    fenced = re.search(r"```(?:json)?\s*(\{[\s\S]*?\})\s*```", text, re.IGNORECASE)
    if fenced:
        text = fenced.group(1).strip()

    if not text.startswith("{"):
        start = text.find("{")
        end = text.rfind("}")
        if start < 0 or end <= start:
            return None
        text = text[start : end + 1]

    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        return None

    return payload if isinstance(payload, dict) else None


def parse_price(value: Any) -> float | None:
    """원화/달러 문자열과 숫자 입력을 float로 정규화한다."""

    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if not isinstance(value, str):
        return None

    cleaned = re.sub(r"[^0-9.\-]", "", value)
    if cleaned in {"", "-", ".", "-."}:
        return None
    try:
        return float(cleaned)
    except ValueError:
        return None


def get_nested(payload: dict[str, Any], *keys: str) -> Any:
    """중첩 dict에서 첫 번째로 발견되는 값을 꺼낸다."""

    for key in keys:
        current: Any = payload
        found = True
        for part in key.split("."):
            if not isinstance(current, dict) or part not in current:
                found = False
                break
            current = current[part]
        if found:
            return current
    return None


def normalize_report_markdown(payload: dict[str, Any], fallback: str) -> str:
    """Discord와 DB 저장에 쓸 사람이 읽기 좋은 리포트 본문을 만든다."""

    markdown = payload.get("markdown_report")
    if isinstance(markdown, str) and markdown.strip():
        return markdown.strip()

    ticker = payload.get("ticker") or payload.get("symbol") or "UNKNOWN"
    opinion = payload.get("investment_opinion") or payload.get("signal_type") or "N/A"
    confidence = payload.get("confidence") or "N/A"
    target = payload.get("target_price") or get_nested(payload, "prices.target_price")
    current = payload.get("current_price") or get_nested(payload, "prices.current_price")

    lines = [
        f"# {payload.get('company_name', ticker)} ({ticker})",
        "",
        f"Investment Opinion: {opinion}",
        f"Confidence: {confidence}",
        f"12-Month Target Price: {target if target is not None else 'N/A'}",
        f"Current Price: {current if current is not None else 'N/A'}",
    ]

    thesis = payload.get("investment_thesis")
    if isinstance(thesis, list) and thesis:
        lines.extend(["", "## Investment Thesis"])
        for idx, item in enumerate(thesis[:3], start=1):
            if isinstance(item, dict):
                title = item.get("title", f"Thesis {idx}")
                evidence = item.get("evidence", "")
                lines.append(f"{idx}. {title}")
                if evidence:
                    lines.append(f"   {evidence}")
            else:
                lines.append(f"{idx}. {item}")

    risks = payload.get("risks")
    if isinstance(risks, list) and risks:
        lines.extend(["", "## Risks"])
        lines.extend(f"- {risk}" for risk in risks[:5])

    catalysts = payload.get("catalysts")
    if isinstance(catalysts, list) and catalysts:
        lines.extend(["", "## Catalysts"])
        lines.extend(f"- {catalyst}" for catalyst in catalysts[:4])

    rendered = "\n".join(lines).strip()
    return rendered or fallback
