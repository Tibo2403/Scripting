"""Default upstream, route profiles and scoring parameters."""

UPSTREAM_BASE = "http://127.0.0.1:4000/v1"


ROUTE_CANDIDATES = {
    "codex-risk-adjusted": ["gemini-flash-direct", "gemini-pro-direct", "codex-qwen-local"],
    "codex-auto": ["gemini-flash-direct", "gemini-pro-direct", "codex-qwen-local"],
    "codex-light": ["gemini-flash-direct", "codex-qwen-local"],
    "codex-default": ["codex-qwen-local", "gemini-flash-direct", "gemini-pro-direct"],
    "codex-long": ["codex-qwen-local", "gemini-pro-direct"],
    "codex-deep": ["codex-qwen-local", "gemini-pro-direct"],
    "codex-no-openai": ["codex-qwen-local", "gemini-flash-direct", "gemini-pro-direct"],
    "codex-cheap": ["gemini-flash-direct", "codex-qwen-local"],
    "codex-strong": ["codex-qwen-local", "gemini-pro-direct"],
}


MODEL_PROFILE = {
    "gemini-flash-direct": {
        "cost": 0.20,
        "total_latency": 3500.0,
        "ttft": 900.0,
        "tokens_per_second": 45.0,
        "tpm_limit": 250_000,
        "max_in_flight": 2,
    },
    "gemini-pro-direct": {
        "cost": 0.45,
        "total_latency": 6500.0,
        "ttft": 1600.0,
        "tokens_per_second": 28.0,
        "tpm_limit": 100_000,
        "max_in_flight": 1,
    },
    "codex-qwen-local": {
        "cost": 0.02,
        "total_latency": 5500.0,
        "ttft": 1400.0,
        "tokens_per_second": 18.0,
        "tpm_limit": 1_000_000,
        "max_in_flight": 1,
    },
    "codex-local-only": {
        "cost": 0.02,
        "total_latency": 5500.0,
        "ttft": 1400.0,
        "tokens_per_second": 18.0,
        "tpm_limit": 1_000_000,
        "max_in_flight": 1,
    },
}


SOFT_WEIGHTS = {
    "cost": 0.10,
    "ttft": 0.22,
    "total_latency": 0.14,
    "tokens_per_second": 0.14,
    "error": 0.25,
    "token_pressure": 0.08,
    "queue": 0.07,
}
TEMPERATURE = 0.30
EWMA_ALPHA = 0.25
RETRYABLE_STATUSES = {404, 408, 409, 429, 500, 502, 503, 504}
HARD_LIMIT_STATUS_SECONDS = {
    401: 3600,
    403: 3600,
    404: 1800,
    429: 300,
}
STREAM_TOKEN_BYTES = 24
