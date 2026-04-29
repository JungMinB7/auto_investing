---
template: design
version: 1.3
feature: pro-securities-analyst
date: 2026-04-29
author: JungMinB7
project: auto-investing
status: Draft
planning_doc: docs/01-plan/features/pro-securities-analyst.plan.md
---

# pro-securities-analyst Design Document

> **Summary**: 20년차 글로벌 증권 전문가 오케스트레이터 스킬 — 티커 입력 하나로 7단계 분석 파이프라인을 자동 실행하고 브로커 리포트를 출력
>
> **Project**: auto-investing
> **Author**: JungMinB7
> **Date**: 2026-04-29
> **Status**: Draft
> **Planning Doc**: [pro-securities-analyst.plan.md](../01-plan/features/pro-securities-analyst.plan.md)

---

## Context Anchor

| Key | Value |
|-----|-------|
| **WHY** | 분산된 스킬들을 통합해 브로커 수준 종목 판단을 단일 진입점에서 제공 |
| **WHO** | 개인 투자자, 투자 리서치 보조가 필요한 사용자 (글로벌 주식 시장 전반) |
| **RISK** | 페르소나 자동 선택 로직이 잘못된 페르소나를 고르면 분석 방향이 왜곡될 수 있음 |
| **SUCCESS** | 티커 입력 → 브로커 리포트 (TP + 의견 + 근거3 + 리스크 + 카탈리스트) 완전 자동 생성 |
| **SCOPE** | Phase 1: SKILL.md / Phase 2: 페르소나 선택 로직 ref / Phase 3: 아웃풋 컨트랙트 ref |

---

## 1. Overview

### 1.1 Design Goals

1. **단일 진입점**: 티커 또는 종목명만으로 전체 파이프라인 즉시 실행
2. **적응형 페르소나 패널**: 종목 유형에 따라 가장 적합한 2~3개 페르소나를 자동 선택
3. **일관된 아웃풋 구조**: 어떤 종목이 입력되어도 동일한 6-섹션 브로커 리포트 형식으로 출력
4. **기존 스킬 완전 재사용**: 기존 스킬 파일 수정 없이 오케스트레이션만으로 구현
5. **할루시네이션 방어**: 검증 불가 데이터는 명시적 불확실성 태그 유지

### 1.2 Design Principles

- **오케스트레이터는 얇게**: SKILL.md는 흐름 제어만, 세부 로직은 references/로 위임
- **기존 스킬 output-contract 존중**: 각 하위 스킬의 아웃풋 형식을 그대로 수용한 후 통합
- **Fail Gracefully**: OpenBB 실패 시 partial analysis 모드로 전환, 분석 포기하지 않음
- **투명한 선택 근거**: 페르소나 선택 이유, 데이터 태그, 불확실성을 항상 출력에 포함

---

## 2. Architecture Options

### 2.0 Architecture Comparison

| Criteria | Option A: Minimal | Option B: Clean | Option C: Pragmatic |
|----------|:-:|:-:|:-:|
| **Approach** | SKILL.md 단일 파일 | SKILL.md + 4개 references | SKILL.md + 3개 references |
| **New Files** | 1 | 6 | 5 |
| **Complexity** | Low | High | Medium |
| **Maintainability** | Low | High | **High** |
| **기존 패턴 준수** | No | Over-engineered | **Yes** |
| **Recommendation** | - | - | **Selected** |

**Selected**: Option C — Pragmatic  
**Rationale**: 기존 `company-analysis` (3개 refs), `quant-research` (4개 refs) 패턴과 일치. 과설계 없이 충분한 분리.

### 2.1 Skill Orchestration Diagram

