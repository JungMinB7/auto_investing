# Analysis Pipeline

## Overview

This reference defines the 7-step execution sequence for `pro-securities-analyst`. Each step calls a downstream skill and extracts specific outputs for the next step and the final broker report.

---

## Pre-Step: Input Parsing

Before Step 1, parse the raw user input.

```
Normalize ticker:
  - Strip whitespace, convert to uppercase
  - If 6-digit integer → KOSPI/KOSDAQ, set market=KR
  - If Korean text (유니코드 한국어) → run web search to resolve ticker
  - If company name (English) → resolve to primary exchange ticker

Parse suffixes:
  - "+quant"      → force Step 6 execution
  - "+value"      → persona override (VALUE)
  - "+growth"     → persona override (GROWTH)
  - "+momentum"   → persona override (MOMENTUM)
  - "+contrarian" → persona override (DISTRESSED)
  - "+macro"      → persona override (MACRO)
  - "+brief"      → set output_mode = BRIEF
  - No suffix     → output_mode = STANDARD
```

---

## Step 1: Data Collection (`openbb-data-fetcher`)

**Goal**: Gather raw financial data before any analysis.

**Inputs to pass**:
```
- ticker (normalized)
- market (US/KR/EU/etc.)
- date_range: trailing 4 quarters + 3-year CAGR data
```

**Data to collect** (in this order):
1. Price data: current price, 52W high/low, 6M return, volume trend
2. Fundamentals: revenue (4Q), net income (4Q), FCF (4Q), total debt, cash
3. Valuation: P/E, P/B, EV/EBITDA, FCF yield, dividend yield
4. Analyst consensus: mean TP, # of buys/holds/sells (if available)
5. News: most recent 10 headlines (for Deal Radar check)
6. Sector and index: what index the stock belongs to, sector classification

**Failure handling**:
- If OpenBB returns no data → attempt `pip install openbb` and retry once
- If still failing → activate `PARTIAL_ANALYSIS` mode
  - Set flag: `data_quality = "web-fallback"`
  - Use web search for price, market cap, sector, recent news
  - Tag all values: `[Estimated-webfallback]`
- For Korean stocks (market=KR) failing OpenBB → try DART/네이버금융 as web fallback

**Stock type signals extracted** (passed to Step 4):
```
- revenue_growth_cagr_3y
- pe_ratio
- pb_ratio
- fcf_yield
- sector
- country_exchange
- recent_news_flags  ← from Deal Radar headlines
- price_momentum_6m
```

---

## Step 2: Company Analysis (`company-analysis`)

**Goal**: Establish the valuation anchor and core business judgment.

**Context to provide**:
- Pass Step 1 data as context
- State: "Run full company-analysis workflow: Narrative → Reverse DCF → Forward DCF → Comps → So What"

**Key outputs to extract** for the report:
```
- narrative: string            (what the market is pricing in)
- implied_growth_rate: float   (Reverse DCF result)
- fair_value_range: [low, high]
- expectation_gap: string      (overvalued / undervalued / fairly priced + magnitude)
- so_what: string              (core investment conclusion from company-analysis)
```

**Special case — Private company**:
- Skip Reverse DCF (no market price)
- Focus on: business model quality, revenue trajectory, funding history
- Tag fair_value_range as `[Assumption]`

**Special case — Korean stock (market=KR)**:
- Add K-IFRS accounting note: "Financial statements prepared under K-IFRS"
- Reference DART filings if available
- Note: "Foreign investor ownership: [X]%, Institutional ownership: [Y]%" if data available

---

## Step 3: Market Context (`traditional-market-analysis`)

**Goal**: Assess whether the market backdrop supports or undermines the investment case.

**Context to provide**:
- Pass Step 2 narrative and sector as context
- Ask for: regime diagnosis → cycle position → liquidity/policy transmission → asymmetry → backdrop verdict

**Key outputs to extract**:
```
- regime: string               (risk-on/off, tightening/easing, etc.)
- cycle_position: string       (early/mid/late/contraction)
- backdrop_verdict: string     ("강화" / "약화" / "중립" / "무효화")
- key_transmission: string     (how rates/liquidity are affecting this stock's sector)
- asymmetry_note: string       (upside vs downside asymmetry given current positioning)
```

---

## Step 4: Persona Selection

**Goal**: Classify the stock type and select 2–3 personas.

