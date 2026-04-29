---
template: plan
version: 1.3
feature: pro-securities-analyst
date: 2026-04-29
author: JungMinB7
project: auto-investing
status: Draft
---

# pro-securities-analyst Planning Document

> **Summary**: 20년 경력 글로벌 증권 전문가 페르소나를 가진 오케스트레이터 서브 에이전트 — 티커 하나로 즉시 브로커 리포트 수준의 종목 분석 실행
>
> **Project**: auto-investing
> **Author**: JungMinB7
> **Date**: 2026-04-29
> **Status**: Draft

---

## Executive Summary

| Perspective | Content |
|-------------|---------|
| **Problem** | 기존 스킬들(fundamental, market, quant, personas)이 개별 파편으로 존재하며, 하나의 종목에 대해 통합된 브로커 수준 판단을 내리는 단일 진입점이 없다 |
| **Solution** | 20년차 글로벌 증권 전문가 페르소나를 가진 오케스트레이터 스킬을 신설해, 티커 입력 하나로 전체 분석 파이프라인(데이터 수집 → 기업 분석 → 시장 맥락 → 페르소나 패널 → 브로커 리포트)을 자동 실행 |
| **Function/UX Effect** | 사용자는 "NVDA 분석해줘" 한 마디만으로 BUY/HOLD/SELL 의견, 목표주가, 핵심 근거 3가지, 리스크, 카탈리스트를 담은 1~2페이지 브로커 리포트를 즉시 수령 |
| **Core Value** | 13개 투자자 페르소나 + IB-style 분석 + 시장 맥락을 하나의 일관된 전문가 목소리로 통합해 투자 의사결정 속도를 대폭 단축 |

---

## Context Anchor

| Key | Value |
|-----|-------|
| **WHY** | 분산된 스킬들을 통합해 브로커 수준 종목 판단을 단일 진입점에서 제공 |
| **WHO** | 개인 투자자, 투자 리서치 보조가 필요한 사용자 (글로벌 주식 시장 전반) |
| **RISK** | 13개 페르소나 자동 선택 로직이 잘못된 페르소나를 고르면 분석 방향이 왜곡될 수 있음 |
| **SUCCESS** | 티커 입력 → 브로커 리포트 (TP + 의견 + 근거3 + 리스크 + 카탈리스트) 완전 자동 생성 |
| **SCOPE** | Phase 1: 오케스트레이터 SKILL.md 신설 / Phase 2: 페르소나 선택 로직 레퍼런스 / Phase 3: 브로커 리포트 아웃풋 컨트랙트 |

---

## 1. Overview

### 1.1 Purpose

개별 스킬(company-analysis, traditional-market-analysis, quant-research, investor-personas, openbb-data-fetcher, financial-report)이 파편화된 상태로 존재한다. 사용자가 "TSLA 분석"이라고 입력하면 어떤 스킬을 어떤 순서로 써야 하는지 직접 판단해야 하는 인지 부하가 생긴다.

`pro-securities-analyst`는 이 진입점 문제를 해결한다. 20년 경력 글로벌 증권 애널리스트 페르소나를 가진 오케스트레이터가 내부적으로 적절한 스킬들을 순서대로 호출하고, 최종적으로 기관 브로커 수준의 리포트를 출력한다.

### 1.2 Background

현재 리포지터리는 분석 역량은 충분하지만 "통합 판단자"가 없다. 예를 들어:
- company-analysis는 IB 스타일로 기업을 분석하지만 시장 맥락을 판단하지 않는다.
- traditional-market-analysis는 매크로 백드롭을 설명하지만 개별 종목 판단을 내리지 않는다.
- investor-personas는 특정 렌즈를 제공하지만 어떤 페르소나를 써야 하는지 사용자가 선택해야 한다.

`pro-securities-analyst`는 이 세 계층을 묶어 하나의 일관된 전문가 목소리로 만든다.

### 1.3 Related Documents

- `.claude/skills/fundamental-analysis/company-analysis/SKILL.md`
- `.claude/skills/market-analysis/traditional-market-analysis/SKILL.md`
- `.claude/skills/quantitative-analysis/quant-research/SKILL.md`
- `.claude/skills/data-access/openbb-data-fetcher/SKILL.md`
- `.claude/skills/output-formats/financial-report/SKILL.md`
- `.claude/skills/investor-personas/*/SKILL.md` (13개)

