---
template: design
version: 1.3
feature: auto-trading-engine
date: 2026-04-29
author: JungMinB7
project: auto-investing
status: Draft
---

# auto-trading-engine Design Document

> **Summary**: FastAPI + Ports & Adapters (Hexagonal) Clean Architecture — `pro-securities-analyst` 신호를 키움 REST API로 완전 자동 실행하는 KRX 자동 매매 엔진
>
> **Project**: auto-investing
> **Author**: JungMinB7
> **Date**: 2026-04-29
> **Status**: Draft
> **Planning Doc**: [auto-trading-engine.plan.md](../01-plan/features/auto-trading-engine.plan.md)

---

## Context Anchor

| Key | Value |
|-----|-------|
| **WHY** | 분석 스킬과 실제 주문 실행 사이의 갭 제거 — 수동 개입 없는 완전 자동 거래 사이클 구현 |
| **WHO** | 개인 투자자 (JungMinB7) — 한국 KRX(KOSPI/KOSDAQ) 자동 매매 운영 |
| **RISK** | 잘못된 신호 → 오주문 → 실제 손실; 키움 API 장애 → 미체결 포지션 방치; 리스크 가드 미작동 → 한도 초과 손실 |
| **SUCCESS** | 장 시작부터 종료까지 완전 무인 운영; 리스크 가드가 일일 손실 한도 초과 시 자동 거래 중단 |
| **SCOPE** | Phase 1: 핵심 도메인 + 키움 어댑터 + 기본 실행 파이프라인 / Phase 2: 리스크 가드 + APScheduler / Phase 3: 백테스트 + Discord 알림 |

---

## 1. Overview

### 1.1 Design Goals

1. **레이어 격리**: Domain 레이어는 외부 의존성 0 — FastAPI, SQLAlchemy, Redis 임포트 없음
2. **포트 교체 가능성**: 키움 API → 다른 증권사 교체 시 어댑터만 교체, 도메인/유즈케이스 불변
3. **비동기 네이티브**: 전 레이어 `async/await`, 동기 블로킹 코드 없음
4. **안전 우선**: 리스크 가드가 실패하면 주문 실행 불가 — fail-safe 설계
5. **관찰 가능성**: 모든 주문/신호/오류를 structured JSON 로그 + PostgreSQL 이벤트 소싱으로 기록

### 1.2 Design Principles

- **Dependency Inversion**: 상위 레이어가 하위 레이어 인터페이스에 의존, 구현체에 의존하지 않음
- **Single Responsibility**: 각 유즈케이스는 하나의 비즈니스 작업만 수행
- **Fail-Safe**: 데이터 불완전 시 주문 중단, 오류 노출 (silent fail 금지)
- **Idempotency**: 동일 신호로 중복 주문 발생 불가 (Redis 분산 락)
- **Immutable Audit**: 주문 이벤트는 삭제/수정 불가 append-only 로그

---

## 2. Architecture

### 2.0 Architecture Comparison & Selection

| Criteria | Option A: Layered Monolith | Option B: Ports & Adapters ✅ | Option C: DDD + CQRS |
|----------|:-:|:-:|:-:|
| **접근 방식** | app/routers + services + models | Domain / Application / Infrastructure / Presentation | Aggregate + Command/Query + EventSourcing |
| **신규 파일** | ~20 | ~60 | ~100+ |
| **복잡도** | Low | Medium | High |
| **유지보수성** | Low (결합도 높음) | High | High |
| **구현 기간** | 1주 | 2-3주 | 4-6주 |
| **키움 API 교체** | 전체 수정 필요 | 어댑터만 교체 | 어댑터만 교체 |
| **단위 테스트** | 어려움 (mock 복잡) | 쉬움 (port mocking) | 쉬움 |
| **권장 대상** | 빠른 PoC | **개인 트레이딩 시스템** | 금융기관 엔터프라이즈 |

**선택**: Option B — Ports & Adapters (Hexagonal Architecture)

**근거**: 개인 트레이딩 시스템에 필요한 유지보수성과 테스트 가능성을 확보하면서 DDD/CQRS의 복잡도 오버헤드를 피함. 키움 API 교체 또는 해외 주식 지원 추가 시 어댑터만 교체하면 됨.

### 2.1 시스템 컴포넌트 다이어그램

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         auto-trading-engine                             │
│                                                                         │
│  ┌──────────────┐    ┌─────────────────────────────────────────────┐   │
│  │ APScheduler  │───▶│           TradingPipelineService            │   │
│  │  09:00 KST   │    │  (Application Layer - 파이프라인 조율자)    │   │
│  └──────────────┘    └─────────────┬──────────┬────────────────────┘   │
│                                    │          │                         │
│                       ┌────────────▼──┐  ┌───▼──────────────┐          │
│                       │AnalyzeStock   │  │ ExecuteTrade     │          │
│                       │UseCase        │  │ UseCase          │          │
│                       └────────┬──────┘  └───────┬──────────┘          │
│                                │                 │                      │
│                    ┌───────────▼──┐  ┌───────────▼──────────┐          │
│                    │ AnalystPort  │  │ BrokerPort           │          │
│                    │(인터페이스)  │  │(인터페이스)          │          │
│                    └───────┬──────┘  └───────────┬──────────┘          │
│                            │                     │                      │
│  Infrastructure Layer:     │                     │                      │
│                    ┌───────▼──────┐  ┌───────────▼──────────┐          │
│                    │ClaudeAnalyst │  │ KiwoomRestAdapter    │          │
│                    │Adapter       │  │                      │          │
│                    └───────┬──────┘  └───────────┬──────────┘          │
│                            │                     │                      │
│                    ┌───────▼──────┐  ┌───────────▼──────────┐          │
│                    │ Claude API   │  │  키움 REST API       │          │
│                    │ (External)   │  │  (External)          │          │
│                    └──────────────┘  └──────────────────────┘          │
│                                                                         │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐                 │
│  │ PostgreSQL   │  │   Redis      │  │   Discord    │                 │
│  │ (Audit+Data) │  │ (Cache+Lock) │  │  (Notify)    │                 │
│  └──────────────┘  └──────────────┘  └──────────────┘                 │
│                                                                         │
│  ┌──────────────────────────────────┐                                  │
│  │     FastAPI (Presentation)       │  ◀── 수동 조작 / 모니터링         │
│  │  GET /v1/positions               │                                  │
│  │  POST /v1/orders (manual)        │                                  │
│  │  GET /v1/signals/latest          │                                  │
│  └──────────────────────────────────┘                                  │
└─────────────────────────────────────────────────────────────────────────┘
```

### 2.2 완전 자동 매매 데이터 플로우

```
[APScheduler] 09:00 KST 트리거
  │
  ▼
