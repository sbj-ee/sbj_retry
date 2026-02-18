# sbj_retry

A simple retry utility for Python functions that may fail intermittently.

## Features

- Configurable maximum attempts
- Exponential backoff with optional jitter
- Maximum delay cap to prevent runaway waits
- Exception filtering (only retry on specific exceptions)
- On-retry callback for logging, metrics, or cleanup
- Usable as a decorator or function wrapper
- Logging instead of print (silent by default)
- Fully type-hinted

## Installation

```bash
pip install -e .
```

Or just copy `sbj_retry.py` into your project — no external dependencies.

## Usage

### As a decorator

```python
from sbj_retry import retry

@retry
def my_function():
    ...

@retry(max_attempts=10, delay=2, exceptions=(ConnectionError, TimeoutError))
def fetch_data(url):
    ...
```

### One-off calls with retry_call

```python
from sbj_retry import retry_call

# Pass function and its arguments directly
result = retry_call(fetch_data, "https://example.com", max_attempts=5)

# With keyword arguments
result = retry_call(fetch_data, "https://example.com", timeout=30, max_attempts=5)
```

### As a function wrapper

```python
from sbj_retry import retry

wrapped = retry(my_function, max_attempts=5)
result = wrapped("arg1", key="value")
```

## Parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| `func` | required | The function to retry |
| `max_attempts` | 20 | Maximum retry attempts |
| `delay` | 1 | Initial delay between attempts (seconds) |
| `backoff` | 2 | Multiplier for delay after each attempt. Set to 1 for fixed delay. |
| `max_delay` | None | Maximum delay in seconds. Prevents runaway waits with high backoff. |
| `jitter` | True | Add random jitter to delay to prevent thundering herd |
| `exceptions` | `(Exception,)` | Tuple of exception types to retry on. Others raise immediately. |
| `on_retry` | None | Callback invoked as `on_retry(attempt, exception, sleep_time)` after each failure. |

## Examples

### Exponential backoff with max delay cap

```python
@retry(max_attempts=10, delay=1, backoff=2, max_delay=30)
def call_api():
    # Delays: 1s, 2s, 4s, 8s, 16s, 30s, 30s, 30s, 30s
    ...
```

### Retry only on specific exceptions

```python
@retry(max_attempts=10, exceptions=(ConnectionError, TimeoutError))
def fetch_data(url):
    return requests.get(url).json()

# ConnectionError and TimeoutError will be retried
# TypeError, ValueError, etc. raise immediately
```

### On-retry callback

```python
def log_retry(attempt, exception, sleep_time):
    print(f"Attempt {attempt} failed: {exception}. Retrying in {sleep_time:.1f}s")

@retry(max_attempts=5, on_retry=log_retry)
def unstable_operation():
    ...
```

### Fixed delay (no backoff)

```python
@retry(max_attempts=5, delay=2, backoff=1, jitter=False)
def poll_status():
    ...
```

### Enable logging

```python
import logging
logging.basicConfig(level=logging.INFO)

# Now retry will log: "Attempt 1 of 5", "Attempt 2 of 5", etc.
```

## Requirements

- Python 3.10+
