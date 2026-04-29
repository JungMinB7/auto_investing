from __future__ import annotations

import logging
import re
from pathlib import Path

from src.application.ports.analyst_port import AnalystRequest

logger = logging.getLogger(__name__)

_PROJECT_ROOT = Path(__file__).resolve().parents[3]
_SKILLS_ROOT = _PROJECT_ROOT / ".claude" / "skills"
_ORCHESTRATOR_ROOT = _SKILLS_ROOT / "orchestrators" / "pro-securities-analyst"

_CORE_SKILLS = [
    _SKILLS_ROOT / "fundamental-analysis" / "company-analysis" / "SKILL.md",
    _SKILLS_ROOT / "market-analysis" / "traditional-market-analysis" / "SKILL.md",
]

_QUANT_SKILL = _SKILLS_ROOT / "quantitative-analysis" / "quant-research" / "SKILL.md"
_FINANCIAL_REPORT_SKILL = _SKILLS_ROOT / "output-formats" / "financial-report" / "SKILL.md"
_PERSONA_ROOT = _SKILLS_ROOT / "investor-personas"

_PERSONA_OVERRIDES = {
    "+value": ["warren-buffett", "ben-graham", "charlie-munger"],
    "+growth": ["cathie-wood", "phil-fisher", "peter-lynch"],
    "+momentum": ["jesse-livermore", "stanley-druckenmiller", "peter-lynch"],
    "+contrarian": ["michael-burry", "ben-graham", "nassim-taleb"],
    "+macro": ["stanley-druckenmiller", "nassim-taleb", "aswath-damodaran"],
}

_JSON_OUTPUT_CONTRACT = """
---
## Runtime Structured Output Contract

Return exactly one valid JSON object. Do not wrap it in Markdown fences and do not
write prose outside the JSON.

Required JSON shape:
{
  "ticker": "string",
  "company_name": "string",
  "exchange": "KRX|NASDAQ|NYSE|...",
  "analysis_date": "YYYY-MM-DD",
  "currency": "KRW|USD|...",
  "investment_opinion": "BUY|HOLD|SELL",
  "confidence": "HIGH|MEDIUM-HIGH|MEDIUM|LOW",
  "target_price": 0,
  "current_price": 0,
  "upside_pct": 0,
  "data_quality": "full|partial|web-fallback|unavailable",
  "data_limitations": ["string"],
  "persona_panel": {
    "stock_type": "GROWTH|VALUE|GARP|MACRO|MOMENTUM|EVENT|DISTRESSED|KR",
    "selected": [
      {
        "name": "string",
        "stance": "BUY|HOLD|SELL",
        "conviction": "HIGH|MEDIUM|LOW",
        "rationale": "string"
      }
    ],
    "selection_rationale": "string",
    "consensus": "BUY|HOLD|SELL",
    "minority_view": "string",
    "swing_factor": "string"
  },
  "investment_thesis": [
    {
      "title": "string",
      "evidence": "string",
      "data_tags": [
        "[Actual]|[Estimated]|[Assumption]|[Consensus]|[Estimated-webfallback]|[Unavailable]"
      ]
    }
  ],
  "valuation": {
    "current_price_implies": "string",
    "fair_value_range": {
      "low": 0,
      "high": 0,
      "tag": "[DCF-derived]|[Comps-derived]|[Consensus]|[Assumption]"
    },
    "method": "string",
    "key_assumptions": ["string"],
    "expectation_gap": "string"
  },
  "market_context": {
    "regime": "string",
    "cycle_position": "string",
    "backdrop_verdict": "강화|약화|중립|무효화",
    "key_transmission": "string",
    "asymmetry": "string"
  },
  "quant_signals": {
    "status": "RUN|N/A|UNAVAILABLE",
    "momentum_signal": "POSITIVE|NEUTRAL|NEGATIVE|N/A",
    "factor_exposure": "string",
    "timing_note": "string",
    "backtest_summary": "string"
  },
  "risks": ["string"],
  "catalysts": ["string"],
  "chart_package": {
    "requested": false,
    "exhibits": [{"title": "string", "chart_type": "line|bar|ohlcv|table", "reason": "string"}]
  },
  "markdown_report": "A complete human-readable broker report in Markdown, suitable for Discord."
}

Rules:
- The four parser fields must be present exactly:
  investment_opinion, confidence, target_price, current_price.
- Use null for unavailable numeric values. Do not fabricate values.
- If +charts is present, set chart_package.requested=true and apply the
  financial-report skill's chart playbook conceptually.
- If quant context is provided, incorporate it into quant_signals.backtest_summary;
  otherwise do not invent backtest results.
"""