[TradingPipelineService.run_daily_cycle()]
  │
  ├─ watchlist 조회 (PostgreSQL watchlist 테이블)
  │
  ├─ for each ticker in watchlist:
  │    │
  │    ├─ [Redis Lock] 오늘 이미 처리된 ticker인지 확인
  │    │   └─ 이미 처리됨 → SKIP
  │    │
  │    ├─ [AnalyzeStockUseCase.execute(ticker)]
  │    │   ├─ ClaudeAnalystAdapter.analyze(ticker)
  │    │   │   └─ Claude API → pro-securities-analyst 실행
  │    │   ├─ SignalParserService.parse(analyst_output)
  │    │   │   └─ regex: Investment Opinion: BUY/HOLD/SELL
  │    │   └─ → TradingSignal(type, confidence, target_price, report)
  │    │
  │    ├─ [AuditLogger] signal 이벤트 기록 (signals 테이블)
  │    │
  │    ├─ if signal.type == HOLD → SKIP (알림만)
  │    │
  │    ├─ [RiskGuardService.validate(signal, portfolio)]
  │    │   ├─ 일일 손실 한도 초과? → TradingHaltedError 발생
  │    │   ├─ 최대 포지션 수 초과? → PositionLimitError 발생
  │    │   ├─ 종목당 최대 투자금액 초과? → PositionSizeError 발생
  │    │   └─ 모든 검증 통과 → OK
  │    │
  │    ├─ [ExecuteTradeUseCase.execute(ticker, signal)]
  │    │   ├─ KiwoomRestAdapter.get_current_price(ticker)
  │    │   ├─ calculate_quantity(price, MAX_POSITION_KRW)
  │    │   ├─ KiwoomRestAdapter.place_order(ticker, side, qty, price)
  │    │   ├─ [AuditLogger] trade 이벤트 기록 (trades 테이블)
  │    │   └─ → Trade(id, status=PENDING)
  │    │
  │    └─ [DiscordNotifierAdapter.send(trade_summary)]
  │
  └─ [RiskSnapshotService.update_daily_pnl()]
```

### 2.3 레이어별 의존성 규칙

```
┌─────────────────────────────────────────────────────┐
│ Presentation ──▶ Application ──▶ Domain             │
│                      │                              │
│                      └──▶ Infrastructure ──▶ Domain │
│                                                     │
│ ✅ Domain: 외부 임포트 없음 (순수 Python)            │
│ ✅ Application: Domain만 임포트, Port 인터페이스 정의 │
│ ✅ Infrastructure: Domain + 외부 라이브러리 임포트   │
│ ✅ Presentation: Application 유즈케이스 호출         │
│ ❌ Domain → 다른 레이어 임포트 불가                  │
│ ❌ Application → Infrastructure 구현체 직접 임포트 불가│
└─────────────────────────────────────────────────────┘
```

---

## 3. Data Model

### 3.1 Domain Entities (Python — 외부 의존성 없음)

```python
# src/domain/entities/trade.py
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from uuid import UUID, uuid4

class OrderSide(str, Enum):
    BUY = "BUY"
    SELL = "SELL"

class OrderType(str, Enum):
    MARKET = "MARKET"
    LIMIT = "LIMIT"

class OrderStatus(str, Enum):
    PENDING = "PENDING"
    FILLED = "FILLED"
    CANCELLED = "CANCELLED"
    FAILED = "FAILED"

@dataclass
class Trade:
    ticker: str
    order_side: OrderSide
    order_type: OrderType
    quantity: int
    price: float | None          # None = 시장가
    status: OrderStatus = OrderStatus.PENDING
    id: UUID = field(default_factory=uuid4)
    signal_id: UUID | None = None
    kiwoom_order_id: str | None = None
    filled_price: float | None = None
    filled_quantity: int | None = None
    error_message: str | None = None
    created_at: datetime = field(default_factory=datetime.utcnow)
    filled_at: datetime | None = None

    def mark_filled(self, filled_price: float, filled_qty: int) -> None:
        self.status = OrderStatus.FILLED
        self.filled_price = filled_price
        self.filled_quantity = filled_qty
        self.filled_at = datetime.utcnow()

    def mark_failed(self, reason: str) -> None:
        self.status = OrderStatus.FAILED
        self.error_message = reason
```

```python
# src/domain/entities/signal.py
class SignalType(str, Enum):
    BUY = "BUY"
    HOLD = "HOLD"
    SELL = "SELL"

class ConfidenceLevel(str, Enum):
    HIGH = "HIGH"
    MEDIUM_HIGH = "MEDIUM-HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"

@dataclass
class TradingSignal:
    ticker: str
    signal_type: SignalType
    confidence: ConfidenceLevel
    target_price: float | None
    current_price: float | None
    upside_pct: float | None
    analyst_report: str           # 원문 markdown
    id: UUID = field(default_factory=uuid4)
    created_at: datetime = field(default_factory=datetime.utcnow)

    @property
    def is_actionable(self) -> bool:
        return self.signal_type in (SignalType.BUY, SignalType.SELL)

    @property
    def is_high_confidence(self) -> bool:
        return self.confidence in (ConfidenceLevel.HIGH, ConfidenceLevel.MEDIUM_HIGH)
