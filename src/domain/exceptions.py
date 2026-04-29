"""Domain exception hierarchy — all trading errors root from TradingError."""


class TradingError(Exception):
    """Base exception for all trading domain errors."""


# ── Risk Guard exceptions ──────────────────────────────────

class RiskGuardError(TradingError):
    """Base for all risk validation failures."""


class TradingHaltedError(RiskGuardError):
    """Trading is halted (previous halt not cleared)."""


class DailyLossLimitError(RiskGuardError):
    """Daily loss limit has been reached — triggers automatic halt."""


class PositionLimitError(RiskGuardError):
    """Maximum concurrent position count exceeded."""


class PositionSizeError(RiskGuardError):
    """Single position exceeds maximum allowed investment amount."""


class LowConfidenceError(RiskGuardError):
    """Signal confidence is below the configured minimum threshold."""


# ── Broker exceptions ──────────────────────────────────────

class BrokerError(TradingError):
    """Base for all broker / exchange adapter errors."""


class KiwoomAuthError(BrokerError):
    """Kiwoom OAuth token issuance or refresh failed."""


class KiwoomOrderError(BrokerError):
    """Order placement rejected by Kiwoom REST API."""


class KiwoomRateLimitError(BrokerError):
    """Kiwoom API rate limit exceeded."""


# ── Analysis exceptions ────────────────────────────────────

class AnalysisError(TradingError):
    """Base for analyst adapter errors."""


class SignalParseError(AnalysisError):
    """Could not extract a valid trading signal from analyst report."""


# ── Order lifecycle exceptions ─────────────────────────────

class DuplicateOrderError(TradingError):
    """An order for this ticker was already placed today (idempotency guard)."""


class LockAcquisitionError(TradingError):
    """Could not acquire distributed lock — concurrent operation in progress."""
