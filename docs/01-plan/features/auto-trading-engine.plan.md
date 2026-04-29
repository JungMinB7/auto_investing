---
template: plan
version: 1.3
feature: auto-trading-engine
date: 2026-04-29
author: JungMinB7
project: auto-investing
status: Draft
---

# auto-trading-engine Planning Document

> **Summary**: FastAPI + Clean Architecture 기반 자동 주식 매매 엔진 — `pro-securities-analyst` 분석 신호를 키움 REST API로 즉시 실행하는 완전 자동화 시스템
>
> **Project**: auto-investing
> **Author**: JungMinB7
> **Date**: 2026-04-29
> **Status**: Draft

---

## Executive Summary

| Perspective | Content |
|-------------|---------|
| **Problem** | 브로커 리포트 수준의 분석(`pro-securities-analyst`)은 있지만 실제 주문 실행을 연결하는 자동화 엔진이 없어 사람이 매번 수동으로 거래해야 하는 실행 갭이 존재 |
| **Solution** | FastAPI + Clean Architecture 기반의 자동 매매 엔진 구축 — 분석 신호(BUY/HOLD/SELL)를 파이프라인화해 키움 REST API로 실시간 주문 실행, APScheduler로 장 시간 자동 관리 |
| **Function/UX Effect** | 장 시작(09:00 KST) → 자동 종목 분석 → 리스크 가드 통과 → 즉시 매수/매도 주문 → Discord 체결 알림 수신. 사람 개입 없이 전체 사이클 완료 |
| **Core Value** | `pro-securities-analyst`의 브로커 수준 판단 능력을 실제 자본으로 연결하는 완전 자동화 루프 — 분석·실행·모니터링·기록의 4단계를 단일 시스템으로 통합 |

---

## Context Anchor

| Key | Value |
|-----|-------|
| **WHY** | 분석 스킬과 실제 주문 실행 사이의 갭 제거 — 수동 개입 없는 완전 자동 거래 사이클 구현 |
| **WHO** | 개인 투자자 (JungMinB7) — 한국 KRX(KOSPI/KOSDAQ) 자동 매매 운영 |
| **RISK** | 잘못된 신호 → 오주문 → 실제 손실; 키움 API 장애 → 미체결 포지션 방치; 리스크 가드 미작동 → 한도 초과 손실 |
| **SUCCESS** | 장 시작부터 종료까지 완전 무인 운영; 리스크 가드가 일일 손실 한도 초과 시 자동 거래 중단 |
| **SCOPE** | Phase 1: 핵심 도메인 + 키움 어댑터 + 기본 실행 파이프라인 / Phase 2: 리스크 가드 + APScheduler / Phase 3: 백테스트 모듈 + Discord 알림 |

---

## 1. Overview

### 1.1 Purpose

`pro-securities-analyst`가 분석 리포트를 출력해도 실제 주문 실행은 사람이 해야 한다. 이 시스템은 분석→판단→실행→기록 루프 전체를 자동화한다.

핵심 플로우:
```
[APScheduler] 09:00 KST
  → [AnalyzeStockUseCase] pro-securities-analyst 호출 (Claude API)
  → [Signal Parser] BUY / HOLD / SELL 신호 추출
  → [RiskGuard] 일일 손실 한도 / 최대 포지션 / 종목당 한도 검증
  → [ExecuteTradeUseCase] 키움 REST API 주문 실행
  → [AuditLogger] PostgreSQL 주문/체결 로그
  → [Notifier] Discord 체결 알림
```

### 1.2 Background

현재 스택:
- `.claude/skills/orchestrators/pro-securities-analyst/` — 분석 오케스트레이터 (완성)
- `.claude/skills/investor-personas/` — 14개 투자자 페르소나 (완성)

이 시스템은 분석 스킬과 실제 자본 사이의 마지막 레이어를 구현한다.

### 1.3 Related Documents

- [`pro-securities-analyst` Plan](pro-securities-analyst.plan.md)
- [`pro-securities-analyst` Design](../02-design/features/pro-securities-analyst.design.md)
- [`pro-securities-analyst` Report](../04-report/features/pro-securities-analyst.report.md)
- 키움증권 REST API 공식 문서 (별도 확인 필요)

