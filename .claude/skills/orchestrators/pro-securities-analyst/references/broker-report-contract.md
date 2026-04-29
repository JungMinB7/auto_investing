# Broker Report Contract

## Overview

This reference defines the exact output structure for every `pro-securities-analyst` report. All sections are mandatory unless marked optional. Deviate from this structure only when a section is genuinely inapplicable (state why).

---

## Output Modes

| Mode | Trigger | Sections Included |
|------|---------|-------------------|
| **STANDARD** | Default | All 9 sections |
| **BRIEF** | `+brief` suffix | Header + Investment Thesis + Risks only |
| **EXTENDED** | `+quant` suffix | All 9 sections + expanded Quant Signals |

---

## Section Definitions

### Section 0: Report Header

**Max length**: 7 lines  
**Required fields**:

```
═══════════════════════════════════════════════════════
 [Company Name] ([TICKER]) — [Exchange: NYSE/NASDAQ/KRX/etc.]
 Analysis Date: [YYYY-MM-DD]
 Investment Opinion: [BUY / HOLD / SELL]
 12-Month Target Price: [Currency + Value]  [data tag]
 Current Price: [Currency + Value]          [data tag]
 Upside/Downside: [+/-XX%]
 Confidence: [HIGH / MEDIUM-HIGH / MEDIUM / LOW]

 ▶ Persona Panel: [Primary] + [Secondary] (+ [Optional])
   Stock type: [GROWTH/VALUE/GARP/MACRO/MOMENTUM/EVENT/DISTRESSED]
   Selection rationale: [1 sentence]
═══════════════════════════════════════════════════════
```

**Rules**:
- Target Price must include a data tag: `[DCF-derived]`, `[Comps-derived]`, `[Consensus]`, or `[Assumption]`
- Upside/Downside is calculated as `(TP − current_price) / current_price × 100`
- If TP cannot be calculated reliably → state "TP: N/A — insufficient data" rather than fabricating

---

### Section 1: Investment Thesis

**Max length**: 3 arguments × 3 lines each = 9 lines total  
**Format**:

```
## Investment Thesis

1. [Argument title — 5–8 words]
   [Supporting evidence — 2–3 lines. Include data tags.]
   
2. [Argument title]
   [Supporting evidence]

3. [Argument title]
   [Supporting evidence]
```

**Rules**:
- Arguments must be specific and evidence-backed, not generic statements
- "Strong management" alone is not an argument — requires evidence
- Each argument must reference at least one data point from Steps 1–5
- Arguments should represent the consensus view from the persona panel

---

### Section 2: Valuation

**Max length**: 12 lines  
**Required content**:

```
## Valuation

Current Price Implies: [Reverse DCF result — implied growth rate and margin]
  → [Judgment: is this realistic or stretched relative to operating history?]

Fair Value Estimate:
  Base case: [Currency + value range]  [data tag]
  Method: [DCF / Comps / P/E-based — specify which was used]
  Key assumptions: [WACC/discount rate, terminal growth, margin target]

Expectation Gap: [Overvalued by ~X% / Undervalued by ~X% / Fairly priced]
  → [Explanation of what must be true for the current price to be justified]
```

**Rules**:
- Reverse DCF must appear for any listed company with sufficient data
- If DCF is not feasible (e.g., pre-revenue, financials only), use P/B or P/Revenue + state the substitute
- All numerical inputs must carry data tags (`[Actual]`, `[Estimated]`, `[Assumption]`)
- Do not present a point estimate as fact; always give a range

---

### Section 3: Market Context

**Max length**: 7 lines

```
## Market Context

Regime: [Risk-on/off, tightening/easing, reflation/disinflation, etc.]
Cycle Position: [Early/Mid/Late/Contraction]
Backdrop Verdict: [강화 / 약화 / 중립 / 무효화]

Key transmission: [How current rates/liquidity/policy affects this stock's sector]
Asymmetry: [Whether upside or downside is more asymmetric given current positioning]
```

---

### Section 4: Persona Panel

**Max length**: Persona count × 3 lines + 3 lines for synthesis

