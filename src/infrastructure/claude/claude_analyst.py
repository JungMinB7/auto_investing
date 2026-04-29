"""Claude API → pro-securities-analyst pipeline adapter.

Design Ref: §5.2 ClaudeAnalystAdapter

Loads the full pro-securities-analyst skill definition from
.claude/skills/orchestrators/pro-securities-analyst/ and uses it as the
system prompt, so the same 7-step pipeline, 14-persona matrix, and
broker-report-contract that were PDCA-validated are applied at runtime.
"""
from __future__ import annotations

import logging
from pathlib import Path

import anthropic

from src.application.ports.analyst_port import AnalystPort

logger = logging.getLogger(__name__)

# Project root = 4 levels up from this file (src/infrastructure/claude/claude_analyst.py)
_SKILL_ROOT = Path(__file__).resolve().parents[3] / ".claude" / "skills" / "orchestrators" / "pro-securities-analyst"

_SIGNAL_PARSER_ADDON = """

---
## Signal Parser Requirements (auto-trading integration)

The following fields MUST appear verbatim in your broker report so the automated
signal parser can extract them:

  Investment Opinion: BUY | HOLD | SELL
  Confidence: HIGH | MEDIUM-HIGH | MEDIUM | LOW
  12-Month Target Price: ₩XXX,XXX (use ₩ and KRW amounts for KRX 6-digit tickers)
  Current Price: ₩XXX,XXX

Do not omit or rename these fields.
"""

_FALLBACK_PROMPT = """\
You are a 20-year veteran global securities analyst.

Execute the full 7-step analysis pipeline for the given ticker and output a
structured broker report in English Markdown.

REQUIRED fields:
  Investment Opinion: BUY | HOLD | SELL
  Confidence: HIGH | MEDIUM-HIGH | MEDIUM | LOW
  12-Month Target Price: ₩XXX,XXX (KRX) or $XXX (global)
  Current Price: ₩XXX,XXX (KRX) or $XXX (global)

Do not ask clarifying questions. Start immediately.\
"""


def _load_system_prompt() -> str:
    skill_md = _SKILL_ROOT / "SKILL.md"
    refs_dir = _SKILL_ROOT / "references"

    if not skill_md.exists():
        logger.warning("pro-securities-analyst SKILL.md not found at %s — using fallback prompt", skill_md)
        return _FALLBACK_PROMPT

    parts: list[str] = [skill_md.read_text(encoding="utf-8")]

    for ref_file in sorted(refs_dir.glob("*.md")):
        parts.append(f"\n\n---\n## Reference: {ref_file.name}\n\n{ref_file.read_text(encoding='utf-8')}")

    parts.append(_SIGNAL_PARSER_ADDON)

    prompt = "\n".join(parts)
    logger.info(
        "Loaded pro-securities-analyst system prompt from SKILL.md + %d references (%d chars)",
        len(list(refs_dir.glob("*.md"))),
        len(prompt),
    )
    return prompt


_SYSTEM_PROMPT = _load_system_prompt()


class ClaudeAnalystAdapter(AnalystPort):
    """Claude API를 통해 pro-securities-analyst 파이프라인 실행."""

    MODEL = "claude-sonnet-4-6"
    MAX_TOKENS = 8192

    def __init__(self, api_key: str) -> None:
        self._client = anthropic.AsyncAnthropic(api_key=api_key)

    async def analyze(self, ticker: str) -> str:
        """pro-securities-analyst 7-step 파이프라인 실행 → Markdown 브로커 리포트 반환."""
        logger.info("Running pro-securities-analyst for %s", ticker)

        message = await self._client.messages.create(
            model=self.MODEL,
            max_tokens=self.MAX_TOKENS,
            system=_SYSTEM_PROMPT,
            messages=[
                {
                    "role": "user",
                    "content": (
                        f"Analyze {ticker} and generate a complete broker report "
                        "following the pro-securities-analyst pipeline."
                    ),
                }
            ],
        )

        report: str = message.content[0].text
        logger.info("Analysis complete for %s — %d chars", ticker, len(report))
        return report
