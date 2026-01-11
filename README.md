# sbj_retry

A simple retry utility for Python functions that may fail intermittently.

## Features

- Configurable maximum attempts
- Delay between retries
- Progress output showing attempt number
- Preserves and re-raises the last exception on final failure

## Usage

```python
from sbj_retry import retry

# Basic usage
result = retry(my_function)

# With custom settings
result = retry(my_function, max_attempts=10, delay=2)

# With functions that take arguments
result = retry(lambda: fetch_data("https://example.com"))
```

## Parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| `func` | required | The function to retry |
| `max_attempts` | 20 | Maximum retry attempts |
| `delay` | 1 | Seconds between attempts |

## Example

```python
def unstable_operation():
    if random.random() < 0.7:
        raise ValueError("Operation failed!")
    return "Success!"

try:
    result = retry(unstable_operation)
    print(f"Result: {result}")
except ValueError as e:
    print(f"All attempts failed: {e}")
```

## Installation

```bash
python3 -m venv .venv
source .venv/bin/activate
# No external dependencies required
```

## Requirements

- Python 3.x
