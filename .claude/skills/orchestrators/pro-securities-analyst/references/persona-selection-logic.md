# Persona Selection Logic

## Overview

This reference defines how `pro-securities-analyst` automatically selects 2–3 investor personas from the 14-persona panel for any given stock. The goal is to maximize analytical depth without creating incoherent debates.

## Step 1: Classify the Stock Type

Use data from `openbb-data-fetcher` output to classify the stock into one primary type.

### Classification Rules

| Stock Type | Classification Criteria |
|------------|------------------------|
| **GROWTH** | Revenue CAGR (3Y) > 20% AND P/E > 30 (or loss-making with high revenue growth) |
| **VALUE** | P/B < 2 AND FCF yield > 4% AND revenue growth < 10% |
| **GARP** | Revenue CAGR 10–20% AND P/E 15–30 (Growth at Reasonable Price) |
| **MACRO** | Sector is Financials, Energy, Materials, Utilities, or REITs — highly rate/commodity sensitive |
| **MOMENTUM** | Stock up > 30% in trailing 6M AND trading near 52W high AND relative strength vs index > 1.2 |
| **EVENT** | Recent M&A announcement, spin-off, activist entry, IPO < 12M, or major regulatory change flagged in Deal Radar |
| **DISTRESSED** | P/B < 0.8 OR debt/EBITDA > 5 OR recent credit downgrade OR cash runway < 12M |

**Tie-breaking rule**: If a stock qualifies for multiple types, prioritize in this order: EVENT > DISTRESSED > MACRO > MOMENTUM > GROWTH > GARP > VALUE.

**Korean market override**: For KOSPI/KOSDAQ stocks, add "KR" tag. Korean conglomerates (Samsung, LG, SK) default to GARP unless classified as MACRO or EVENT.

---

## Step 2: Select Personas Using the Matrix

Select 2–3 personas. Always include one **Valuation Anchor** persona and one **Contrarian/Risk** persona.

### Full Selection Matrix (14 Personas)

| Stock Type | Primary (1) | Secondary (2) | Optional (3 — add for depth) |
|------------|-------------|----------------|-------------------------------|
| **GROWTH** | Cathie Wood | Peter Lynch | Phil Fisher |
| **VALUE** | Warren Buffett | Ben Graham | Mohnish Pabrai |
| **GARP** | Peter Lynch | Aswath Damodaran | Charlie Munger |
| **MACRO** | Stanley Druckenmiller | Nassim Taleb | Aswath Damodaran |
| **MOMENTUM** | Jesse Livermore | Stanley Druckenmiller | Peter Lynch |
| **EVENT** | Bill Ackman | Aswath Damodaran | Michael Burry |
| **DISTRESSED** | Michael Burry | Ben Graham | Nassim Taleb |
| **KR (Korean)** | Rakesh Jhunjhunwala | + type-based secondary | Aswath Damodaran |

### Persona Role Descriptions

| Persona | Primary Lens | Best Used For |
|---------|-------------|---------------|
| Warren Buffett | Moat, management, intrinsic value | Quality value stocks |
| Charlie Munger | Mental models, quality over price | Quality businesses at fair price |
| Ben Graham | Net-net, margin of safety, balance sheet | Deep value, distressed |
| Phil Fisher | Scuttlebutt, qualitative growth quality | Growth with durable moat |
| Peter Lynch | GARP, everyday business understanding | Mid-cap growth, consumer |
| Cathie Wood | Disruptive innovation, TAM expansion | High-growth tech/biotech |
| Michael Burry | Contrarian, balance sheet forensics | Distressed, short ideas |
| Nassim Taleb | Tail risk, fragility, convexity | Risk assessment, macro hedge |
| Bill Ackman | Activist, concentrated conviction | Event-driven, turnaround |
| Stanley Druckenmiller | Macro, liquidity, asymmetric bets | Macro-sensitive, regime plays |
| Aswath Damodaran | Rigorous valuation, expectation analysis | Any stock needing TP anchor |
| Mohnish Pabrai | Cloning, high-upside value bets | Value with asymmetric upside |
| Rakesh Jhunjhunwala | Asian/emerging market value + growth | Korean, Indian, EM stocks |
| Jesse Livermore | Price action, trend, timing, risk control | Momentum, timing signals |

---

## Step 3: Selection Output Format

After selecting personas, always output this header in the broker report:

```
▶ Persona Panel: [Primary] + [Secondary] (+ [Optional])
  Stock type: [GROWTH/VALUE/GARP/MACRO/MOMENTUM/EVENT/DISTRESSED] [+KR if applicable]
  Selection rationale: [1 sentence explaining why these personas fit this stock]
```

---

## Override Rules

### User-specified overrides

If the user appends a suffix to the ticker, apply the following persona override:

| Suffix | Override |
|--------|---------|
| `+value` | Force VALUE personas: Buffett + Ben Graham (+ Munger) |
| `+growth` | Force GROWTH personas: Cathie Wood + Phil Fisher (+ Lynch) |
| `+momentum` | Force MOMENTUM personas: Livermore + Druckenmiller |
| `+contrarian` | Force DISTRESSED personas: Burry + Graham + Taleb |
| `+macro` | Force MACRO personas: Druckenmiller + Taleb + Damodaran |

### Special cases

- **Biotech/Pre-revenue**: Always include Cathie Wood + Nassim Taleb (tail risk dominant)
- **Chinese ADR**: Add Rakesh Jhunjhunwala as third persona (EM expertise)
- **Crypto-adjacent equity**: Cathie Wood (primary) + Nassim Taleb (risk)
- **Turnaround story**: Bill Ackman (primary) + Michael Burry (forensics)
- **Dividend/income stock**: Buffett (primary) + Damodaran (yield valuation)

---

## Debate Synthesis Rules

After running each selected persona:

1. **Identify consensus**: If 2 of 2 or 2 of 3 personas share the same BUY/HOLD/SELL stance → consensus
2. **Identify split verdict**: If personas are evenly divided → present both sides, note the split
3. **Identify the swing factor**: What key variable causes the disagreement? Name it explicitly
4. **Livermore veto rule**: If Jesse Livermore's stance is AVOID or SELL due to broken price action, note it as a timing warning even if fundamental personas are BUY
5. **Taleb tail-risk caveat**: If Nassim Taleb flags HIGH tail risk, include it as a mandatory risk bullet regardless of consensus

---

## Confidence Calibration

Adjust overall report confidence based on persona agreement:

| Agreement | Confidence |
|-----------|-----------|
| All personas agree, strong rationale | HIGH |
| 2 of 3 agree, clear majority | MEDIUM-HIGH |
| Split verdict with meaningful swing factor | MEDIUM |
| All personas uncertain or conflicted | LOW |
| Data quality poor (partial analysis mode) | LOW regardless of persona stances |