```
## Persona Panel

| Persona | Stance | Conviction | Core Rationale |
|---------|--------|:----------:|----------------|
| [Name]  | BUY    | HIGH       | [1–2 line summary] |
| [Name]  | HOLD   | MEDIUM     | [1–2 line summary] |
| [Name]  | SELL   | LOW        | [1–2 line summary] |

Consensus: [BUY/HOLD/SELL] — [N of M personas agree]
[If split] Swing factor: [The key variable causing disagreement]
[If applicable] Minority view: [Summarize the dissenting argument in 1 sentence]
[If Livermore is in panel and says AVOID] ⚠ Timing warning: price action not confirmed
[If Taleb is in panel] ⚠ Tail risk: [Taleb's specific tail concern]
```

---

### Section 5: Quant Signals (Optional — always present if Step 6 ran)

**Max length**: 5 lines

```
## Quant Signals

Momentum Signal: [POSITIVE / NEUTRAL / NEGATIVE]
Factor Exposure: [Description of dominant factors]
Relative Strength: [vs. index — outperforming/underperforming]
Timing Note: [Entry timing guidance — e.g., "Extended, wait for pullback to [support]"]
```

If Step 6 did not run: `## Quant Signals: N/A (use +quant to activate)`

---

### Section 6: Risks

**Max length**: 5 bullets

```
## Risks

- [Risk 1]: [Specific risk with magnitude or trigger condition]
- [Risk 2]: [Specific risk]
- [Risk 3]: [Specific risk]
- [Risk 4 — optional]: [Specific risk]
- [Risk 5 — optional]: [Specific risk]
```

**Rules**:
- Must include at least one downside risk to the investment thesis
- Must include at least one market/macro risk
- If Taleb is in panel: his tail risk argument must appear as a bullet
- If Livermore is in panel: his invalidation price level must appear as a bullet
- No generic "market volatility" bullets unless specific to this stock's situation

---

### Section 7: Catalysts

**Max length**: 4 bullets with timing

```
## Catalysts (12-Month Outlook)

- [Catalyst 1] — [Expected timing: Q3 2026 / H1 2026 / ongoing]
- [Catalyst 2] — [Expected timing]
- [Catalyst 3] — [Expected timing]
- [Catalyst 4 — optional] — [Expected timing]
```

**Rules**:
- Catalysts must be specific events, not generic growth stories
- Must cite source or basis for timing (earnings calendar, pipeline data, regulatory schedule)
- Deal Radar findings (M&A, activism) qualify as catalysts if web-verified
- Timing must be specified; "eventually" or "sometime" is not acceptable

---

### Section 8: Disclaimer

**Fixed text — always append verbatim**:

```
## Disclaimer

This report is for informational purposes only and does not constitute investment advice or a solicitation to buy or sell securities. All investment decisions are the sole responsibility of the investor. Past performance does not guarantee future results. Data sourced from OpenBB, public filings, and web research — accuracy is not guaranteed. Verify key figures via official filings or professional financial data services before making investment decisions.
```

---

## Data Tagging Rules

All numerical values in the report must carry one of the following tags:

| Tag | Meaning |
|-----|---------|
| `[Actual]` | Verified from OpenBB, official filing, or cited primary source |
| `[Estimated]` | Reasonable estimate based on disclosed data (e.g., trailing 12M calculation) |
| `[Assumption]` | Modeling input not derived from hard data (e.g., terminal growth rate) |
| `[Consensus]` | Sell-side analyst consensus from data provider |
| `[Estimated-webfallback]` | Web-sourced figure, lower reliability — OpenBB unavailable |
| `[Unavailable]` | Data exists but could not be retrieved |

**Critical rule**: Never use `[Actual]` for a number you cannot cite to a specific source. When in doubt, use `[Estimated]`.

---

## Quality Checklist

Before finalizing output, verify:

- [ ] All 8 sections present (or justified absence noted)
- [ ] Target Price has data tag
- [ ] Persona Panel shows correct stock type and selection rationale
- [ ] Reverse DCF result present for listed stocks
- [ ] At least 3 risks, at least 3 catalysts
- [ ] Livermore timing warning present if Livermore in panel
- [ ] Taleb tail risk present if Taleb in panel
- [ ] Disclaimer appended
- [ ] No `[Actual]` tag on unverified data
- [ ] Partial analysis warning present if PARTIAL_ANALYSIS mode active