```
사용자 입력: "NVDA 분석해줘" 또는 "005930"
         │
         ▼
┌─────────────────────────────────────────────────┐
│         pro-securities-analyst (SKILL.md)        │
│              20년차 글로벌 증권 전문가              │
├─────────────────────────────────────────────────┤
│                                                 │
│  [Step 1]  openbb-data-fetcher                  │
│            → 가격/재무/뉴스/밸류에이션 데이터       │
│                     │                           │
│  [Step 2]  company-analysis                     │
│            → Narrative + Reverse DCF + Comps    │
│                     │                           │
│  [Step 3]  traditional-market-analysis          │
│            → 레짐 + 사이클 + 기대치 + 비대칭성     │
│                     │                           │
│  [Step 4]  persona-selection-logic (ref)        │
│            → 종목 유형 분류 → 2~3 페르소나 선택    │
│                     │                           │
│  [Step 5]  investor-personas (선택된 페르소나들)  │
│            → 각 페르소나 스탠스 + 핵심 근거        │
│                     │                           │
│  [Step 6]  quant-research (선택적)              │
│            → 모멘텀/팩터 신호 → 타이밍 참고        │
│                     │                           │
│  [Step 7]  브로커 리포트 통합 출력               │
│            → TP + 의견 + 근거3 + 리스크 + 카탈    │
└─────────────────────────────────────────────────┘
```

### 2.2 Data Flow

```
티커 입력
    │
    ▼ [Step 1: 데이터 수집]
OpenBB 원시 데이터 (가격, P/E, Revenue, FCF, 뉴스)
    │
    ▼ [Step 2: 기업 분석]
Narrative + Implied Expectations + Valuation Range
    │
    ▼ [Step 3: 시장 맥락]
Regime + Cycle Position + Liquidity Transmission
    │
    ▼ [Step 4: 종목 유형 분류]
성장주 / 가치주 / 매크로민감주 / 이벤트주 / GARP → 페르소나 2~3개
    │
    ▼ [Step 5: 페르소나 패널]
각 페르소나 스탠스 (BUY/HOLD/SELL) + 핵심 이유 1~2줄
    │
    ▼ [Step 6: 퀀트 신호 (선택)]
모멘텀 팩터 + 포지셔닝 → 진입 타이밍 보조
    │
    ▼ [Step 7: 통합 판단]
컨센서스 의견 + 소수의견 + 브로커 리포트 6섹션 출력
```

### 2.3 Skill Dependencies

| Skill | 호출 시점 | 필수 여부 | 아웃풋 활용처 |
|-------|-----------|:---------:|--------------|
| `openbb-data-fetcher` | Step 1 | 필수 | Step 2, 4에 원시 데이터 공급 |
| `company-analysis` | Step 2 | 필수 | 밸류에이션 앵커 & 기업 판단 |
| `traditional-market-analysis` | Step 3 | 필수 | 시장 백드롭 & 타이밍 맥락 |
| `investor-personas/*` | Step 5 | 필수 (2~3개) | 다각적 투자 스탠스 |
| `quant-research` | Step 6 | 선택 | 단기 타이밍 신호 |
| `financial-report` | Step 7 | 선택 | 차트/시각화 포함 시 |

---

## 3. Skill Interface Contracts

*이 프로젝트는 웹앱이 아닌 스킬 시스템이므로, 데이터 모델 대신 스킬 간 인터페이스를 정의합니다.*

### 3.1 Input Interface

```
입력 형식 (사용자가 제공)
──────────────────────────
필수: <ticker_or_name>
  - 미국/글로벌: "NVDA", "AAPL", "Tesla", "ASML"
  - 한국: "005930", "삼성전자", "035720" (6자리 숫자 = KOSPI/KOSDAQ 자동 감지)
  - 기업명: "엔비디아", "마이크로소프트"

선택 접미사 (명시적 조정):
  - "+quant"      → Step 6 퀀트 분석 강제 실행
  - "+value"      → 가치주 페르소나 우선 선택 오버라이드
  - "+growth"     → 성장주 페르소나 우선 선택 오버라이드
  - "+brief"      → 딜 브리핑 형식 (30초 요약) 출력
```

### 3.2 Step Outputs (내부 중간 결과)