class SkillPromptBundleBuilder:
    """Claude system prompt에 필요한 스킬 원문을 조립한다.

    Claude Skills 런타임이 별도로 존재하지 않는 API 환경에서는, 필요한 SKILL.md를
    system prompt에 직접 포함해야 하위 스킬의 판단 기준이 실제 분석에 반영된다.
    """

    def build(self, request: AnalystRequest) -> str:
        parts: list[str] = []
        parts.extend(self._orchestrator_parts())
        parts.extend(self._skill_parts("Core downstream skill", _CORE_SKILLS))

        if request.force_quant or request.quant_context:
            parts.extend(self._skill_parts("Conditional downstream skill", [_QUANT_SKILL]))

        if request.include_charts:
            parts.extend(self._skill_parts("+charts output skill", [_FINANCIAL_REPORT_SKILL]))

        persona_paths = self._persona_paths(request)
        parts.extend(self._skill_parts("Investor persona skill", persona_paths))
        parts.append(_JSON_OUTPUT_CONTRACT)

        prompt = "\n\n".join(part for part in parts if part.strip())
        logger.info("Built Claude skill prompt bundle: %d chars", len(prompt))
        return prompt

    def _orchestrator_parts(self) -> list[str]:
        parts: list[str] = []
        skill_md = _ORCHESTRATOR_ROOT / "SKILL.md"
        parts.append(self._read_section("Orchestrator: pro-securities-analyst/SKILL.md", skill_md))
        refs_dir = _ORCHESTRATOR_ROOT / "references"
        for ref_file in sorted(refs_dir.glob("*.md")):
            parts.append(self._read_section(f"Orchestrator reference: {ref_file.name}", ref_file))
        return parts

    def _skill_parts(self, label: str, paths: list[Path]) -> list[str]:
        return [
            self._read_section(f"{label}: {path.relative_to(_PROJECT_ROOT)}", path)
            for path in paths
        ]

    def _persona_paths(self, request: AnalystRequest) -> list[Path]:
        names = self._selected_persona_names(request)
        if names is None:
            # 종목 유형은 데이터 수집 후 확정되므로, 명시 오버라이드가 없으면 후보 전체를 제공한다.
            # 오케스트레이터는 persona-selection-logic에 따라 최종 2~3개만 사용해야 한다.
            return sorted(_PERSONA_ROOT.glob("*/SKILL.md"))
        return [_PERSONA_ROOT / name / "SKILL.md" for name in names]

    def _selected_persona_names(self, request: AnalystRequest) -> list[str] | None:
        raw = request.ticker.lower()
        for suffix, names in _PERSONA_OVERRIDES.items():
            if suffix in raw:
                return names

        ticker_only = raw.split()[0].strip()
        if re.fullmatch(r"\d{6}", ticker_only) or re.search(r"[가-힣]", raw):
            return ["rakesh-jhunjhunwala", "aswath-damodaran", "peter-lynch"]

        if request.force_quant:
            return ["jesse-livermore", "stanley-druckenmiller", "aswath-damodaran"]

        return None

    @staticmethod
    def _read_section(title: str, path: Path) -> str:
        if not path.exists():
            logger.warning("Skill prompt file missing: %s", path)
            return f"---\n## {title}\n\n[Unavailable: {path}]"
        return f"---\n## {title}\n\n{path.read_text(encoding='utf-8')}"