---

## 2. Scope

### 2.1 In Scope

- [ ] **핵심 도메인**: Trade, Position, Signal, Portfolio, RiskRule 엔티티 + Repository 인터페이스
- [ ] **키움 REST API 어댑터**: 인증(OAuth), 종목 조회, 매수/매도 주문, 체결 조회, 잔고 조회
- [ ] **Claude API 통합**: `pro-securities-analyst` 호출 → BUY/HOLD/SELL 신호 파싱
- [ ] **APScheduler**: 장 시작(09:00)/장 마감(15:30)/주기적 신호 갱신 스케줄링
- [ ] **WebSocket 클라이언트**: 키움 실시간 시세 수신 → Redis 캐시
- [ ] **리스크 가드**: 일일 손실 한도, 종목당 최대 투자금액, 최대 동시 포지션 수
- [ ] **PostgreSQL 저장**: 주문/체결/포지션/신호/감사 로그 이벤트 소싱
- [ ] **Redis**: 실시간 가격 캐시, 분산 락(중복 주문 방지), 이벤트 큐
- [ ] **Discord Webhook**: 주문 실행/체결/리스크 경보 알림
- [ ] **FastAPI REST API**: 포지션 조회, 수동 주문, 전략 제어, 헬스체크
- [ ] **vectorbt 백테스트**: 과거 데이터 기반 전략 검증 모듈
- [ ] **Docker Compose**: 전체 스택 단일 명령 실행

### 2.2 Out of Scope

- 미국/해외 주식 거래 (KRX 전용, Phase 1)
- 웹 대시보드 UI (REST API + Discord로 대체)
- 옵션/선물/파생상품
- 암호화폐
- 멀티 계좌 운용
- 자동 전략 파라미터 최적화 (강화학습 등)

---

## 3. Requirements

### 3.1 Functional Requirements

| ID | Requirement | Priority | Status |
|----|-------------|----------|--------|
| FR-01 | 키움 REST API OAuth 인증 및 토큰 자동 갱신 | High | Pending |
| FR-02 | `pro-securities-analyst` 호출 → BUY/HOLD/SELL 신호 파싱 파이프라인 | High | Pending |
| FR-03 | BUY 신호 시 지정가/시장가 매수 주문 실행 (키움 REST API) | High | Pending |
| FR-04 | SELL 신호 또는 손절 조건 충족 시 매도 주문 실행 | High | Pending |
| FR-05 | APScheduler로 장 시작(09:00)/장 마감(15:30)/주기적 스캔(30분) 자동 실행 | High | Pending |
| FR-06 | 리스크 가드: 일일 손실 한도 초과 시 전체 거래 중단 | High | Pending |
| FR-07 | 리스크 가드: 종목당 최대 투자금액, 최대 동시 포지션 수 제한 | High | Pending |
| FR-08 | Redis 분산 락으로 동일 종목 중복 주문 방지 (idempotency) | High | Pending |
| FR-09 | 실시간 WebSocket 시세 수신 → Redis 캐시 (가격 데이터 최신성 보장) | High | Pending |
| FR-10 | 모든 주문/신호/체결을 PostgreSQL에 이벤트 소싱 방식으로 영속 저장 | High | Pending |
| FR-11 | Discord Webhook으로 주문 실행/체결/리스크 경보 알림 | Medium | Pending |
| FR-12 | FastAPI REST API: 포지션 현황 조회, 수동 주문 실행, 스케줄러 제어 | Medium | Pending |
| FR-13 | vectorbt 기반 백테스트 모듈: 과거 OHLCV 데이터로 전략 성과 검증 | Medium | Pending |
| FR-14 | Graceful Shutdown: 장 마감 시 미체결 주문 자동 취소 처리 | Medium | Pending |
| FR-15 | 헬스체크 엔드포인트 (키움 API 연결, DB 연결, Redis 연결 상태) | Low | Pending |