```
Step 1 출력 ─────────────────────────────────────────
  stock_type_signals:
    - revenue_growth_cagr_3y: float      [Actual|Estimated]
    - pe_ratio: float                    [Actual|Estimated]
    - pb_ratio: float                    [Actual|Estimated]
    - fcf_yield: float                   [Actual|Estimated]
    - market_cap_usd: float              [Actual]
    - sector: string
    - country_exchange: string           (KR=KOSPI/KOSDAQ, US=NYSE/NASDAQ 등)
    - recent_news_flags: list            (M&A, activist, regulatory 등)

Step 2 출력 ─────────────────────────────────────────
  valuation_anchor:
    - narrative: string                  시장이 프라이싱하는 스토리
    - implied_growth_rate: float         Reverse DCF 역산 성장률
    - fair_value_range: [low, high]      Forward DCF 추정 범위
    - expectation_gap: string            현재가 vs 내재가치 괴리 판단

Step 3 출력 ─────────────────────────────────────────
  market_context:
    - regime: string                     risk-on/off, tightening/easing 등
    - cycle_position: string             early/mid/late/contraction
    - backdrop_verdict: string           "강화" / "약화" / "중립" / "무효화"

Step 4 출력 ─────────────────────────────────────────
  stock_type: string                     GROWTH/VALUE/GARP/MACRO/EVENT
  selected_personas: list[2~3]           페르소나 이름 + 선택 이유

Step 5 출력 ─────────────────────────────────────────
  persona_stances:
    - persona_name: string
    - stance: BUY | HOLD | SELL
    - rationale: string (1~2줄)
    - conviction: HIGH | MEDIUM | LOW
  consensus_verdict: BUY | HOLD | SELL
  minority_view: string (있을 경우)

Step 6 출력 (선택) ──────────────────────────────────
  quant_signals:
    - momentum_signal: POSITIVE | NEUTRAL | NEGATIVE
    - factor_exposure: string
    - timing_note: string
```

### 3.3 Final Output Interface (브로커 리포트 섹션)

| 섹션 | 필수 | 최대 길이 | 상세 |
|------|:----:|:---------:|------|
| Header (종목/날짜/의견/TP) | Y | 5줄 | 리포트 최상단 |
| Investment Thesis (핵심 근거 3가지) | Y | 각 3줄 | 번호 매기기 |
| Valuation (TP 산출 근거) | Y | 8줄 | Reverse DCF + Comps 요약 |
| Market Context (백드롭 판단) | Y | 5줄 | regime + 백드롭 verdict |
| Persona Panel (패널 스탠스) | Y | 페르소나당 2줄 | 선택 이유 포함 |
| Risks & Catalysts | Y | 각 3~5 bullet | 리스크 / 카탈리스트 |
| Disclaimer | Y | 3줄 | 고정 면책 문구 |

---

## 4. Skill Call Sequences

### 4.1 Standard Flow (글로벌 상장주)

```
1. 입력 파싱 → 티커/종목명 정규화, 접미사 파싱, 시장 감지
2. openbb-data-fetcher 호출
   - 가격, 재무제표 (최근 4분기), 밸류에이션 멀티플, 뉴스 (최근 10건)
   - 실패 시 → partial-analysis 플래그 ON
3. company-analysis 호출
   - openbb 아웃풋을 컨텍스트로 제공
   - Narrative → Reverse DCF → Forward DCF → Comps → So What
4. traditional-market-analysis 호출
   - 현재 레짐 + 사이클 + 유동성 + 비대칭성 평가
5. persona-selection-logic (ref 파일 규칙 적용)
   - Step 1 데이터 기반 stock_type 분류
   - 선택 매트릭스에서 2~3개 페르소나 결정
6. 선택된 페르소나 스킬 순차 호출
   - 각 페르소나에 company-analysis + market-context 요약 전달
7. quant-research 호출 ("+quant" 접미사 OR 성장주/모멘텀주 자동)
8. 브로커 리포트 통합 조합 → broker-report-contract.md 형식으로 출력
```

### 4.2 Korean Market Flow (6자리 숫자 티커 감지 시)

```
Standard Flow 위에 추가:
- openbb 한국 주식 지원 여부 확인 (provider 가용 체크)
- 폴백: 웹 검색 (금융감독원 DART, 네이버금융, KIND) 로 K-IFRS 재무 수집
- 컨텍스트 추가: 외국인/기관 수급, 코스피 지수 대비 RS, K-IFRS 회계 기준 명시
- 페르소나 선택 시 Rakesh Jhunjhunwala (신흥국/아시아 가치주) 우선순위 상향
- Disclaimer에 "한국 시장 특화 분석, K-IFRS 기준" 문구 추가
```