---

## 2. Scope

### 2.1 In Scope

- [ ] 오케스트레이터 SKILL.md 신설 (`skills/orchestrators/pro-securities-analyst/SKILL.md`)
- [ ] 페르소나 자동 선택 로직 레퍼런스 (`references/persona-selection-logic.md`)
- [ ] 브로커 리포트 아웃풋 컨트랙트 (`references/broker-report-contract.md`)
- [ ] 분석 파이프라인 라우팅 레퍼런스 (`references/analysis-pipeline.md`)
- [ ] `skills/orchestrators/AGENTS.md` 카테고리 가이드 신설
- [ ] 글로벌 주식 (미국, 유럽, 아시아) 및 한국 KOSPI/KOSDAQ 지원

### 2.2 Out of Scope

- 옵션/선물/파생상품 분석 (v1에서 제외)
- 자동 포트폴리오 리밸런싱 실행
- 실시간 알림 / 슬랙 연동
- 채권, 크립토 특화 분석 (기존 스킬 범위에 위임)

---

## 3. Requirements

### 3.1 Functional Requirements

| ID | Requirement | Priority | Status |
|----|-------------|----------|--------|
| FR-01 | 사용자가 티커 또는 종목명만 입력하면 추가 질문 없이 전체 분석 파이프라인 즉시 실행 | High | Pending |
| FR-02 | 종목 특성(성장주/가치주/매크로 민감주/퀀트 전략 등)에 따라 2~3개 투자자 페르소나 자동 선택 | High | Pending |
| FR-03 | openbb-data-fetcher로 데이터 수집 후 company-analysis 실행 (Reverse DCF 포함) | High | Pending |
| FR-04 | traditional-market-analysis로 시장 맥락(레짐, 사이클, 기대치) 평가 | High | Pending |
| FR-05 | 선택된 페르소나들의 스탠스를 통합해 컨센서스 + 소수의견 구조로 종합 | High | Pending |
| FR-06 | 최종 아웃풋: TP, 투자의견(BUY/HOLD/SELL), 핵심 근거 3가지, 핵심 리스크, 카탈리스트를 포함한 브로커 리포트 | High | Pending |
| FR-07 | 모든 수치에 `[Actual]`, `[Estimated]`, `[Assumption]` 태깅 유지 | High | Pending |
| FR-08 | 데이터 취득 실패 시 명확한 불확실성 명시 후 분석 가능 범위 내에서 계속 진행 | Medium | Pending |
| FR-09 | 퀀트 신호(모멘텀, 팩터 노출) 선택적 통합 — 단기 타이밍 판단에 활용 | Medium | Pending |
| FR-10 | 한국 시장(KOSPI/KOSDAQ) 종목 지원: K-IFRS, 금감원 공시, 외국인/기관 수급 컨텍스트 포함 | Medium | Pending |

### 3.2 Non-Functional Requirements

| Category | Criteria | Measurement Method |
|----------|----------|-------------------|
| Completeness | 브로커 리포트 6개 섹션 모두 존재 (TP, 의견, 근거, 리스크, 카탈리스트, 면책) | 아웃풋 컨트랙트 체크리스트 |
| Accuracy | 모든 사실 수치에 소스 태그 (`[Actual]`/`[Estimated]`/`[Assumption]`) | 아웃풋 리뷰 |
| Robustness | 데이터 취득 실패해도 partial analysis 가능 | 에러 케이스 테스트 |
| Anti-hallucination | 검증되지 않은 수치를 `[Actual]`로 태깅하지 않음 | 출력 검토 |

---

## 4. Success Criteria

### 4.1 Definition of Done

- [ ] `skills/orchestrators/pro-securities-analyst/SKILL.md` 작성 완료
- [ ] 페르소나 선택 매트릭스 레퍼런스 작성 완료
- [ ] 브로커 리포트 아웃풋 컨트랙트 작성 완료
- [ ] 분석 파이프라인 시퀀스 레퍼런스 작성 완료
- [ ] 글로벌 종목 1개 + 한국 종목 1개로 End-to-End 테스트 통과