### 3.2 Non-Functional Requirements

| Category | Criteria | Measurement |
|----------|----------|-------------|
| **아키텍처** | Clean Architecture 4-레이어 완전 분리 (Domain / Application / Infrastructure / Presentation) | 레이어 간 의존성 방향 단방향 검증 |
| **비동기** | 전 레이어 async/await 적용 — 동기 블로킹 코드 금지 | 코드 리뷰 |
| **신뢰성** | 주문 실행 idempotency — 동일 신호로 중복 주문 발생 불가 | 통합 테스트 |
| **보안** | API 키/시크릿 환경변수 전용 관리, 코드에 하드코딩 금지 | `.env` + `python-dotenv` |
| **테스트** | 유닛 테스트 80% 이상 커버리지 (Domain + Application 레이어) | pytest + coverage |
| **관찰가능성** | structured JSON 로그 (모든 주문/신호/오류), 타임스탬프 포함 | logging 표준 출력 |
| **배포** | `docker compose up` 단일 명령으로 전체 스택 실행 | Docker Compose 검증 |
| **복구** | 키움 API 일시 장애 시 지수 백오프 재시도 (최대 3회) | 재시도 로직 테스트 |

---

## 4. Success Criteria

### 4.1 Definition of Done

- [ ] 키움 REST API 인증 및 실제 주문 API 호출 성공 확인 (계좌 조회 등)
- [ ] `pro-securities-analyst` → 신호 파싱 → 키움 주문 실행 E2E 파이프라인 동작
- [ ] APScheduler로 09:00 KST 트리거 → 분석 → 주문 자동 실행 검증
- [ ] 리스크 가드가 일일 손실 한도 초과 케이스에서 거래 중단 동작
- [ ] `docker compose up` 한 번으로 전체 스택 (FastAPI + PostgreSQL + Redis) 실행
- [ ] Discord 주문 체결 알림 정상 수신
- [ ] pytest 유닛 테스트 통과 (Domain + Application 레이어)

### 4.2 Quality Criteria

- [ ] Domain 레이어가 외부 의존성 전혀 없음 (순수 Python, 프레임워크 import 없음)
- [ ] Application 레이어가 Infrastructure 구현체에 직접 의존하지 않음 (인터페이스만 사용)
- [ ] 모든 API 키/시크릿이 환경변수로 관리됨 (하드코딩 없음)
- [ ] 모든 주문 이벤트가 PostgreSQL에 기록됨 (감사 로그 완전성)
- [ ] 동일 신호로 연속 2회 실행 시 중복 주문 발생하지 않음

---

## 5. Risks and Mitigation

| Risk | Impact | Likelihood | Mitigation |
|------|--------|------------|------------|
| 키움 REST API 스펙 불명확 / 변경 | High | Medium | Adapter 패턴으로 키움 의존성을 Infrastructure에만 격리; 포트 인터페이스 먼저 설계 후 구현 |
| 잘못된 분석 신호 → 실제 손실 | High | Medium | 리스크 가드 레이어 필수 구현; 초기 운영은 소액(1만 원 단위) 페이퍼 트레이딩으로 검증 |
| 네트워크 단절 → WebSocket 재연결 실패 → 가격 데이터 stale | High | Medium | WebSocket 자동 재연결 로직 + Redis TTL로 stale 데이터 감지; 가격 데이터 없으면 거래 중단 |
| 키움 API Rate Limit 초과 → 주문 거부 | Medium | Low | Redis 기반 Rate Limiter 구현; API 호출 간격 최소 0.5초 |
| APScheduler 크래시 → 스케줄 누락 | High | Low | FastAPI lifespan 이벤트로 스케줄러 관리; 헬스체크 엔드포인트 + Docker restart policy |
| PostgreSQL 장애 → 주문 기록 유실 | High | Low | 이벤트 소싱 패턴 — 주문 성공 후 DB 저장 실패 시 재시도 큐; 로컬 파일 감사 로그 백업 |
| Discord API 장애 → 알림 누락 | Low | Low | 알림 실패가 거래 파이프라인을 막지 않도록 비동기 + 오류 무시 처리 |