### 4.3 Partial Analysis Mode (데이터 취득 실패 시)

```
OpenBB 완전 실패 시:
  → 웹 검색으로 최소 데이터 수집 (시가총액, 섹터, 최근 뉴스)
  → company-analysis는 "데이터 제한" 모드로 실행
  → 모든 수치에 [Unavailable] 또는 [Estimated-webfallback] 태그
  → 리포트 최상단에 "DATA LIMITATION" 섹션 추가
  → 파이프라인 계속 진행 (분석 포기하지 않음)
```

---

## 5. Output Format Design (브로커 리포트)

### 5.1 리포트 구조

```
═══════════════════════════════════════════════════════
 [종목명] ([티커]) — [거래소]
 분석일: [YYYY-MM-DD]  |  투자의견: [BUY/HOLD/SELL]
 목표주가(12M TP): [USD/KRW X,XXX]  |  현재가: [X,XXX]
 업사이드: [+XX%]  |  신뢰도: [HIGH/MEDIUM/LOW]

 ▶ 페르소나 패널: [페르소나1] + [페르소나2] (+ [페르소나3])
   선택 이유: [종목 유형] — [선택 근거 1줄]
═══════════════════════════════════════════════════════

## Investment Thesis

1. [핵심 근거 1] (2~3줄)
2. [핵심 근거 2] (2~3줄)
3. [핵심 근거 3] (2~3줄)

## Valuation

[Reverse DCF 역산: 현재 가격이 내포하는 성장률/마진 기대치]
[Forward DCF / Comps 기반 목표주가 산출 근거]
[Expectation Gap 판단]

모든 수치: [Actual] / [Estimated] / [Assumption] 태그 필수

## Market Context

레짐: [진단]  |  사이클: [위치]
백드롭 판단: [강화/약화/중립/무효화] — [이유 2~3줄]

## Persona Panel

| 페르소나 | 스탠스 | 핵심 이유 |
|----------|--------|-----------|
| [이름]   | BUY    | [1~2줄]   |
| [이름]   | HOLD   | [1~2줄]   |

컨센서스: [BUY/HOLD/SELL] (N/3 또는 N/2 동의)
소수의견: [있을 경우 명시]

## Quant Signals (선택)

모멘텀: [POSITIVE/NEUTRAL/NEGATIVE]
팩터 노출: [설명]
타이밍 참고: [진입/관망 노트]

## Risks

- [핵심 리스크 1]
- [핵심 리스크 2]
- [핵심 리스크 3]

## Catalysts (향후 12개월)

- [카탈리스트 1] — [예상 시점]
- [카탈리스트 2] — [예상 시점]

## Disclaimer

본 분석은 투자 참고 목적이며 투자 권유가 아닙니다.
모든 투자 결정의 책임은 투자자 본인에게 있습니다.
데이터 출처: OpenBB / 공개 재무 공시 / 웹 검색 (폴백).
═══════════════════════════════════════════════════════
```

### 5.2 출력 변형

| 트리거 | 형식 | 분량 |
|--------|------|------|
| 기본 | 브로커 리포트 (상기 전체) | 1~2페이지 |
| `+brief` | 딜 브리핑 (헤더 + Thesis + Risks only) | 30초 독서 분량 |
| `+quant` | 브로커 리포트 + 확장 퀀트 섹션 | 2~3페이지 |

---

## 6. Error Handling

### 6.1 오류 유형 및 처리

| 상황 | 처리 방식 | 아웃풋 영향 |
|------|-----------|-------------|
| OpenBB 미설치 | pip install 후 재시도, 실패 시 웹 폴백 | DATA LIMITATION 섹션 추가 |
| 티커 인식 불가 | 웹 검색으로 티커 추정, 확인 후 진행 | 헤더에 "ticker inferred" 명시 |
| 페르소나 스킬 호출 실패 | 해당 페르소나 건너뛰고 나머지로 진행 | 패널에 "skip reason" 표시 |
| 사모기업/비상장 | 비상장 모드 전환 (comps 중심, DCF 제한적) | 헤더에 "Private company — limited data" |
| 한국 종목 OpenBB 실패 | DART/네이버금융 웹 폴백 | [non-OpenBB fallback data] 태그 |