**Process**:
1. Apply classification rules from `references/persona-selection-logic.md` using Step 1 stock_type_signals
2. Check for user-specified overrides (from suffix parsing)
3. Check for special cases (biotech, Chinese ADR, Korean stock, etc.)
4. Output: `stock_type`, `selected_personas` list with selection rationale

---

## Step 5: Persona Panel (`investor-personas/*`)

**Goal**: Get each selected persona's investment stance.

**For each selected persona**:
- Provide: Step 2 (company analysis summary) + Step 3 (market context summary) + Step 1 key metrics
- Request: stance (BUY/HOLD/SELL), rationale (2–3 sentences), conviction level (HIGH/MEDIUM/LOW)
- Run personas sequentially; pass prior persona stances to each subsequent persona for debate framing

**Synthesis** (after all personas run):
1. Count stances: BUY / HOLD / SELL
2. Determine consensus or split verdict (per persona-selection-logic.md debate synthesis rules)
3. Identify swing factor if split
4. Apply Livermore veto rule if Livermore is in panel and says AVOID/SELL
5. Apply Taleb tail-risk caveat if Taleb is in panel

**Output**:
```
- persona_stances: list (name, stance, rationale, conviction)
- consensus_verdict: BUY | HOLD | SELL
- confidence: HIGH | MEDIUM-HIGH | MEDIUM | LOW
- minority_view: string (if applicable)
- swing_factor: string (if split)
```

---

## Step 6: Quantitative Signals (`quant-research`) — Conditional

**Trigger conditions** (run Step 6 when any is true):
- User used `+quant` suffix
- Stock type is MOMENTUM
- Stock type is GROWTH with high momentum signal (price_momentum_6m > 30%)
- Livermore is in persona panel (always pair with quant signals)

**Context to provide**:
- Price momentum data from Step 1
- Ask for: momentum factor signal, relative strength vs index, factor exposure, short-term timing note

**Output**:
```
- momentum_signal: POSITIVE | NEUTRAL | NEGATIVE
- factor_exposure: string
- timing_note: string    (entry timing guidance — "extended, wait for pullback" vs "breakout confirmed")
```

**If Step 6 is skipped**: Note "Quant signals: N/A" in the report.

---

## Step 7: Broker Report Synthesis

**Goal**: Integrate all step outputs into the final broker report.

**Assembly sequence**:
1. Header block (ticker, date, consensus verdict, TP calculation)
2. Investment Thesis (3 core arguments — extract from company analysis + persona consensus)
3. Valuation section (Reverse DCF result + fair value range + expectation gap)
4. Market Context (regime + backdrop verdict + key transmission)
5. Persona Panel table
6. Quant Signals (if Step 6 ran)
7. Risks (combine: company-analysis risks + Taleb tail risks + Livermore invalidation point)
8. Catalysts (from company-analysis "So What" + Deal Radar news)
9. Disclaimer

**TP Calculation rule**:
- Primary: midpoint of fair_value_range from Forward DCF
- If DCF not available: use analyst consensus TP `[Estimated]` or sector P/E × forward EPS `[Assumption]`
- Always tag TP with data quality tag

**Output format**: Follow `references/broker-report-contract.md` exactly.

---

## Routing for Special Situations

| Situation | Routing Change |
|-----------|----------------|
| Stock not yet listed (pre-IPO) | Skip Step 1 price data, focus on funding history + revenue |
| ETF / index | Skip company-analysis, use market-analysis as primary; note "ETF — no single-company analysis" |
| Crypto (indirect exposure via equity) | Add Taleb mandatory, add Cathie Wood; note cryptocurrency exposure prominently |
| Korean holding company (지주사) | Add SOTP note in valuation; discount holdings for conglomerate discount |
| Mega-cap (market cap > $500B USD) | Note liquidity premium in valuation; Buffett/Munger more relevant |

---

## Partial Analysis Mode Behavior

When `PARTIAL_ANALYSIS` flag is set (Step 1 data unavailable):

```
Insert at top of report:
══════════════════════════════════════════
 ⚠ DATA LIMITATION
 OpenBB data unavailable. Analysis based on web-sourced data.
 All figures tagged [Estimated-webfallback].
 Confidence: LOW regardless of other signals.
 Recommend verifying key figures via Bloomberg, CapIQ, or official filings.
══════════════════════════════════════════
```

- Continue all steps with available data
- Reduce persona count to 2 (drop optional third)
- Set overall confidence = LOW
- Skip Step 6 unless user explicitly requested `+quant`
