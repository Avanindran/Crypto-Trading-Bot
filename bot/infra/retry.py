"""
bot/infra/retry.py — Exponential backoff retry decorator.

Wraps API calls to handle transient network failures gracefully.
On failure, the bot skips the cycle rather than crashing.
"""
import time
import logging
import functools
from typing import Callable, TypeVar, Any

logger = logging.getLogger(__name__)

F = TypeVar("F", bound=Callable[..., Any])

_DEFAULT_MAX_RETRIES = 3
_DEFAULT_BASE_DELAY = 2.0   # seconds; doubles each retry


def with_retry(max_retries: int = _DEFAULT_MAX_RETRIES, base_delay: float = _DEFAULT_BASE_DELAY) -> Callable[[F], F]:
    """
    Decorator: retry a function up to max_retries times with exponential backoff.

    On exhaustion, logs the error and re-raises so the caller can decide to skip
    the cycle rather than crash the process.
    """
    def decorator(func: F) -> F:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            last_exc: Exception | None = None
            for attempt in range(1, max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except Exception as exc:
                    last_exc = exc
                    delay = base_delay * (2 ** (attempt - 1))
                    logger.warning(
                        "API call %s failed (attempt %d/%d): %s — retrying in %.1fs",
                        func.__name__, attempt, max_retries, exc, delay,
                    )
                    time.sleep(delay)
            logger.error("API call %s exhausted %d retries. Last error: %s", func.__name__, max_retries, last_exc)
            raise last_exc  # type: ignore[misc]
        return wrapper  # type: ignore[return-value]
    return decorator