```

```python
# src/domain/entities/position.py
@dataclass
class Position:
    ticker: str
    quantity: int
    avg_cost: float               # KRW
    id: UUID = field(default_factory=uuid4)
    realized_pnl: float = 0.0
    opened_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)

    def market_value(self, current_price: float) -> float:
        return self.quantity * current_price

    def unrealized_pnl(self, current_price: float) -> float:
        return (current_price - self.avg_cost) * self.quantity

    def unrealized_pnl_pct(self, current_price: float) -> float:
        return (current_price - self.avg_cost) / self.avg_cost * 100
```

```python
# src/domain/entities/risk_rule.py
@dataclass
class RiskRule:
    max_daily_loss_krw: float     # 일일 최대 손실 (원)
    max_position_count: int       # 최대 동시 보유 종목 수
    max_position_krw: float       # 종목당 최대 투자금액 (원)
    max_position_pct: float       # 포트폴리오 대비 최대 비중 (%)
    min_signal_confidence: ConfidenceLevel  # 최소 신호 신뢰도
```

### 3.2 Value Objects

```python
# src/domain/value_objects/ticker.py
@dataclass(frozen=True)
class Ticker:
    code: str   # e.g., "005930", "000660"

    def __post_init__(self):
        if not self.code.isdigit() or len(self.code) != 6:
            raise ValueError(f"KRX ticker must be 6 digits: {self.code}")

    @property
    def is_kospi(self) -> bool:
        return int(self.code) < 200000  # 대략적 구분 (실제는 API에서 확인)
```

### 3.3 Repository Interfaces (Domain Layer — ABC)

```python
# src/domain/repositories/trade_repository.py
from abc import ABC, abstractmethod

class TradeRepository(ABC):
    @abstractmethod
    async def save(self, trade: Trade) -> Trade: ...

    @abstractmethod
    async def find_by_id(self, trade_id: UUID) -> Trade | None: ...

    @abstractmethod
    async def find_by_ticker_today(self, ticker: str) -> list[Trade]: ...

    @abstractmethod
    async def find_pending(self) -> list[Trade]: ...
```

### 3.4 PostgreSQL Schema

```sql
-- 001_initial_schema.sql (Alembic migration)

-- 분석 신호
CREATE TABLE signals (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    ticker      VARCHAR(10)  NOT NULL,
    signal_type VARCHAR(10)  NOT NULL CHECK (signal_type IN ('BUY', 'HOLD', 'SELL')),
    confidence  VARCHAR(20)  NOT NULL,
    target_price NUMERIC(15,2),
    current_price NUMERIC(15,2),
    upside_pct  NUMERIC(8,2),
    analyst_report TEXT,
    created_at  TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);
CREATE INDEX ix_signals_ticker_date ON signals(ticker, DATE(created_at));

-- 주문 내역
CREATE TABLE trades (
    id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    ticker           VARCHAR(10)  NOT NULL,
    order_side       VARCHAR(10)  NOT NULL CHECK (order_side IN ('BUY', 'SELL')),
    order_type       VARCHAR(20)  NOT NULL CHECK (order_type IN ('MARKET', 'LIMIT')),
    quantity         INTEGER      NOT NULL,
    price            NUMERIC(15,2),           -- NULL = 시장가
    status           VARCHAR(20)  NOT NULL DEFAULT 'PENDING',
    kiwoom_order_id  VARCHAR(50),
    signal_id        UUID         REFERENCES signals(id),
    filled_price     NUMERIC(15,2),
    filled_quantity  INTEGER,
    error_message    TEXT,
    created_at       TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    filled_at        TIMESTAMPTZ
);
CREATE INDEX ix_trades_ticker_date ON trades(ticker, DATE(created_at));
CREATE INDEX ix_trades_status ON trades(status);