---

## 6. Impact Analysis

### 6.1 Changed Resources

| Resource | Type | Change Description |
|----------|------|--------------------|
| `src/` | New Directory | Clean Architecture 4-레이어 소스 구조 신설 |
| `docker-compose.yml` | New File | FastAPI + PostgreSQL + Redis 오케스트레이션 |
| `.env` | New File | 키움 API 키, DB URL, Redis URL, Claude API 키, Discord Webhook URL |
| `docs/01-plan/features/auto-trading-engine.plan.md` | New File | 본 문서 |

### 6.2 Current Consumers

| Resource | Operation | Code Path | Impact |
|----------|-----------|-----------|--------|
| `.claude/skills/orchestrators/pro-securities-analyst/` | READ (호출) | `AnalyzeStockUseCase` → Claude API | None (스킬 불변, API로만 호출) |
| `.claude/skills/investor-personas/` | READ (간접) | pro-securities-analyst 내부에서 호출 | None |

### 6.3 Verification

- [ ] 기존 pro-securities-analyst 스킬 동작 불변 확인
- [ ] 키움 REST API 계좌 권한 범위 확인 (실계좌 vs 모의계좌)
- [ ] Claude API 키 유효성 및 pro-securities-analyst 호출 비용 추정

---

## 7. Architecture Considerations

### 7.1 Project Level Selection

| Level | Characteristics | Selected |
|-------|-----------------|:--------:|
| Starter | 단순 구조 | ☐ |
| Dynamic | 기능 기반 모듈 | ☐ |
| **Enterprise** | 엄격한 레이어 분리, DI, 복잡한 도메인 | ✅ |

**선택 근거**: 자동 매매 시스템은 도메인 복잡도(리스크 관리, 주문 상태 머신, 포지션 계산), 외부 의존성(키움 API, Claude API, Redis, PostgreSQL), 신뢰성 요구(중복 주문 방지, 감사 로그)가 모두 Enterprise 레벨에 해당함.

### 7.2 Key Architectural Decisions

| Decision | Options | Selected | Rationale |
|----------|---------|----------|-----------|
| 프레임워크 | FastAPI / Django / Flask | **FastAPI** | async 네이티브, OpenAPI 자동 생성, 타입 힌트 기반 Pydantic |
| 스케줄러 | Celery / APScheduler / cron | **APScheduler** | 예측 가능한 시간 기반 스케줄; Celery는 과설계 (분산 큐 불필요) |
| ORM | SQLAlchemy 2.0 / Tortoise | **SQLAlchemy 2.0 async** | 가장 성숙한 Python ORM, async 지원, Alembic 통합 |
| 마이그레이션 | Alembic / 수동 | **Alembic** | 스키마 버전 이력 관리 필수 |
| 캐시/락 | Redis / 인메모리 | **Redis** | 분산 락(중복 주문), 가격 캐시, pub/sub |
| 백테스트 | vectorbt / backtrader | **vectorbt** | NumPy 기반 고속 처리, Python 네이티브 통합 |
| 알림 | Discord / Slack / Telegram | **Discord Webhook** | 개인 투자자 운영 환경에 적합 |
| DI 컨테이너 | dependency_injector / 수동 | **dependency_injector** | Clean Architecture DI 지원, FastAPI 통합 |
| 테스트 | pytest / unittest | **pytest + pytest-asyncio** | asyncio 테스트 지원, fixture 시스템 |

### 7.3 Clean Architecture Folder Structure

