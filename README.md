# Auto Trading Engine

KRX(한국거래소) 완전 자동 매매 엔진. Claude API의 `pro-securities-analyst` 7단계 파이프라인이 종목을 분석하고, 키움증권 REST API로 주문을 실행하며, Discord로 알림을 전송합니다.

```
종목 분석 (Claude + OpenBB)
    → 신호 파싱 (BUY/HOLD/SELL)
    → 리스크 검증 (5-Rule Guard)
    → 주문 실행 (키움 REST API)
    → Discord 알림
```

---

## 목차

1. [아키텍처 개요](#아키텍처-개요)
2. [사전 요구사항](#사전-요구사항)
3. [빠른 시작](#빠른-시작)
4. [환경 변수 설정](#환경-변수-설정)
5. [API 사용법](#api-사용법)
6. [자동 스케줄러](#자동-스케줄러)
7. [OpenBB 설정](#openbb-설정)
8. [Paper Trading (모의 매매)](#paper-trading-모의-매매)
9. [리스크 관리](#리스크-관리)
10. [개발 환경](#개발-환경)
11. [테스트](#테스트)
12. [트러블슈팅](#트러블슈팅)

---

## 아키텍처 개요

```
┌─────────────────────────────────────────────────────────┐
│                    FastAPI (Port 8000)                   │
│  /health  /v1/positions  /v1/orders  /v1/signals        │
│  /v1/watchlist  /v1/risk  /v1/scheduler                 │
└──────────────────────┬──────────────────────────────────┘
                       │ DI Container (dependency-injector)
          ┌────────────┼────────────┐
          │            │            │
   APScheduler    Claude API   Kiwoom REST
   (4 KST jobs)  (분석 파이프) (주문 실행)
          │            │
          │     OpenBB (Step 1)
          │     → 가격/재무/뉴스 수집
          │
   ┌──────┴──────┐
PostgreSQL    Redis
(거래 기록)   (가격캐시/분산락)
```

**주요 컴포넌트:**

| 레이어 | 기술 | 역할 |
|--------|------|------|
| Presentation | FastAPI + Pydantic | REST API, 스키마 검증 |
| Application | Pure Python services | 신호 파싱, 리스크 가드, 파이프라인 |
| Infrastructure | Kiwoom, Claude, Redis, PostgreSQL | 외부 연동 |
| Scheduler | APScheduler (KST) | 장전/장중/장후 자동 실행 |

---

## 사전 요구사항

| 항목 | 버전 | 비고 |
|------|------|------|
| Docker Desktop | 4.x+ | docker compose v2 포함 |
| Python | 3.12+ | 개발/테스트용 (실행은 Docker) |
| 키움증권 계좌 | - | Open API 신청 필요 |
| Anthropic API Key | - | Claude API |
| Discord Webhook | - | 선택 사항 |

### 키움증권 API 신청

1. [한국투자증권 Open API](https://apiportal.koreainvestment.com) 접속
2. 회원가입 → 앱 등록 → `APP_KEY`, `SECRET_KEY` 발급
3. 계좌번호 10자리 확인 (앞 8자리 CANO + 뒤 2자리 상품코드)
4. 모의투자는 TR ID가 `VTTC*`, 실전투자는 `TTTC*`로 자동 선택

---

## 빠른 시작

### 1. 저장소 클론

```bash
git clone <repo-url>
cd auto_investing
```

### 2. 환경 변수 설정

```bash
cp .env.example .env
# .env 파일을 열어 API 키 입력 (아래 "환경 변수 설정" 참고)
```

### 3. Docker Compose 실행

```bash
# 빌드 + 실행 (처음 실행 시 이미지 빌드 포함, 약 3-5분)
docker compose up -d

# 로그 확인
docker compose logs -f api
```

### 4. DB 마이그레이션

```bash
docker compose exec api alembic upgrade head
```

정상 시작 로그 예시:
```
Starting auto-trading-engine …
TradingScheduler: 4 jobs registered
Scheduler started
Application startup complete.
```

### 5. API 동작 확인

```bash
curl http://localhost:8000/health
# {"status":"ok","db":"ok","redis":"ok","kiwoom":"paper","scheduler_running":true}
```

### 6. Swagger UI

브라우저에서 `http://localhost:8000/docs` 접속 → 모든 엔드포인트 확인 및 테스트 가능

---

## 환경 변수 설정

`.env.example`을 복사하여 `.env`를 작성합니다.

```bash
# ── 인증 ──────────────────────────────────────────────────
API_KEY=your-secret-api-key          # REST API X-API-Key 헤더값

# ── 키움증권 ──────────────────────────────────────────────
KIWOOM_APP_KEY=PSxxxxxxxxxxxxx       # Open API 앱 키
KIWOOM_SECRET_KEY=xxxxxxxxxxxxx      # Open API 시크릿 키
KIWOOM_ACCOUNT_NO=1234567890         # 계좌번호 10자리 (하이픈 없이)
KIWOOM_IS_PAPER=true                 # true=모의매매, false=실전매매

# ── Claude API ────────────────────────────────────────────
ANTHROPIC_API_KEY=sk-ant-xxxxx       # Anthropic API 키

# ── Discord (선택) ────────────────────────────────────────
DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/xxx/yyy

# ── 데이터베이스 ──────────────────────────────────────────
POSTGRES_DB=auto_investing
POSTGRES_USER=trading
POSTGRES_PASSWORD=strong-password-here
DATABASE_URL=postgresql+asyncpg://trading:strong-password-here@db:5432/auto_investing

# ── Redis ─────────────────────────────────────────────────
REDIS_PASSWORD=strong-redis-password
REDIS_URL=redis://:strong-redis-password@redis:6379/0

# ── 리스크 한도 ───────────────────────────────────────────
MAX_DAILY_LOSS_PCT=3.0              # 일일 최대 손실률 (%)
MAX_POSITION_COUNT=10               # 최대 동시 보유 종목 수
MAX_POSITION_SIZE_PCT=10.0          # 종목당 최대 투자 비중 (%)
MIN_CONFIDENCE=MEDIUM               # 최소 신호 신뢰도 (HIGH/MEDIUM-HIGH/MEDIUM/LOW)
```

**주의:** `.env` 파일은 절대 Git에 커밋하지 마세요. `.gitignore`에 이미 포함되어 있습니다.

---

## API 사용법

모든 `/v1/*` 엔드포인트는 `X-API-Key` 헤더 인증이 필요합니다.

```bash
# 공통 헤더 (예시에서 반복 생략)
-H "X-API-Key: your-api-key" \
-H "Content-Type: application/json"
```

### Health Check

```bash
# 시스템 상태 확인 (인증 불필요)
curl http://localhost:8000/health
```

```json
{
  "status": "ok",
  "db": "ok",
  "redis": "ok",
  "kiwoom": "paper",
  "scheduler_running": true
}
```

---

### 관심종목 (Watchlist)

스케줄러가 매일 아침 분석할 종목 목록입니다.

```bash
# 목록 조회
curl http://localhost:8000/v1/watchlist \
  -H "X-API-Key: your-api-key"

# 종목 추가 (6자리 KRX 종목코드)
curl -X POST http://localhost:8000/v1/watchlist \
  -H "X-API-Key: your-api-key" \
  -H "Content-Type: application/json" \
  -d '{"ticker": "005930", "name": "삼성전자"}'

# 종목 삭제
curl -X DELETE http://localhost:8000/v1/watchlist/005930 \
  -H "X-API-Key: your-api-key"
```

자주 쓰는 KRX 종목코드:

| 종목명 | 코드 |
|--------|------|
| 삼성전자 | 005930 |
| SK하이닉스 | 000660 |
| LG에너지솔루션 | 373220 |
| 현대차 | 005380 |
| NAVER | 035420 |
| 카카오 | 035720 |
| POSCO홀딩스 | 005490 |

---

### 종목 분석 (Signals)

Claude API의 `pro-securities-analyst` 7단계 파이프라인으로 분석합니다.

```bash
# 특정 종목 즉시 분석 (Claude API 호출 → 브로커 리포트 생성)
curl -X POST http://localhost:8000/v1/signals/analyze \
  -H "X-API-Key: your-api-key" \
  -H "Content-Type: application/json" \
  -d '{"ticker": "005930"}'
```

```json
{
  "id": "uuid",
  "ticker": "005930",
  "signal_type": "BUY",
  "confidence": "HIGH",
  "target_price": 90000.0,
  "current_price": 75000.0,
  "report_summary": "Samsung Electronics demonstrates strong...",
  "created_at": "2026-04-29T09:00:00Z"
}
```

```bash
# 관심종목 전체 최신 신호 조회
curl http://localhost:8000/v1/signals/latest \
  -H "X-API-Key: your-api-key"
```

**신뢰도(Confidence) 기준:**

| 값 | 의미 |
|----|------|
| `HIGH` | 매매 신호 강함 |
| `MEDIUM-HIGH` | 신호 신뢰도 높음 |
| `MEDIUM` | 기본 임계값 (MIN_CONFIDENCE 기본값) |
| `LOW` | 신호 약함 — 주문 실행 안 됨 |

---

### 주문 (Orders)

```bash
# 대기 중인 주문 목록
curl http://localhost:8000/v1/orders \
  -H "X-API-Key: your-api-key"

# 수동 주문 (모의 모드에서는 PAPER-* 주문 ID 반환)
curl -X POST http://localhost:8000/v1/orders \
  -H "X-API-Key: your-api-key" \
  -H "Content-Type: application/json" \
  -d '{
    "ticker": "005930",
    "side": "BUY",
    "order_type": "LIMIT",
    "quantity": 10,
    "price": 75000
  }'
```

| 필드 | 값 |
|------|----|
| `side` | `BUY` \| `SELL` |
| `order_type` | `LIMIT` \| `MARKET` |
| `price` | LIMIT 주문 시 필수, MARKET 주문 시 null |

---

### 포지션 (Positions)

```bash
# 전체 활성 포지션
curl http://localhost:8000/v1/positions \
  -H "X-API-Key: your-api-key"

# 특정 종목 포지션
curl http://localhost:8000/v1/positions/005930 \
  -H "X-API-Key: your-api-key"
```

---

### 리스크 관리 (Risk)

```bash
# 현재 리스크 상태 조회
curl http://localhost:8000/v1/risk/status \
  -H "X-API-Key: your-api-key"
```

```json
{
  "trading_halted": false,
  "daily_loss_krw": 150000.0,
  "open_position_count": 3,
  "halt_reason": null
}
```

```bash
# 거래 중단 해제 (일일 손실 한도 초과 후 수동 재개)
curl -X POST http://localhost:8000/v1/risk/resume \
  -H "X-API-Key: your-api-key"
```

---

### 스케줄러 제어 (Scheduler)

```bash
# 스케줄러 수동 시작
curl -X POST http://localhost:8000/v1/scheduler/start \
  -H "X-API-Key: your-api-key"

# 스케줄러 정지
curl -X POST http://localhost:8000/v1/scheduler/stop \
  -H "X-API-Key: your-api-key"
```

---

## 자동 스케줄러

APScheduler가 KST(한국 시간) 기준으로 4개 작업을 자동 실행합니다.

| 시간 (KST) | 작업 | 설명 |
|-----------|------|------|
| 08:50 | `prepare_market_open` | 장전 준비: 관심종목 로드, 시스템 체크 |
| 09:00 | `run_morning_cycle` | 장 시작: 관심종목 분석 → 신호 생성 → 주문 실행 |
| 매 30분 | `run_position_monitor` | 포지션 모니터링: 손절(-5%) / 익절(+15%) 경보 |
| 15:20 | `run_closing_routine` | 장 마감 정리 |

**모닝 사이클 흐름:**
```
09:00 시작
 └─ 관심종목 목록 로드
      └─ 각 종목 Claude 분석 (병렬 실행)
           └─ BUY/SELL 신호 파싱
                └─ 리스크 검증 통과 시 주문 실행
                     └─ Discord 알림
```

---

## OpenBB 설정

`pro-securities-analyst` 파이프라인의 **Step 1(데이터 수집)**에서 OpenBB를 사용합니다. OpenBB는 Claude가 분석 실행 시 내부적으로 호출합니다.

### OpenBB란?

[OpenBB](https://openbb.co)는 오픈소스 금융 데이터 플랫폼으로, 가격 데이터·재무제표·분석가 컨센서스·뉴스 등을 표준화된 API로 제공합니다.

### 설치

```bash
# Python 환경에 설치 (Claude가 실행되는 환경)
pip install openbb

# 또는 특정 데이터 제공자 포함
pip install "openbb[yfinance,fmp]"
```

### Claude 환경에서 OpenBB 사용 흐름

```
POST /v1/signals/analyze {"ticker": "005930"}
  └─ ClaudeAnalystAdapter.analyze("005930")
       └─ Claude API 호출 (pro-securities-analyst 시스템 프롬프트)
            └─ Step 1: openbb-data-fetcher 실행
                 │  openbb.equity.price.historical("005930", ...)
                 │  openbb.equity.fundamental.income("005930", ...)
                 │  openbb.equity.estimates.consensus("005930", ...)
                 └─ 수집된 데이터로 Steps 2~7 진행
```

### OpenBB 데이터 제공자 설정

OpenBB는 여러 데이터 제공자(provider)를 지원합니다. 무료로 사용할 수 있는 제공자:

| 제공자 | 한국 주식 | 무료 | 설정 방법 |
|--------|----------|------|----------|
| `yfinance` | 부분 지원 | 무료 | 별도 설정 불필요 |
| `fmp` | 미지원 | 무료 플랜 있음 | API 키 필요 |
| `intrinio` | 미지원 | 유료 | API 키 필요 |

```python
# OpenBB 허브 로그인 (선택 - 더 많은 데이터 접근)
from openbb import obb
obb.account.login(pat="your-personal-access-token")

# 한국 주식 가격 조회 예시
price = obb.equity.price.historical("005930", provider="yfinance")
```

### 한국 주식 데이터 한계 및 대안

OpenBB가 한국 주식(KRX) 데이터를 가져오지 못할 경우, `pro-securities-analyst`는 자동으로 **PARTIAL_ANALYSIS 모드**로 전환합니다:

1. **1차 폴백**: 웹 검색(naver.com/finance, finance.yahoo.com)으로 데이터 수집
2. **2차 폴백**: DART(전자공시시스템) 공시 데이터 활용
3. 모든 추정값은 `[Estimated-webfallback]` 태그 표시

```
# PARTIAL_ANALYSIS 모드 메시지 예시
OpenBB data unavailable for KRX:005930.
Falling back to web sources: 네이버금융, Yahoo Finance KR.
data_quality = "web-fallback"
```

**한국 주식 권장 설정:**

```bash
# yfinance는 .KS 접미사로 KOSPI 주식 조회 가능
# 종목코드 005930 → Yahoo Finance ticker: 005930.KS
pip install yfinance
```

---

## Paper Trading (모의 매매)

`KIWOOM_IS_PAPER=true` 설정 시 **네트워크 호출 없이** 모든 주문을 시뮬레이션합니다.

| 기능 | Paper 모드 | 실전 모드 |
|------|-----------|----------|
| 주문 실행 | `PAPER-{ticker}-{time}` ID 반환 | 실제 키움 API 호출 |
| 현재가 조회 | `100,000원` 고정값 반환 | 실시간 시세 조회 |
| 잔고 조회 | `10,000,000원` 고정값 반환 | 실제 잔고 조회 |
| 포지션 조회 | 빈 목록 반환 | 실제 보유 종목 |

### Paper 모드 smoke test

```bash
# docker compose 실행 후
python scripts/smoke_test.py

# 다른 주소/API 키 지정
python scripts/smoke_test.py --base-url http://localhost:8000 --api-key your-api-key
```

출력 예시:
```
Smoke test → http://localhost:8000
──────────────────────────────────
  [PASS] GET /health → 200
  [PASS]   status == ok
  [PASS] POST /v1/watchlist → 201
  [PASS] POST /v1/orders (paper BUY) → 201
  [PASS]   order_id starts with PAPER-  (PAPER-005930-031604452276)
  [PASS] GET /v1/risk/status → 200
  ...
Result: ALL PASSED ✓
```

### 실전 매매 전환

```bash
# .env 수정
KIWOOM_IS_PAPER=false

# 컨테이너 재시작
docker compose restart api
```

**실전 매매 전 체크리스트:**

- [ ] Paper 모드에서 최소 1주일 이상 검증 완료
- [ ] `MAX_DAILY_LOSS_PCT` 값을 보수적으로 설정 (권장: 1~2%)
- [ ] `MAX_POSITION_SIZE_PCT` 값 확인 (권장: 5~10%)
- [ ] `MIN_CONFIDENCE=HIGH` 또는 `MEDIUM-HIGH`로 설정
- [ ] Discord 알림 정상 수신 확인
- [ ] 키움 API 실전 계좌 연동 및 TR ID 확인

---

## 리스크 관리

5단계 순서로 검증합니다. 하나라도 실패하면 주문이 거부됩니다.

```
Rule 1: 거래 중단 여부 (TradingHaltedError)
Rule 2: 일일 손실 한도 초과 (DailyLossLimitError)
Rule 3: 최대 보유 종목 수 초과 (PositionLimitError)
Rule 4: 종목당 최대 투자금액 초과 (PositionSizeError)
Rule 5: 최소 신호 신뢰도 미달 (LowConfidenceError)
```

### 자동 거래 중단

일일 손실이 `MAX_DAILY_LOSS_PCT`를 초과하면 자동으로 거래가 중단됩니다:

```bash
# 거래 중단 상태 확인
curl http://localhost:8000/v1/risk/status -H "X-API-Key: your-key"
# {"trading_halted": true, "halt_reason": "일일 손실 한도 초과 (자동 중단)"}

# 수동으로 재개 (원인 파악 후 신중히)
curl -X POST http://localhost:8000/v1/risk/resume -H "X-API-Key: your-key"
```

---

## 개발 환경

### 로컬 개발 (Docker 없이)

```bash
# Python 가상환경 생성 (Python 3.12 필요)
python3.12 -m venv .venv
source .venv/bin/activate

# 의존성 설치
pip install -e ".[dev]"

# PostgreSQL, Redis는 별도 실행 또는 Docker만 사용
docker compose up -d db redis

# 환경 변수 (로컬 연결용으로 수정)
export DATABASE_URL=postgresql+asyncpg://trading:trading_dev_pw@localhost:5432/auto_investing
export REDIS_URL=redis://:redis_dev_pw@localhost:6379/0

# Alembic 마이그레이션
alembic upgrade head

# 서버 실행
uvicorn main:app --reload --port 8000
```

### 프로젝트 구조

```
auto_investing/
├── main.py                          # FastAPI 앱 진입점 + DI lifespan
├── alembic/                         # DB 마이그레이션
│   └── versions/001_initial_schema.py
├── docker/
│   └── Dockerfile
├── scripts/
│   └── smoke_test.py               # Paper trading E2E 검증
├── src/
│   ├── core/
│   │   └── settings.py             # pydantic-settings 설정
│   ├── domain/                     # 도메인 레이어 (순수 Python)
│   │   ├── entities/               # Trade, Position, Signal, ...
│   │   ├── repositories/           # Repository ABC 인터페이스
│   │   ├── value_objects/          # Ticker, Money
│   │   └── exceptions.py
│   ├── application/                # 애플리케이션 레이어
│   │   ├── ports/                  # BrokerPort, AnalystPort, ...
│   │   ├── services/               # SignalParser, RiskGuard, Pipeline
│   │   └── use_cases/              # AnalyzeStock, ExecuteTrade, MonitorPosition
│   ├── infrastructure/             # 외부 연동
│   │   ├── db/                     # SQLAlchemy ORM + 5개 Repository 구현체
│   │   ├── redis/                  # PriceCache, DistributedLock
│   │   ├── kiwoom/                 # REST API Adapter + Token Manager
│   │   ├── claude/                 # Claude API Adapter
│   │   ├── discord/                # Discord Webhook Notifier
│   │   └── scheduler/              # APScheduler TradingScheduler
│   └── presentation/               # FastAPI 레이어
│       ├── api/v1/                 # 7개 Router
│       ├── schemas/                # Pydantic 스키마
│       ├── auth.py                 # X-API-Key 인증
│       └── dependencies.py         # DI Container (TradingContainer)
└── tests/
    ├── conftest.py
    └── unit/
        ├── domain/test_entities.py
        └── application/
            ├── test_signal_parser.py
            ├── test_risk_guard.py
            ├── test_analyze_stock_uc.py
            └── test_execute_trade_uc.py
```

---

## 테스트

### 단위 테스트

```bash
# 가상환경 활성화 후
pytest tests/unit/ -v

# 커버리지 포함
pytest tests/unit/ --cov=src --cov-report=term-missing

# 특정 테스트만
pytest tests/unit/application/test_risk_guard.py -v
```

현재 커버리지: **49/49 테스트 통과** (도메인 엔티티, 서비스, 유즈케이스)

### Paper Trading E2E 테스트

```bash
# Docker 스택이 실행 중인 상태에서
python scripts/smoke_test.py

# 포트/키가 다른 경우
python scripts/smoke_test.py --base-url http://localhost:8000 --api-key dev-key
```

### Alembic 마이그레이션 검증

```bash
# 현재 마이그레이션 상태
docker compose exec api alembic current

# 최신으로 업그레이드
docker compose exec api alembic upgrade head

# 히스토리 확인
docker compose exec api alembic history
```

---

## 트러블슈팅

### API 응답이 401 Unauthorized

```bash
# X-API-Key 헤더 확인
curl http://localhost:8000/v1/orders -H "X-API-Key: $(grep API_KEY .env | cut -d= -f2)"
```

### 스케줄러가 실행되지 않음

```bash
docker compose logs api | grep -i "scheduler\|error"

# 수동으로 스케줄러 시작
curl -X POST http://localhost:8000/v1/scheduler/start -H "X-API-Key: your-key"
```

### Claude 분석이 빠르게 실패함 (API 키 없음)

```bash
# .env에 ANTHROPIC_API_KEY가 설정되어 있는지 확인
grep ANTHROPIC_API_KEY .env

# Paper 모드에서는 Claude 분석 없이 신호 생성 불가
# POST /v1/signals/analyze는 실제 API 키 필요
```

### OpenBB 데이터 수집 실패

Claude 분석 시 아래 메시지가 나타나면 PARTIAL_ANALYSIS 모드로 자동 전환됩니다:

```
OpenBB data unavailable. Falling back to web sources.
data_quality = "web-fallback"
```

해결 방법:
```bash
# Claude가 실행되는 환경에 OpenBB 설치
pip install openbb

# yfinance 별도 설치 (한국 주식 지원)
pip install yfinance

# OpenBB 버전 확인
python -c "import openbb; print(openbb.__version__)"
```

### DB 연결 실패

```bash
# DB 컨테이너 상태 확인
docker compose ps db

# DB 로그 확인
docker compose logs db

# 수동 연결 테스트
docker compose exec db psql -U trading -d auto_investing -c "\dt"
```

### Redis 연결 실패

```bash
docker compose exec redis redis-cli -a "$REDIS_PASSWORD" ping
# PONG 응답이 나와야 함
```

### 컨테이너 완전 초기화 (주의: 데이터 삭제)

```bash
docker compose down -v   # 볼륨 포함 삭제
docker compose up -d
docker compose exec api alembic upgrade head
```

---

## 라이선스

MIT License