### 4.2 Quality Criteria

- [ ] 입력: 티커만으로 전체 파이프라인 실행 가능
- [ ] 아웃풋: 브로커 리포트 6개 섹션 모두 포함
- [ ] 페르소나 선택: 성장주에 Buffett 대신 Lynch/Wood 선택 등 적절한 매칭
- [ ] 할루시네이션 방어: 검증 불가 데이터는 명시적 불확실성 표시

---

## 5. Risks and Mitigation

| Risk | Impact | Likelihood | Mitigation |
|------|--------|------------|------------|
| 페르소나 자동 선택 오류 — 성격이 다른 페르소나 조합으로 혼란스러운 의견 충돌 | Medium | Medium | 선택 매트릭스에 종목 유형별 우선순위 명시, 선택 근거 투명하게 출력 |
| OpenBB 데이터 취득 실패로 분석 불완전 | High | Low | partial-analysis 모드 정의, 취득 실패 섹션 명시 후 분석 가능 부분만 진행 |
| 기존 스킬 아웃풋 형식이 오케스트레이터 기대치와 불일치 | Medium | Low | 각 스킬의 output-contract.md를 사전 리뷰, 오케스트레이터에서 변환 레이어 정의 |
| 브로커 리포트가 너무 길어져 실용성 저하 | Low | Medium | 아웃풋 컨트랙트에 섹션별 최대 길이 제한 명시 |

---

## 6. Impact Analysis

### 6.1 Changed Resources

| Resource | Type | Change Description |
|----------|------|--------------------|
| `.claude/skills/orchestrators/` | New Directory | 오케스트레이터 카테고리 신설 |
| `.claude/skills/orchestrators/pro-securities-analyst/SKILL.md` | New File | 오케스트레이터 스킬 메인 파일 |
| `.claude/skills/orchestrators/pro-securities-analyst/references/` | New Directory | 페르소나 선택, 파이프라인, 아웃풋 컨트랙트 레퍼런스 |
| `.claude/skills/orchestrators/AGENTS.md` | New File | 오케스트레이터 카테고리 가이드 |

### 6.2 Current Consumers

| Resource | Operation | Code Path | Impact |
|----------|-----------|-----------|--------|
| `company-analysis` | READ (호출) | `pro-securities-analyst` → `company-analysis` | None (기존 스킬 불변) |
| `traditional-market-analysis` | READ (호출) | `pro-securities-analyst` → `traditional-market-analysis` | None (기존 스킬 불변) |
| `openbb-data-fetcher` | READ (호출) | `pro-securities-analyst` → `openbb-data-fetcher` | None (기존 스킬 불변) |
| `investor-personas/*` | READ (호출) | `pro-securities-analyst` → 선택된 2~3개 페르소나 | None (기존 스킬 불변) |
| `financial-report` | READ (호출) | `pro-securities-analyst` → `financial-report` | None (기존 스킬 불변) |
| `.claude/skills/AGENTS.md` | READ | 기존 스킬 구조 참조 | None |

### 6.3 Verification

- [ ] 기존 스킬(company-analysis, market-analysis 등) 동작 불변 확인
- [ ] 신규 디렉터리가 기존 naming 규칙(lowercase hyphen-case) 준수 확인
- [ ] AGENTS.md 계층 구조 일관성 확인

---

## 7. Architecture Considerations

### 7.1 Project Level Selection

| Level | Characteristics | Selected |
|-------|-----------------|:--------:|
| Starter | 단순 스킬 하나 | ☐ |
| Dynamic | 기존 스킬 조합·오케스트레이션 | ☑ |
| Enterprise | 독립 마이크로서비스 분리 | ☐ |

**선택: Dynamic** — 새 파일을 최소화하고 기존 스킬들을 오케스트레이션하는 구조.

### 7.2 Key Architectural Decisions

