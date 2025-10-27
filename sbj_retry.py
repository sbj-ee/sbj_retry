import time
import random

# Modified retry function to display attempt number
def retry(func, max_attempts=20, delay=1):
    """
    Retry a function up to max_attempts times with a delay between attempts.

    Args:
        func: The function to retry
        max_attempts: Maximum number of attempts (default: 5)
        delay: Delay between attempts in seconds (default: 1)

    Returns:
        The result of the function if successful

    Raises:
        The last exception if all attempts fail
    """
    last_exception = None

    for attempt in range(max_attempts):
        print(f"Attempt {attempt + 1} of {max_attempts}")
        try:
            return func()
        except Exception as e:
            last_exception = e
            if attempt < max_attempts - 1:
                time.sleep(delay)

    raise last_exception

# Example function that randomly fails
def unstable_operation():
    if random.random() < 0.7:  # 70% chance of failure
        raise ValueError("Operation failed!")
    return "Success!"

# Using the retry function
try:
    result = retry(unstable_operation)
    print(f"Operation succeeded with result: {result}")
except ValueError as e:
    print(f"All attempts failed with error: {e}")

# Example with a different function that takes arguments
def fetch_data(url):
    if random.random() < 0.8:  # 80% chance of failure
        raise ConnectionError("Failed to connect to " + url)
    return f"Data from {url}"

# Using retry with a function that takes arguments
try:
    result = retry(lambda: fetch_data("https://example.com"))
    print(f"Fetch succeeded with result: {result}")
except ConnectionError as e:
    print(f"All attempts failed with error: {e}")
