"""Claude API → pro-securities-analyst pipeline adapter."""
from __future__ import annotations

import logging

import anthropic

from src.application.ports.analyst_port import AnalystPort, AnalystRequest
from src.infrastructure.claude.skill_bundle import SkillPromptBundleBuilder

logger = logging.getLogger(__name__)

_FALLBACK_PROMPT = """\
You are a 20-year veteran global securities analyst.

Execute the full 7-step analysis pipeline for the given ticker and output a
single valid JSON object.

Required fields: investment_opinion, confidence, target_price, current_price,
investment_thesis, risks, catalysts, markdown_report.

Do not ask clarifying questions. Start immediately.\
"""


class ClaudeAnalystAdapter(AnalystPort):
    """Claude API를 통해 pro-securities-analyst 파이프라인 실행."""

    MODEL = "claude-sonnet-4-6"
    MAX_TOKENS = 8192

    def __init__(
        self,
        api_key: str,
        prompt_builder: SkillPromptBundleBuilder | None = None,
    ) -> None:
        self._client = anthropic.AsyncAnthropic(api_key=api_key)
        self._prompt_builder = prompt_builder or SkillPromptBundleBuilder()

    async def analyze(self, request: AnalystRequest) -> str:
        """pro-securities-analyst 7-step 파이프라인 실행 → JSON 리포트 반환."""
        logger.info("Running pro-securities-analyst for %s", request.ticker)
        system_prompt = self._build_system_prompt(request)
        user_prompt = self._build_user_prompt(request)

        message = await self._client.messages.create(
            model=self.MODEL,
            max_tokens=self.MAX_TOKENS,
            system=system_prompt,
            messages=[{"role": "user", "content": user_prompt}],
        )

        report: str = message.content[0].text
        logger.info("Analysis complete for %s — %d chars", request.ticker, len(report))
        return report

    def _build_system_prompt(self, request: AnalystRequest) -> str:
        try:
            return self._prompt_builder.build(request)
        except Exception:
            logger.exception("Failed to build skill prompt bundle; using fallback prompt")
            return _FALLBACK_PROMPT

    @staticmethod
    def _build_user_prompt(request: AnalystRequest) -> str:
        suffixes: list[str] = []
        if request.force_quant and "+quant" not in request.ticker.lower():
            suffixes.append("+quant")
        if request.include_charts and "+charts" not in request.ticker.lower():
            suffixes.append("+charts")

        lines = [
            f"Analyze {request.ticker} {' '.join(suffixes)}".strip(),
            "Generate the complete broker report using the bundled skills.",
            "Return JSON only, matching the Runtime Structured Output Contract.",
        ]

        if request.quant_context:
            lines.extend(
                [
                    "",
                    "Precomputed quant/backtest context:",
                    request.quant_context,
                ]
            )

        return "\n".join(lines)