-- 현재 포지션
CREATE TABLE positions (
    id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    ticker         VARCHAR(10)  NOT NULL UNIQUE,
    quantity       INTEGER      NOT NULL DEFAULT 0,
    avg_cost       NUMERIC(15,2) NOT NULL,
    realized_pnl   NUMERIC(15,2) NOT NULL DEFAULT 0,
    opened_at      TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    updated_at     TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

-- 감사 이벤트 (append-only, 삭제/수정 불가)
CREATE TABLE audit_events (
    id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    event_type   VARCHAR(50)  NOT NULL,   -- 'SIGNAL_CREATED', 'ORDER_PLACED', 'ORDER_FILLED', 'RISK_HALT'
    entity_type  VARCHAR(50)  NOT NULL,
    entity_id    UUID,
    payload      JSONB        NOT NULL,
    created_at   TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);
CREATE INDEX ix_audit_events_type_date ON audit_events(event_type, DATE(created_at));

-- 일별 리스크 스냅샷
CREATE TABLE risk_snapshots (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    snapshot_date   DATE         NOT NULL UNIQUE,
    daily_pnl       NUMERIC(15,2) NOT NULL DEFAULT 0,
    daily_loss      NUMERIC(15,2) NOT NULL DEFAULT 0,
    trading_halted  BOOLEAN      NOT NULL DEFAULT FALSE,
    halt_reason     TEXT,
    created_at      TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

-- 감시 종목 리스트
CREATE TABLE watchlist (
    id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    ticker     VARCHAR(10)  NOT NULL UNIQUE,
    name       VARCHAR(100),
    market     VARCHAR(10)  NOT NULL DEFAULT 'KRX',
    is_active  BOOLEAN      NOT NULL DEFAULT TRUE,
    added_at   TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);
```

---

## 4. Application Layer (Ports & Use Cases)

### 4.1 Port Interfaces (Application Layer — ABC)

```python
# src/application/ports/broker_port.py
class BrokerPort(ABC):
    @abstractmethod
    async def place_order(self, ticker: str, side: OrderSide,
                          order_type: OrderType, quantity: int,
                          price: float | None) -> str: ...  # kiwoom_order_id

    @abstractmethod
    async def get_positions(self) -> list[dict]: ...

    @abstractmethod
    async def get_balance(self) -> float: ...  # 주문 가능 금액 (KRW)

    @abstractmethod
    async def get_current_price(self, ticker: str) -> float: ...

# src/application/ports/analyst_port.py
class AnalystPort(ABC):
    @abstractmethod
    async def analyze(self, ticker: str) -> str: ...  # Markdown 리포트 원문

# src/application/ports/price_port.py
class PricePort(ABC):
    @abstractmethod
    async def get_price(self, ticker: str) -> float | None: ...

    @abstractmethod
    async def set_price(self, ticker: str, price: float, ttl: int = 60) -> None: ...

# src/application/ports/notifier_port.py
class NotifierPort(ABC):
    @abstractmethod
    async def send(self, title: str, message: str, color: int = 0x00ff00) -> None: ...
```

### 4.2 Use Cases

```python
# src/application/use_cases/analyze_stock.py
@dataclass
class AnalyzeStockRequest:
    ticker: str

@dataclass
class AnalyzeStockResponse:
    signal: TradingSignal
    raw_report: str

class AnalyzeStockUseCase:
    def __init__(self, analyst: AnalystPort, signal_parser: SignalParserService,
                 signal_repo: SignalRepository):
        self._analyst = analyst
        self._parser = signal_parser
        self._signal_repo = signal_repo

    async def execute(self, request: AnalyzeStockRequest) -> AnalyzeStockResponse:
        raw_report = await self._analyst.analyze(request.ticker)
        signal = self._parser.parse(request.ticker, raw_report)
        await self._signal_repo.save(signal)
        return AnalyzeStockResponse(signal=signal, raw_report=raw_report)
```

```python
# src/application/use_cases/execute_trade.py
@dataclass
class ExecuteTradeRequest:
    ticker: str
    signal: TradingSignal

class ExecuteTradeUseCase:
    def __init__(self, broker: BrokerPort, risk_guard: RiskGuardService,
                 trade_repo: TradeRepository, lock: DistributedLock,
                 audit: AuditLogger, notifier: NotifierPort):
        ...

    async def execute(self, request: ExecuteTradeRequest) -> Trade:
        # 1. 중복 주문 방지 (Redis 분산 락)
        lock_key = f"trade:{request.ticker}:{date.today().isoformat()}"
        async with self._lock.acquire(lock_key, ttl=300):
            # 2. 오늘 이미 처리했는지 확인
            existing = await self._trade_repo.find_by_ticker_today(request.ticker)
            if existing:
                raise DuplicateOrderError(f"Already processed {request.ticker} today")

            # 3. 현재가 조회
            current_price = await self._broker.get_current_price(request.ticker)

            # 4. 주문 수량 계산
            quantity = self._calculate_quantity(current_price)

            # 5. 리스크 가드 검증
            await self._risk_guard.validate(request.ticker, request.signal, quantity, current_price)

            # 6. 주문 실행
            kiwoom_order_id = await self._broker.place_order(
                ticker=request.ticker,
                side=OrderSide[request.signal.signal_type.value],
                order_type=OrderType.LIMIT,
                quantity=quantity,
                price=current_price,
            )

            # 7. 거래 기록
            trade = Trade(
                ticker=request.ticker,
                order_side=OrderSide[request.signal.signal_type.value],
                order_type=OrderType.LIMIT,
                quantity=quantity,
                price=current_price,
                signal_id=request.signal.id,
                kiwoom_order_id=kiwoom_order_id,
            )
            await self._trade_repo.save(trade)
            await self._audit.log("ORDER_PLACED", "trade", trade.id, trade.__dict__)

            return trade
```

### 4.3 RiskGuardService

```python
# src/application/services/risk_guard.py
class RiskGuardService:
    async def validate(self, ticker: str, signal: TradingSignal,
                       quantity: int, price: float) -> None:
        """리스크 검증 — 실패 시 예외 발생. 예외 없으면 주문 가능."""

        snapshot = await self._get_today_snapshot()

        # Rule 1: 거래 중단 여부
        if snapshot.trading_halted:
            raise TradingHaltedError(f"Trading halted: {snapshot.halt_reason}")

        # Rule 2: 일일 손실 한도
        if abs(snapshot.daily_loss) >= self._rule.max_daily_loss_krw:
            await self._halt_trading("일일 손실 한도 초과")
            raise DailyLossLimitError(f"Daily loss limit reached: {snapshot.daily_loss:,.0f} KRW")

        # Rule 3: 최대 포지션 수
        position_count = await self._position_repo.count_active()
        if position_count >= self._rule.max_position_count:
            raise PositionLimitError(f"Max positions reached: {position_count}")

        # Rule 4: 종목당 최대 투자금액
        investment_krw = quantity * price
        if investment_krw > self._rule.max_position_krw:
            raise PositionSizeError(f"Investment {investment_krw:,.0f} KRW exceeds max {self._rule.max_position_krw:,.0f}")

        # Rule 5: 최소 신뢰도
        if not self._meets_confidence(signal.confidence):
            raise LowConfidenceError(f"Signal confidence {signal.confidence} below minimum")
```

### 4.4 SignalParserService

```python
# src/application/services/signal_parser.py
class SignalParserService:
    _SIGNAL_RE = re.compile(r'Investment Opinion:\s*(BUY|HOLD|SELL)', re.IGNORECASE)
    _CONFIDENCE_RE = re.compile(r'Confidence:\s*(HIGH|MEDIUM-HIGH|MEDIUM|LOW)', re.IGNORECASE)
    _TP_RE = re.compile(r'12-Month Target Price:.*?([\d,]+)', re.IGNORECASE)
    _CURRENT_RE = re.compile(r'Current Price:.*?([\d,]+)', re.IGNORECASE)

    def parse(self, ticker: str, report: str) -> TradingSignal:
        signal_match = self._SIGNAL_RE.search(report)
        if not signal_match:
            raise SignalParseError(f"Cannot find Investment Opinion in report for {ticker}")

        confidence_match = self._CONFIDENCE_RE.search(report)
        tp_match = self._TP_RE.search(report)
        current_match = self._CURRENT_RE.search(report)

        tp = float(tp_match.group(1).replace(',', '')) if tp_match else None
        current = float(current_match.group(1).replace(',', '')) if current_match else None
        upside = ((tp - current) / current * 100) if tp and current else None

        return TradingSignal(
            ticker=ticker,
            signal_type=SignalType(signal_match.group(1).upper()),
            confidence=ConfidenceLevel(confidence_match.group(1).upper() if confidence_match else "MEDIUM"),
            target_price=tp,
            current_price=current,
            upside_pct=upside,
            analyst_report=report,
        )
```

---

## 5. Infrastructure Layer (Adapters)

### 5.1 KiwoomRestAdapter

```python
# src/infrastructure/kiwoom/kiwoom_adapter.py
class KiwoomRestAdapter(BrokerPort):
    """키움증권 REST API 어댑터 — BrokerPort 구현체"""

    BASE_URL = "https://openapi.koreainvestment.com:9443"  # 실제 URL 확인 필요

    def __init__(self, app_key: str, secret_key: str, account_no: str,
                 is_paper: bool = False):
        self._app_key = app_key
        self._secret_key = secret_key
        self._account_no = account_no
        self._is_paper = is_paper
        self._token: str | None = None
        self._token_expires: datetime | None = None
        self._client = httpx.AsyncClient(base_url=self.BASE_URL, timeout=10.0)

    async def _ensure_token(self) -> str:
        """OAuth 토큰 자동 갱신 (만료 5분 전 재발급)"""
        if self._token and self._token_expires and \
           datetime.utcnow() < self._token_expires - timedelta(minutes=5):
            return self._token
        await self._refresh_token()
        return self._token

    async def place_order(self, ticker: str, side: OrderSide, order_type: OrderType,
                          quantity: int, price: float | None) -> str:
        token = await self._ensure_token()
        # 키움 REST API 주문 엔드포인트 호출
        # 실제 엔드포인트: POST /uapi/domestic-stock/v1/trading/order-cash
        ...

    async def get_current_price(self, ticker: str) -> float:
        # GET /uapi/domestic-stock/v1/quotations/inquire-price
        ...
```

### 5.2 ClaudeAnalystAdapter

```python
# src/infrastructure/claude/claude_analyst.py
class ClaudeAnalystAdapter(AnalystPort):
    """Claude API → pro-securities-analyst 호출 어댑터"""

    MODEL = "claude-sonnet-4-6"
    SKILL_SYSTEM_PROMPT = """
    You are a 20-year veteran global securities analyst.
    Run the full pro-securities-analyst pipeline for the given ticker.
    Output the complete broker report in English Markdown format.
    Start immediately without asking clarifying questions.
    """

    def __init__(self, api_key: str):
        self._client = anthropic.AsyncAnthropic(api_key=api_key)

    async def analyze(self, ticker: str) -> str:
        message = await self._client.messages.create(
            model=self.MODEL,
            max_tokens=4096,
            system=self.SKILL_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": ticker}],
        )
        return message.content[0].text
```

### 5.3 APScheduler 통합

```python
# src/infrastructure/scheduler/trading_scheduler.py
class TradingScheduler:
    def __init__(self, pipeline: TradingPipelineService):
        self._scheduler = AsyncIOScheduler(timezone="Asia/Seoul")
        self._pipeline = pipeline

    def start(self) -> None:
        # 장 시작 10분 전 준비 (시세 WebSocket 연결 등)
        self._scheduler.add_job(
            self._pipeline.prepare_market_open,
            CronTrigger(hour=8, minute=50, day_of_week="mon-fri"),
            id="prepare",
        )
        # 장 시작 — 분석 + 매수
        self._scheduler.add_job(
            self._pipeline.run_morning_cycle,
            CronTrigger(hour=9, minute=0, day_of_week="mon-fri"),
            id="morning",
        )
        # 30분마다 포지션 모니터링 (손절/익절)
        self._scheduler.add_job(
            self._pipeline.run_position_monitor,
            IntervalTrigger(minutes=30),
            id="monitor",
        )
        # 장 마감 10분 전 — 미체결 주문 취소
        self._scheduler.add_job(
            self._pipeline.run_closing_routine,
            CronTrigger(hour=15, minute=20, day_of_week="mon-fri"),
            id="closing",
        )
        self._scheduler.start()

# main.py - FastAPI lifespan
@asynccontextmanager
async def lifespan(app: FastAPI):
    scheduler = app.state.container.scheduler()
    scheduler.start()
    yield
    scheduler.shutdown()
```

### 5.4 DI Container

```python
# src/presentation/dependencies.py
class TradingContainer(containers.DeclarativeContainer):
    config = providers.Configuration()

    # Infrastructure singletons
    kiwoom = providers.Singleton(
        KiwoomRestAdapter,
        app_key=config.kiwoom.app_key,
        secret_key=config.kiwoom.secret_key,
        account_no=config.kiwoom.account_no,
        is_paper=config.trading.paper_mode,
    )
    claude = providers.Singleton(
        ClaudeAnalystAdapter,
        api_key=config.claude.api_key,
    )
    db_session_factory = providers.Resource(create_async_session_factory, config.db.url)
    redis = providers.Singleton(RedisClient, url=config.redis.url)
    discord = providers.Singleton(DiscordNotifierAdapter, webhook_url=config.discord.webhook_url)

    # Repositories
    trade_repo = providers.Factory(PostgresTradeRepository, session=db_session_factory)
    position_repo = providers.Factory(PostgresPositionRepository, session=db_session_factory)
    signal_repo = providers.Factory(PostgresSignalRepository, session=db_session_factory)

    # Services
    signal_parser = providers.Singleton(SignalParserService)
    risk_guard = providers.Singleton(
        RiskGuardService,
        rule=providers.Factory(RiskRule,
            max_daily_loss_krw=config.risk.max_daily_loss_krw,
            max_position_count=config.risk.max_position_count,
            max_position_krw=config.risk.max_position_krw,
        ),
        position_repo=position_repo,
        snapshot_repo=providers.Factory(PostgresRiskSnapshotRepository, session=db_session_factory),
    )

    # Use Cases
    analyze_stock_uc = providers.Factory(
        AnalyzeStockUseCase, analyst=claude, signal_parser=signal_parser, signal_repo=signal_repo
    )
    execute_trade_uc = providers.Factory(
        ExecuteTradeUseCase, broker=kiwoom, risk_guard=risk_guard,
        trade_repo=trade_repo, notifier=discord,
    )

    # Pipeline
    pipeline = providers.Singleton(TradingPipelineService, ...)
    scheduler = providers.Singleton(TradingScheduler, pipeline=pipeline)
```

---

## 6. API Specification (FastAPI)

### 6.1 Endpoint 목록

| Method | Path | Description | Auth |
|--------|------|-------------|------|
| GET | `/health` | 시스템 헬스체크 (DB/Redis/Kiwoom 연결) | None |
| GET | `/v1/positions` | 현재 포지션 전체 조회 | API Key |
| GET | `/v1/positions/{ticker}` | 특정 종목 포지션 조회 | API Key |
| GET | `/v1/orders` | 주문 내역 조회 (date 파라미터 가능) | API Key |
| POST | `/v1/orders` | 수동 주문 실행 | API Key |
| GET | `/v1/signals/latest` | 최근 분석 신호 조회 | API Key |
| POST | `/v1/signals/analyze` | 특정 종목 즉시 분석 요청 | API Key |
| GET | `/v1/watchlist` | 감시 종목 조회 | API Key |
| POST | `/v1/watchlist` | 감시 종목 추가 | API Key |
| DELETE | `/v1/watchlist/{ticker}` | 감시 종목 제거 | API Key |
| GET | `/v1/risk/status` | 오늘 리스크 상태 (PnL, halt 여부) | API Key |
| POST | `/v1/risk/resume` | 거래 중단 수동 해제 | API Key |
| POST | `/v1/scheduler/start` | 스케줄러 수동 시작 | API Key |
| POST | `/v1/scheduler/stop` | 스케줄러 수동 중지 | API Key |

### 6.2 주요 Request/Response 스키마

```python
# POST /v1/orders (수동 주문)
class ManualOrderRequest(BaseModel):
    ticker: str = Field(..., pattern=r"^\d{6}$")
    side: Literal["BUY", "SELL"]
    order_type: Literal["MARKET", "LIMIT"] = "LIMIT"
    quantity: int = Field(..., gt=0)
    price: float | None = None  # LIMIT 시 필수

class TradeResponse(BaseModel):
    id: str
    ticker: str
    order_side: str
    quantity: int
    price: float | None
    status: str
    kiwoom_order_id: str | None
    created_at: datetime

# GET /health
class HealthResponse(BaseModel):
    status: Literal["healthy", "degraded", "unhealthy"]
    db: bool
    redis: bool
    kiwoom: bool
    scheduler_running: bool
    timestamp: datetime
```

### 6.3 API 인증 (Simple API Key)

```python
# X-API-Key 헤더 기반 인증
async def verify_api_key(x_api_key: str = Header(...)) -> None:
    if x_api_key != settings.API_KEY:
        raise HTTPException(status_code=401, detail="Invalid API key")
```

---

## 7. Error Handling

### 7.1 도메인 예외 계층

```
TradingError (base)
├── RiskGuardError
│   ├── TradingHaltedError
│   ├── DailyLossLimitError
│   ├── PositionLimitError
│   ├── PositionSizeError
│   └── LowConfidenceError
├── BrokerError
│   ├── KiwoomAuthError
│   ├── KiwoomOrderError
│   └── KiwoomRateLimitError
├── AnalysisError
│   └── SignalParseError
└── DuplicateOrderError
```

### 7.2 오류 처리 전략

| 오류 유형 | 처리 방식 | 알림 |
|---------|---------|------|
| `TradingHaltedError` | 해당 사이클 스킵, 다음 틱 대기 | Discord 경보 |
| `DailyLossLimitError` | 당일 전체 거래 중단 | Discord 긴급 알림 |
| `KiwoomAuthError` | 토큰 재발급 1회 재시도, 실패 시 halt | Discord 경보 |
| `KiwoomOrderError` | 주문 실패 기록, 재시도 없음 | Discord 알림 |
| `SignalParseError` | 신호 파싱 실패 → HOLD로 처리 | 로그만 |
| `DuplicateOrderError` | 조용히 스킵 | 로그만 |

### 7.3 FastAPI 전역 예외 핸들러

```python
@app.exception_handler(TradingError)
async def trading_error_handler(request: Request, exc: TradingError):
    return JSONResponse(
        status_code=400,
        content={"error": {"code": type(exc).__name__, "message": str(exc)}},
    )

@app.exception_handler(Exception)
async def generic_error_handler(request: Request, exc: Exception):
    logger.error("Unhandled error", exc_info=exc)
    return JSONResponse(status_code=500, content={"error": {"code": "INTERNAL_ERROR"}})
```

---

## 8. Security Considerations

- [ ] 모든 API 키/시크릿은 `.env` 파일에서 로드 (`python-dotenv`), 코드에 하드코딩 없음
- [ ] FastAPI API Key 인증 — 운영 환경에서 강력한 랜덤 키 사용
- [ ] PostgreSQL 연결은 SSL 모드 권장
- [ ] Redis `requirepass` 설정
- [ ] Docker 네트워크 격리 — PostgreSQL/Redis는 외부 노출 없음
- [ ] 주문 실행 전 quantity 상한값 검증 (최대 주문 수량 하드 제한)
- [ ] 키움 API 응답의 수치 데이터는 명시적 타입 변환 후 사용 (injection 방지)
- [ ] `TRADING_MODE=paper` 환경변수로 모의 거래 모드 강제 — 실거래 전 검증 필수

---

## 9. Test Plan

### 9.1 테스트 범위

| Type | 대상 | 도구 | Phase |
|------|------|------|-------|
| L1: 단위 테스트 | Domain 엔티티, SignalParserService, RiskGuardService | pytest | Do |
| L2: 통합 테스트 | Use Cases + Mock Adapters | pytest + pytest-asyncio | Do |
| L3: API 테스트 | FastAPI 엔드포인트 | pytest + httpx.AsyncClient | Do |
| L4: E2E 파이프라인 | 전체 파이프라인 (paper mode) | pytest + testcontainers | Check |

### 9.2 단위 테스트 시나리오 (L1)

| # | 테스트 | 기대 결과 |
|---|--------|---------|
| 1 | Trade.mark_filled(price, qty) | status=FILLED, filled_at 설정됨 |
| 2 | Ticker("005930") 생성 | 정상 생성 |
| 3 | Ticker("AAPL") 생성 | ValueError 발생 (6자리 아님) |
| 4 | SignalParserService.parse(ticker, report_BUY) | SignalType.BUY, confidence 파싱 |
| 5 | SignalParserService.parse(ticker, no_opinion_report) | SignalParseError 발생 |
| 6 | RiskGuardService.validate (정상 케이스) | 예외 없음 |
| 7 | RiskGuardService.validate (손실 한도 초과) | DailyLossLimitError |
| 8 | RiskGuardService.validate (포지션 한도 초과) | PositionLimitError |

### 9.3 API 테스트 시나리오 (L3)

| # | Endpoint | Method | 케이스 | Expected |
|---|----------|--------|--------|----------|
| 1 | /health | GET | 정상 상태 | 200, status=healthy |
| 2 | /v1/positions | GET | 인증 없음 | 401 |
| 3 | /v1/positions | GET | 인증 있음 | 200, list |
| 4 | /v1/orders | POST | 유효한 주문 (paper) | 201, trade.id |
| 5 | /v1/orders | POST | 잘못된 ticker | 422, validation error |
| 6 | /v1/risk/status | GET | 정상 | 200, trading_halted=false |

### 9.4 Mock 전략

```python
# tests/conftest.py
@pytest.fixture
def mock_broker():
    """BrokerPort mock — 실제 키움 API 호출 없음"""
    broker = AsyncMock(spec=BrokerPort)
    broker.get_current_price.return_value = 78500.0  # 삼성전자 가격
    broker.place_order.return_value = "ORDER-12345"
    broker.get_balance.return_value = 10_000_000.0   # 1천만원
    return broker

@pytest.fixture
def mock_analyst():
    analyst = AsyncMock(spec=AnalystPort)
    analyst.analyze.return_value = SAMPLE_BUY_REPORT  # 테스트용 리포트 픽스처
    return analyst
```

---

## 10. Clean Architecture 레이어 상세

### 10.1 레이어별 임포트 규칙

| From | Can Import | Cannot Import |
|------|-----------|---------------|
| `domain/` | 표준 라이브러리만 (`dataclasses`, `enum`, `uuid`, `datetime`) | FastAPI, SQLAlchemy, Redis, httpx 등 모두 불가 |
| `application/` | `domain/`, `abc`, `dataclasses` | `infrastructure/`, `presentation/`, FastAPI |
| `infrastructure/` | `domain/`, `application/ports/`, 외부 라이브러리 | `presentation/` |
| `presentation/` | `application/use_cases/`, `application/ports/`, `FastAPI` | `infrastructure/` 직접 (DI 컨테이너 통해서만) |

### 10.2 이 프로젝트의 레이어 할당

| 컴포넌트 | 레이어 | 경로 |
|---------|-------|------|
| Trade, Position, Signal | Domain | `src/domain/entities/` |
| Ticker, Money | Domain | `src/domain/value_objects/` |
| TradeRepository (ABC) | Domain | `src/domain/repositories/` |
| AnalyzeStockUseCase | Application | `src/application/use_cases/` |
| ExecuteTradeUseCase | Application | `src/application/use_cases/` |
| RiskGuardService | Application | `src/application/services/` |
| SignalParserService | Application | `src/application/services/` |
| BrokerPort (ABC) | Application | `src/application/ports/` |
| AnalystPort (ABC) | Application | `src/application/ports/` |
| KiwoomRestAdapter | Infrastructure | `src/infrastructure/kiwoom/` |
| ClaudeAnalystAdapter | Infrastructure | `src/infrastructure/claude/` |
| PostgresTradeRepository | Infrastructure | `src/infrastructure/db/repositories/` |
| RedisPriceCacheAdapter | Infrastructure | `src/infrastructure/redis/` |
| DiscordNotifierAdapter | Infrastructure | `src/infrastructure/discord/` |
| TradingScheduler (APScheduler) | Infrastructure | `src/infrastructure/scheduler/` |
| FastAPI routers | Presentation | `src/presentation/api/v1/` |
| DI Container | Presentation | `src/presentation/dependencies.py` |

---

## 11. Implementation Guide

### 11.1 최종 파일 구조

```
auto_investing/
├── src/
│   ├── domain/
│   │   ├── __init__.py
│   │   ├── entities/
│   │   │   ├── trade.py
│   │   │   ├── position.py
│   │   │   ├── signal.py
│   │   │   ├── risk_rule.py
│   │   │   └── watchlist.py
│   │   ├── value_objects/
│   │   │   ├── ticker.py
│   │   │   └── money.py
│   │   ├── repositories/
│   │   │   ├── trade_repository.py
│   │   │   ├── position_repository.py
│   │   │   └── signal_repository.py
│   │   └── exceptions.py
│   ├── application/
│   │   ├── use_cases/
│   │   │   ├── analyze_stock.py
│   │   │   ├── execute_trade.py
│   │   │   └── monitor_position.py
│   │   ├── services/
│   │   │   ├── risk_guard.py
│   │   │   ├── signal_parser.py
│   │   │   └── trading_pipeline.py
│   │   └── ports/
│   │       ├── broker_port.py
│   │       ├── analyst_port.py
│   │       ├── price_port.py
│   │       └── notifier_port.py
│   ├── infrastructure/
│   │   ├── kiwoom/
│   │   │   ├── kiwoom_adapter.py
│   │   │   ├── kiwoom_auth.py
│   │   │   └── kiwoom_websocket.py
│   │   ├── claude/
│   │   │   └── claude_analyst.py
│   │   ├── db/
│   │   │   ├── models.py             (SQLAlchemy ORM)
│   │   │   ├── session.py
│   │   │   └── repositories/
│   │   │       ├── postgres_trade_repo.py
│   │   │       ├── postgres_position_repo.py
│   │   │       └── postgres_signal_repo.py
│   │   ├── redis/
│   │   │   ├── price_cache.py
│   │   │   └── distributed_lock.py
│   │   ├── discord/
│   │   │   └── discord_notifier.py
│   │   └── scheduler/
│   │       └── trading_scheduler.py
│   └── presentation/
│       ├── api/
│       │   └── v1/
│       │       ├── positions.py
│       │       ├── orders.py
│       │       ├── signals.py
│       │       ├── watchlist.py
│       │       ├── risk.py
│       │       ├── scheduler.py
│       │       └── health.py
│       ├── schemas/
│       │   ├── position_schema.py
│       │   ├── order_schema.py
│       │   └── signal_schema.py
│       └── dependencies.py           (DI Container)
├── tests/
│   ├── unit/
│   │   ├── domain/
│   │   └── application/
│   ├── integration/
│   └── fixtures/
│       └── sample_reports.py        (pro-securities-analyst 샘플 출력)
├── alembic/
│   ├── env.py
│   └── versions/
│       └── 001_initial_schema.py
├── docker/
│   └── Dockerfile
├── docker-compose.yml
├── docker-compose.override.yml      (로컬 개발용)
├── pyproject.toml                   (uv 의존성)
├── .env.example
└── main.py                          (FastAPI app + lifespan)
```

**신규 파일**: ~55개 | **수정 파일**: 0개 (기존 없음)

### 11.2 구현 순서 (의존성 그래프 기반)

```
1. 프로젝트 구조 + pyproject.toml + Docker Compose
2. Domain 엔티티 + 값 객체 + 레포지터리 인터페이스
3. Application 포트 (ABC) 정의
4. Application 서비스 (SignalParserService, RiskGuardService)
5. Application 유즈케이스 (AnalyzeStockUseCase, ExecuteTradeUseCase)
6. SQLAlchemy 모델 + Alembic 마이그레이션
7. PostgreSQL 레포지터리 구현체
8. Redis 어댑터 (price cache + distributed lock)
9. KiwoomRestAdapter + 인증 클라이언트
10. ClaudeAnalystAdapter
11. DiscordNotifierAdapter
12. APScheduler + TradingPipelineService
13. FastAPI 라우터 + DI 컨테이너
14. 단위 테스트 (Domain + Application)
15. API 테스트 (Presentation)
16. Docker Compose 통합 검증
```

### 11.3 Session Guide

#### Module Map

| Module | Scope Key | 포함 내용 | 예상 턴 수 |
|--------|-----------|----------|:---------:|
| 프로젝트 기반 + Domain | `module-1` | pyproject.toml, Docker Compose, Domain 엔티티, 값객체, 레포지터리 인터페이스, 도메인 예외 | 30-40 |
| Application 레이어 | `module-2` | Ports(ABC), SignalParserService, RiskGuardService, AnalyzeStockUseCase, ExecuteTradeUseCase | 40-50 |
| DB + Redis Infrastructure | `module-3` | SQLAlchemy 모델, Alembic, Postgres 레포지터리 구현체, Redis 캐시/락 | 40-50 |
| 외부 API 어댑터 | `module-4` | KiwoomRestAdapter(+인증), ClaudeAnalystAdapter, DiscordNotifierAdapter | 40-50 |
| Presentation + Scheduler | `module-5` | FastAPI 라우터, Pydantic 스키마, DI 컨테이너, APScheduler 통합 | 30-40 |
| 테스트 + E2E 검증 | `module-6` | pytest 단위/통합 테스트, docker compose 검증, paper trading E2E | 30-40 |

#### Recommended Session Plan

| Session | Phase | Scope | 예상 턴 |
|---------|-------|-------|:-------:|
| Session 1 | Plan + Design | 전체 | 완료 |
| Session 2 | Do | `--scope module-1` | 30-40 |
| Session 3 | Do | `--scope module-2` | 40-50 |
| Session 4 | Do | `--scope module-3` | 40-50 |
| Session 5 | Do | `--scope module-4` | 40-50 |
| Session 6 | Do | `--scope module-5` | 30-40 |
| Session 7 | Do + Check | `--scope module-6` + analyze | 40-50 |
| Session 8 | Check + Report | 전체 | 30-40 |

> 각 세션: `/pdca do auto-trading-engine --scope module-N`

---

## Version History

| Version | Date | Changes | Author |
|---------|------|---------|--------|
| 0.1 | 2026-04-29 | Initial draft — Option B (Ports & Adapters) | JungMinB7 |