| Decision | Options | Selected | Rationale |
|----------|---------|----------|-----------|
| 스킬 위치 | `analysts/` vs `orchestrators/` | `orchestrators/` | 페르소나와 혼동 방지, 역할(조율)이 명확 |
| 페르소나 선택 방식 | 런타임 LLM 판단 vs 선택 매트릭스 | 매트릭스 + LLM 보정 | 일관성 확보하되 엣지케이스 유연성 유지 |
| 아웃풋 형식 | Markdown vs Plain-text | Markdown | 기존 financial-report 스킬 방식 따름 |
| 데이터 계층 | OpenBB 전용 vs 웹 검색 폴백 | OpenBB 우선 + 폴백 | openbb-data-fetcher의 폴백 정책 그대로 상속 |

### 7.3 Folder Structure

```
.claude/skills/
├── orchestrators/                        ← 신규 카테고리
│   ├── AGENTS.md                         ← 오케스트레이터 카테고리 가이드
│   └── pro-securities-analyst/
│       ├── SKILL.md                      ← 메인 오케스트레이터 스킬
│       └── references/
│           ├── persona-selection-logic.md   ← 페르소나 선택 매트릭스
│           ├── analysis-pipeline.md         ← 분석 순서 & 라우팅
│           └── broker-report-contract.md    ← 아웃풋 섹션 정의 & 길이 제한
```

### 7.4 Analysis Pipeline (High-Level)

```
입력: 티커 or 종목명
    │
    ▼
[Step 1] openbb-data-fetcher
    → 가격, 재무, 뉴스, 밸류에이션 데이터 수집
    │
    ▼
[Step 2] company-analysis
    → Narrative 정의 → Reverse DCF → Forward DCF → Comps → So What
    │
    ▼
[Step 3] traditional-market-analysis
    → 레짐 진단 → 사이클 위치 → 유동성/정책 전달 → 비대칭성 평가
    │
    ▼
[Step 4] persona-selection-logic
    → 종목 유형 분류 → 2~3개 페르소나 자동 선택
    │
    ▼
[Step 5] investor-personas (선택된 페르소나들)
    → 각 페르소나 스탠스 (BUY/HOLD/SELL + 핵심 이유)
    │
    ▼
[Step 6] quant-research (선택적, 단기 타이밍)
    → 모멘텀 신호, 팩터 노출, 포지셔닝 참고
    │
    ▼
[Step 7] 통합 판단 & 브로커 리포트 출력
    → TP + 의견 + 근거3 + 리스크 + 카탈리스트 + 면책
```

---

## 8. Convention Prerequisites

### 8.1 Existing Project Conventions

- [x] `.claude/AGENTS.md` 리포지터리 전체 규칙 존재
- [x] `.claude/skills/AGENTS.md` 스킬 규칙 존재
- [x] `skills/<top-level-domain>/<skill-name>/SKILL.md` 구조 준수
- [x] SKILL.md frontmatter: `name`, `description` 필드 필수
- [x] `references/` 폴더: 긴 공식, 프레임워크, 체크리스트 분리
- [x] lowercase hyphen-case 폴더명 규칙
- [x] 할루시네이션 방어: `[actual]`/`[inference]`/`[assumption]` 태깅

### 8.2 Conventions to Define for This Skill

| Category | Rule |
|----------|------|
| 페르소나 선택 태깅 | 선택된 페르소나와 선택 이유를 리포트 상단에 명시 |
| 신뢰도 태깅 | 데이터 태그를 `[Actual]`/`[Estimated]`/`[Assumption]` (대문자 첫글자)로 통일 |
| 섹션 길이 | 각 섹션 최대 줄 수는 broker-report-contract.md에 정의 |
| 한국 시장 식별 | 티커가 6자리 숫자면 KOSPI/KOSDAQ으로 자동 인식, 한국 특화 컨텍스트 활성화 |

---

## 9. Next Steps

1. [ ] Design 문서 작성 (`/pdca design pro-securities-analyst`)
   - SKILL.md 상세 구조 설계
   - 페르소나 선택 매트릭스 설계
   - 브로커 리포트 아웃풋 컨트랙트 설계
2. [ ] Do 단계: 파일 작성 및 End-to-End 테스트
3. [ ] 글로벌 종목(예: NVDA) + 한국 종목(예: 005930 삼성전자)으로 검증

---

## Version History

| Version | Date | Changes | Author |
|---------|------|---------|--------|
| 0.1 | 2026-04-29 | Initial draft | JungMinB7 |


### 모든 출력을 한국어로 번역해서 출력