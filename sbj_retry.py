from __future__ import annotations

import time
import random
import logging
import functools
from typing import Any, Callable, TypeVar

logger = logging.getLogger(__name__)

T = TypeVar("T")

# Sentinel to distinguish "not provided" from None
_UNSET = object()


def retry(
    func: Callable[..., T] | None = None,
    *,
    max_attempts: int = 20,
    delay: float = 1,
    backoff: float = 2,
    max_delay: float | None = None,
    jitter: bool = True,
    exceptions: tuple[type[BaseException], ...] = (Exception,),
    on_retry: Callable[[int, BaseException, float], Any] | None = None,
) -> Callable[..., T]:
    """
    Retry a function up to max_attempts times with exponential backoff.

    Can be used as a decorator or a function wrapper:

        @retry
        def my_func(): ...

        @retry(max_attempts=5, delay=2)
        def my_func(): ...

        result = retry(my_func, max_attempts=5)()

    For one-off calls, use retry_call() instead:

        result = retry_call(my_func, max_attempts=5)

    Args:
        func: The function to retry (or None when used as decorator with arguments)
        max_attempts: Maximum number of attempts (default: 20)
        delay: Initial delay between attempts in seconds (default: 1)
        backoff: Multiplier for delay after each attempt (default: 2). Set to 1 for fixed delay.
        max_delay: Maximum delay in seconds (default: None, no cap). Prevents
                   runaway waits with high backoff values.
        jitter: Add random jitter to delay to prevent thundering herd (default: True)
        exceptions: Tuple of exception types to retry on (default: (Exception,)).
                    Exceptions not in this tuple are raised immediately.
        on_retry: Optional callback invoked after each failed attempt with
                  (attempt_number, exception, next_sleep_time). Called before sleeping.

    Returns:
        Decorated function that will retry on failure

    Raises:
        The last exception if all attempts fail, or immediately for non-retryable exceptions
    """
    def decorator(fn: Callable[..., T]) -> Callable[..., T]:
        @functools.wraps(fn)
        def wrapper(*args: Any, **kwargs: Any) -> T:
            last_exception: BaseException | None = None
            current_delay = delay

            for attempt in range(max_attempts):
                logger.info("Attempt %d of %d", attempt + 1, max_attempts)
                try:
                    return fn(*args, **kwargs)
                except exceptions as e:
                    last_exception = e
                    if attempt < max_attempts - 1:
                        sleep_time = current_delay
                        if jitter:
                            sleep_time += random.uniform(0, current_delay)
                        if max_delay is not None:
                            sleep_time = min(sleep_time, max_delay)
                        if on_retry is not None:
                            on_retry(attempt + 1, e, sleep_time)
                        time.sleep(sleep_time)
                        current_delay *= backoff

            raise last_exception  # type: ignore[misc]

        return wrapper

    if func is not None:
        return decorator(func)

    return decorator  # type: ignore[return-value]


def retry_call(
    func: Callable[..., T],
    *args: Any,
    max_attempts: int = 20,
    delay: float = 1,
    backoff: float = 2,
    max_delay: float | None = None,
    jitter: bool = True,
    exceptions: tuple[type[BaseException], ...] = (Exception,),
    on_retry: Callable[[int, BaseException, float], Any] | None = None,
    **kwargs: Any,
) -> T:
    """
    Execute a function with retry logic. Convenience wrapper for one-off calls.

        result = retry_call(fetch_data, "https://example.com", max_attempts=5)

    Args:
        func: The function to call
        *args: Positional arguments passed to func
        max_attempts: Maximum number of attempts (default: 20)
        delay: Initial delay between attempts in seconds (default: 1)
        backoff: Multiplier for delay after each attempt (default: 2)
        max_delay: Maximum delay in seconds (default: None, no cap)
        jitter: Add random jitter to delay (default: True)
        exceptions: Tuple of exception types to retry on (default: (Exception,))
        on_retry: Optional callback invoked after each failed attempt
        **kwargs: Keyword arguments passed to func

    Returns:
        The result of func if successful

    Raises:
        The last exception if all attempts fail
    """
    wrapped = retry(
        max_attempts=max_attempts,
        delay=delay,
        backoff=backoff,
        max_delay=max_delay,
        jitter=jitter,
        exceptions=exceptions,
        on_retry=on_retry,
    )(func)
    return wrapped(*args, **kwargs)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    # Example: decorator with on_retry callback
    def log_retry(attempt: int, exc: BaseException, sleep_time: float) -> None:
        print(f"  Retry callback: attempt {attempt} failed ({exc}), sleeping {sleep_time:.2f}s")

    @retry(max_attempts=10, delay=0.1, max_delay=2, on_retry=log_retry)
    def unstable_operation():
        if random.random() < 0.7:
            raise ValueError("Operation failed!")
        return "Success!"

    try:
        result = unstable_operation()
        print(f"Operation succeeded: {result}")
    except ValueError as e:
        print(f"All attempts failed: {e}")

    # Example: retry_call for one-off usage
    def fetch_data(url: str) -> str:
        if random.random() < 0.8:
            raise ConnectionError("Failed to connect to " + url)
        return f"Data from {url}"

    try:
        result = retry_call(
            fetch_data, "https://example.com",
            max_attempts=10, delay=0.1, exceptions=(ConnectionError,),
        )
        print(f"Fetch succeeded: {result}")
    except ConnectionError as e:
        print(f"All attempts failed: {e}")