### 6.2 할루시네이션 방어 규칙

- 검증되지 않은 수치는 절대 `[Actual]`로 태깅하지 않음
- 멀티플/거래 데이터 출처 불명 시 "Bloomberg/CapIQ 등 전문 DB 검증 필요" 명시
- 사설 가이던스, 루머성 뉴스는 `[rumor]` 태그 후 분석 제외

---

## 7. Security Considerations

이 스킬은 파일 기반 Markdown 시스템으로, 전통적 보안 위험은 없으나 다음을 준수:

- [ ] OpenBB API 키를 SKILL.md나 references에 절대 하드코딩하지 않음
- [ ] `~/.openbb_platform/.env` 또는 세션 전용 환경변수만 사용 (openbb-data-fetcher 정책 상속)
- [ ] 웹 폴백 데이터 출처 항상 명시 (출처 미명시 = hallucination과 동일 취급)
- [ ] 투자 의견은 항상 면책 조항과 함께 출력

---

## 8. Test Plan

### 8.1 Test Scope

| Type | Target | Method |
|------|--------|--------|
| L1: 기본 파이프라인 | 미국 상장주 (NVDA) — 7단계 실행 완료 확인 | 수동 실행 + 아웃풋 컨트랙트 체크 |
| L2: 한국 종목 | KOSPI 종목 (005930) — 6자리 감지 + K컨텍스트 활성화 | 수동 실행 |
| L3: 페르소나 선택 | 성장주 vs 가치주 — 적합한 페르소나 선택 검증 | 2종목 비교 |
| L4: 오류 처리 | 존재하지 않는 티커 / OpenBB 실패 시 graceful handling | 케이스 시뮬레이션 |

### 8.2 End-to-End 테스트 케이스

| # | 입력 | 검증 포인트 | 성공 기준 |
|---|------|-------------|-----------|
| 1 | `NVDA` | 브로커 리포트 6섹션 완성 + TP 존재 + BUY/HOLD/SELL 명시 | 아웃풋 컨트랙트 100% 충족 |
| 2 | `005930` | "KOSPI/K-IFRS" 컨텍스트 포함, KRW 목표주가 | 한국 시장 컨텍스트 존재 |
| 3 | `NVDA` vs `JNJ` | NVDA → 성장주 페르소나, JNJ → 가치주 페르소나 자동 선택 | 페르소나 매칭 적합성 |
| 4 | `XXXXX` (존재 불가 티커) | 오류 후 graceful fallback, 분석 포기하지 않음 | DATA LIMITATION 명시 후 최선 분석 |
| 5 | `NVDA +brief` | 딜 브리핑 형식 — 헤더+Thesis+Risks만 출력 | 분량 30초 이내 |

---

## 9. File Layer Structure

*스킬 파일 시스템의 계층 구조 (웹앱 Clean Architecture 대응)*

### 9.1 레이어 정의

| 레이어 | 역할 | 파일 |
|--------|------|------|
| **Orchestration** | 흐름 제어, 스킬 호출 순서 | `SKILL.md` |
| **Logic Reference** | 페르소나 선택 매트릭스, 파이프라인 라우팅 | `references/persona-selection-logic.md`, `references/analysis-pipeline.md` |
| **Output Contract** | 아웃풋 형식, 섹션 정의, 길이 제한 | `references/broker-report-contract.md` |
| **Downstream Skills** | 실제 분석 실행 | 기존 스킬들 (불변) |

### 9.2 의존 방향

```
SKILL.md (Orchestration)
    │
    ├── references/persona-selection-logic.md   (Logic)
    ├── references/analysis-pipeline.md          (Logic)
    ├── references/broker-report-contract.md     (Output)
    │
    └── 호출 → openbb-data-fetcher
           → company-analysis
           → traditional-market-analysis
           → investor-personas/*
           → quant-research (선택)
           → financial-report (선택)
```

---

## 10. Coding Convention Reference

*스킬 파일 작성 컨벤션 (`.claude/AGENTS.md` + `.claude/skills/AGENTS.md` 기반)*