```
auto_investing/
├── src/
│   ├── domain/                      # 순수 Python — 외부 의존성 없음
│   │   ├── entities/
│   │   │   ├── trade.py             (Trade, OrderSide, OrderStatus 엔티티)
│   │   │   ├── position.py          (Position, PositionSide)
│   │   │   ├── signal.py            (TradingSignal: BUY/HOLD/SELL + confidence)
│   │   │   ├── portfolio.py         (Portfolio aggregate)
│   │   │   └── risk_rule.py         (RiskRule: 손실 한도, 포지션 한도)
│   │   ├── value_objects/
│   │   │   ├── money.py             (Money: amount + currency, KRW)
│   │   │   ├── ticker.py            (Ticker: 종목 코드, 6자리 KOSPI/KOSDAQ)
│   │   │   └── market_price.py      (MarketPrice: price + timestamp)
│   │   └── repositories/            (추상 인터페이스 — ABC)
│   │       ├── trade_repository.py
│   │       ├── position_repository.py
│   │       └── signal_repository.py
│   │
│   ├── application/                 # 유즈케이스 — 도메인 의존, Infrastructure 인터페이스만 사용
│   │   ├── use_cases/
│   │   │   ├── analyze_stock.py     (AnalyzeStockUseCase: pro-securities-analyst 호출 → Signal)
│   │   │   ├── execute_trade.py     (ExecuteTradeUseCase: Signal → 주문 실행)
│   │   │   ├── monitor_position.py  (MonitorPositionUseCase: 손절/익절 모니터링)
│   │   │   └── run_backtest.py      (RunBacktestUseCase: vectorbt 실행)
│   │   ├── services/
│   │   │   ├── risk_guard.py        (RiskGuardService: 리스크 규칙 검증)
│   │   │   ├── signal_parser.py     (SignalParser: pro-securities-analyst 응답 파싱)
│   │   │   └── trading_pipeline.py  (TradingPipeline: 전체 파이프라인 조율)
│   │   └── ports/                   (아웃바운드 포트 인터페이스)
│   │       ├── broker_port.py       (BrokerPort: 주문 실행 추상화)
│   │       ├── analyst_port.py      (AnalystPort: 분석 호출 추상화)
│   │       ├── price_port.py        (PricePort: 시세 조회 추상화)
│   │       └── notifier_port.py     (NotifierPort: 알림 추상화)
│   │
│   ├── infrastructure/              # 외부 시스템 구현체
│   │   ├── kiwoom/
│   │   │   ├── kiwoom_adapter.py    (KiwoomRestAdapter: BrokerPort 구현)
│   │   │   ├── kiwoom_auth.py       (OAuth 토큰 자동 갱신)
│   │   │   └── kiwoom_websocket.py  (실시간 시세 WebSocket 클라이언트)
│   │   ├── claude/
│   │   │   └── claude_analyst.py    (ClaudeAnalystAdapter: AnalystPort 구현)
│   │   ├── db/
│   │   │   ├── models.py            (SQLAlchemy ORM 모델)
│   │   │   ├── repositories/        (Repository 구현체)
│   │   │   └── migrations/          (Alembic 마이그레이션)
│   │   ├── redis/
│   │   │   ├── price_cache.py       (Redis 가격 캐시: PricePort 구현)
│   │   │   └── distributed_lock.py  (Redis 분산 락: 중복 주문 방지)
│   │   ├── discord/
│   │   │   └── discord_notifier.py  (DiscordNotifier: NotifierPort 구현)
│   │   └── scheduler/
│   │       └── trading_scheduler.py (APScheduler: 장 시작/마감 트리거)
│   │
│   └── presentation/                # FastAPI 진입점
│       ├── api/
│       │   ├── v1/
│       │   │   ├── positions.py     (GET /positions, GET /positions/{ticker})
│       │   │   ├── orders.py        (POST /orders, GET /orders)
│       │   │   ├── signals.py       (GET /signals/latest)
│       │   │   └── health.py        (GET /health)
│       │   └── router.py
│       ├── schemas/                 (Pydantic Request/Response 스키마)
│       └── dependencies.py          (DI 컨테이너 설정)
│
├── tests/
│   ├── unit/
│   │   ├── domain/                  (엔티티 + 값 객체 테스트)
│   │   └── application/             (유즈케이스 + 서비스 테스트, mock 사용)
│   ├── integration/                 (실제 DB/Redis 연동 테스트)
│   └── e2e/                         (전체 파이프라인 테스트)
│
├── alembic/                         (DB 마이그레이션)
├── docker/
│   ├── Dockerfile
│   └── docker-compose.yml
├── .env.example
├── pyproject.toml                   (의존성: uv 또는 poetry)
└── README.md
```