### 10.1 스킬 파일 컨벤션

| 항목 | 규칙 |
|------|------|
| 폴더명 | lowercase hyphen-case (`pro-securities-analyst`) |
| SKILL.md 프론트매터 | `name`, `description` 필수 |
| description 길이 | 1~2 문장, 언제 사용할지 명확히 명시 |
| 데이터 태깅 | `[actual]`/`[inference]`/`[assumption]` (하위 스킬 관례) 또는 `[Actual]`/`[Estimated]`/`[Assumption]` (이 스킬 관례) — 리포트 아웃풋에서는 대문자 첫글자 통일 |
| references 파일 | 긴 프레임워크, 체크리스트, 템플릿만 분리 |
| 섹션 제목 | `##` 레벨 사용, 번호 매기기 |

### 10.2 한국 시장 식별 규칙

| 조건 | 감지 로직 | 활성화 컨텍스트 |
|------|-----------|----------------|
| 티커 = 6자리 숫자 | `^\d{6}$` 패턴 | K-IFRS 컨텍스트, KRW 목표주가, 금감원/DART 언급 |
| 종목명 한국어 | 유니코드 한국어 범위 포함 | 동일 |
| 거래소 = KRX | OpenBB country='KR' | 동일 |

---

## 11. Implementation Guide

### 11.1 File Structure (신규 생성 파일)

```
.claude/skills/
├── orchestrators/                                   ← 신규 카테고리 디렉터리
│   ├── AGENTS.md                                   ← 신규 (카테고리 가이드)
│   └── pro-securities-analyst/                     ← 신규 스킬 폴더
│       ├── SKILL.md                               ← 신규 (오케스트레이터 메인)
│       └── references/
│           ├── persona-selection-logic.md         ← 신규 (페르소나 선택 매트릭스)
│           ├── analysis-pipeline.md               ← 신규 (파이프라인 상세 라우팅)
│           └── broker-report-contract.md          ← 신규 (아웃풋 형식 & 길이 제한)
```

**수정 파일**: 없음 (기존 스킬 모두 불변)

### 11.2 Implementation Order

1. [ ] **Module 1**: `orchestrators/AGENTS.md` — 카테고리 가이드
2. [ ] **Module 2**: `references/persona-selection-logic.md` — 페르소나 선택 매트릭스 (13개 페르소나 × 종목 유형)
3. [ ] **Module 3**: `references/analysis-pipeline.md` — 7단계 파이프라인 상세, 라우팅, 폴백
4. [ ] **Module 4**: `references/broker-report-contract.md` — 아웃풋 섹션 정의, 길이 제한, 예시
5. [ ] **Module 5**: `SKILL.md` — 오케스트레이터 메인 (모든 ref 참조, 전체 흐름 제어)

### 11.3 Session Guide

#### Module Map

| Module | Scope Key | 파일 | 추정 작업량 |
|--------|-----------|------|:-----------:|
| 카테고리 AGENTS | `module-1` | `orchestrators/AGENTS.md` | 소 (1개 파일, ~30줄) |
| 페르소나 선택 로직 | `module-2` | `references/persona-selection-logic.md` | 중 (13개 페르소나 매트릭스) |
| 분석 파이프라인 | `module-3` | `references/analysis-pipeline.md` | 중 (7단계 상세 라우팅) |
| 아웃풋 컨트랙트 | `module-4` | `references/broker-report-contract.md` | 소~중 (형식 정의) |
| SKILL.md 메인 | `module-5` | `SKILL.md` | 중~대 (전체 오케스트레이션 로직) |

#### Recommended Session Plan

| Session | 범위 | Scope Key |
|---------|------|-----------|
| Session 1 (현재) | Plan + Design | 완료 |
| Session 2 | Module 1~4 (references 먼저) | `--scope module-1,module-2,module-3,module-4` |
| Session 3 | Module 5 (SKILL.md) + E2E 테스트 | `--scope module-5` |

---

## Version History

| Version | Date | Changes | Author |
|---------|------|---------|--------|
| 0.1 | 2026-04-29 | Initial draft (Option C Pragmatic selected) | JungMinB7 |

---
### 모든 출력을 한국어로 번역해서 출력