---

## 8. Convention Prerequisites

### 8.1 Tech Stack (확정)

| Component | Library / Version | Role |
|-----------|------------------|------|
| Runtime | Python 3.12 | |
| API Framework | FastAPI 0.115+ | REST API 서버 |
| Data Validation | Pydantic v2 | 스키마 검증 |
| ORM | SQLAlchemy 2.0 (async) | DB 접근 |
| DB Migration | Alembic | 스키마 버전 관리 |
| DB | PostgreSQL 16 | 주문/체결/로그 저장 |
| Cache / Lock | Redis 7 + redis-py (async) | 가격 캐시, 분산 락 |
| Scheduler | APScheduler 3.x | 장 시간 스케줄링 |
| WebSocket | websockets | 키움 실시간 시세 |
| HTTP Client | httpx (async) | 키움/Claude REST API 호출 |
| Backtest | vectorbt | 과거 데이터 전략 검증 |
| DI | dependency-injector | 의존성 주입 |
| Testing | pytest + pytest-asyncio | 유닛/통합 테스트 |
| Packaging | uv | 빠른 의존성 관리 |
| Container | Docker + Docker Compose | 배포 |
| Notification | Discord Webhook | 알림 |
| Broker | 키움증권 REST API | 주문 실행 |
| Analyst | Anthropic Claude API | pro-securities-analyst 호출 |

### 8.2 Naming Conventions

| Category | Rule | Example |
|----------|------|---------|
| 파일명 | snake_case | `execute_trade.py` |
| 클래스명 | PascalCase | `ExecuteTradeUseCase` |
| 유즈케이스 | `{Action}{Noun}UseCase` | `AnalyzeStockUseCase` |
| 포트(인터페이스) | `{Noun}Port` | `BrokerPort` |
| 어댑터(구현체) | `{Platform}{Noun}Adapter` | `KiwoomRestAdapter` |
| 엔티티 | 순수 명사, PascalCase | `Trade`, `Position` |
| 값 객체 | 순수 명사, PascalCase | `Money`, `Ticker` |
| 레포지터리 인터페이스 | `{Noun}Repository` | `TradeRepository` |
| 레포지터리 구현체 | `Postgres{Noun}Repository` | `PostgresTradeRepository` |

### 8.3 Environment Variables

| Variable | Purpose | Scope |
|----------|---------|-------|
| `KIWOOM_APP_KEY` | 키움 REST API App Key | Server |
| `KIWOOM_SECRET_KEY` | 키움 REST API Secret | Server |
| `KIWOOM_ACCOUNT_NO` | 거래 계좌번호 | Server |
| `CLAUDE_API_KEY` | Anthropic Claude API 키 | Server |
| `DATABASE_URL` | PostgreSQL 연결 URL | Server |
| `REDIS_URL` | Redis 연결 URL | Server |
| `DISCORD_WEBHOOK_URL` | Discord 알림 Webhook | Server |
| `MAX_DAILY_LOSS_KRW` | 일일 최대 손실 한도 (원) | Server |
| `MAX_POSITION_COUNT` | 최대 동시 보유 종목 수 | Server |
| `MAX_POSITION_KRW` | 종목당 최대 투자금액 (원) | Server |
| `TRADING_MODE` | `live` / `paper` (모의 거래) | Server |
| `LOG_LEVEL` | `INFO` / `DEBUG` / `WARNING` | Server |

---

## 9. Next Steps

1. [ ] `/pdca design auto-trading-engine` — Clean Architecture 설계 문서 작성
2. [ ] 키움 REST API 공식 문서 확인 및 계좌 API 권한 신청
3. [ ] Claude API 키 발급 및 비용 예산 설정
4. [ ] 모의 계좌(페이퍼 트레이딩)로 초기 검증 환경 구성

---

## Version History

| Version | Date | Changes | Author |
|---------|------|---------|--------|
| 0.1 | 2026-04-29 | Initial draft | JungMinB7 |
