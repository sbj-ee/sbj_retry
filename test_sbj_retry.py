"""Tests for sbj_retry module."""

import logging
import pytest
from unittest.mock import patch, MagicMock, call
from sbj_retry import retry, retry_call


class TestRetryAsWrapper:
    """Tests for retry used as a function wrapper."""

    def test_succeeds_on_first_attempt(self):
        """Function that succeeds immediately should return result."""
        func = MagicMock(return_value="success")

        result = retry(func, max_attempts=3, delay=0)()

        assert result == "success"
        assert func.call_count == 1

    def test_succeeds_after_failures(self):
        """Function that fails then succeeds should return result."""
        func = MagicMock(side_effect=[ValueError("fail"), ValueError("fail"), "success"])

        result = retry(func, max_attempts=5, delay=0)()

        assert result == "success"
        assert func.call_count == 3

    def test_raises_after_max_attempts(self):
        """Function that always fails should raise the last exception."""
        func = MagicMock(side_effect=ValueError("always fails"))

        with pytest.raises(ValueError, match="always fails"):
            retry(func, max_attempts=3, delay=0)()

        assert func.call_count == 3

    def test_default_max_attempts(self):
        """Default max_attempts should be 20."""
        func = MagicMock(side_effect=ValueError("fail"))

        with pytest.raises(ValueError):
            retry(func, delay=0)()

        assert func.call_count == 20

    def test_preserves_return_value_type(self):
        """Should preserve the return value type."""
        func_dict = MagicMock(return_value={"key": "value"})
        assert retry(func_dict, max_attempts=1, delay=0)() == {"key": "value"}

        func_list = MagicMock(return_value=[1, 2, 3])
        assert retry(func_list, max_attempts=1, delay=0)() == [1, 2, 3]

        func_none = MagicMock(return_value=None)
        assert retry(func_none, max_attempts=1, delay=0)() is None

    def test_single_attempt(self):
        """Should work with max_attempts=1."""
        func_success = MagicMock(return_value="ok")
        assert retry(func_success, max_attempts=1, delay=0)() == "ok"

        func_fail = MagicMock(side_effect=RuntimeError("error"))
        with pytest.raises(RuntimeError):
            retry(func_fail, max_attempts=1, delay=0)()

    def test_different_exception_types(self):
        """Should handle different exception types."""
        func = MagicMock(side_effect=ConnectionError("network error"))

        with pytest.raises(ConnectionError, match="network error"):
            retry(func, max_attempts=2, delay=0)()

    def test_with_arguments(self):
        """Wrapped function should pass through arguments."""
        func = MagicMock(side_effect=[ValueError("fail"), "result"])

        wrapped = retry(func, max_attempts=3, delay=0)
        result = wrapped("arg1", key="val")

        assert result == "result"
        func.assert_called_with("arg1", key="val")


class TestDelay:
    """Tests for delay and backoff behavior."""

    def test_fixed_delay(self):
        """backoff=1 should give fixed delay between attempts."""
        func = MagicMock(side_effect=[ValueError("fail"), "success"])

        with patch("sbj_retry.time.sleep") as mock_sleep:
            retry(func, max_attempts=3, delay=2, backoff=1, jitter=False)()

        mock_sleep.assert_called_once_with(2)

    def test_no_delay_after_last_attempt(self):
        """Should not sleep after the final failed attempt."""
        func = MagicMock(side_effect=ValueError("fail"))

        with patch("sbj_retry.time.sleep") as mock_sleep:
            with pytest.raises(ValueError):
                retry(func, max_attempts=3, delay=1, backoff=1, jitter=False)()

        assert mock_sleep.call_count == 2

    def test_exponential_backoff(self):
        """Delay should increase exponentially with backoff multiplier."""
        func = MagicMock(side_effect=[ValueError("f"), ValueError("f"), ValueError("f"), "ok"])

        with patch("sbj_retry.time.sleep") as mock_sleep:
            retry(func, max_attempts=5, delay=1, backoff=2, jitter=False)()

        # delay=1, then 1*2=2, then 2*2=4
        mock_sleep.assert_has_calls([call(1), call(2), call(4)])
        assert mock_sleep.call_count == 3

    def test_jitter_adds_randomness(self):
        """Jitter should add random time to the delay."""
        func = MagicMock(side_effect=[ValueError("fail"), "ok"])

        with patch("sbj_retry.time.sleep") as mock_sleep, \
             patch("sbj_retry.random.uniform", return_value=0.5):
            retry(func, max_attempts=3, delay=1, backoff=1, jitter=True)()

        # delay=1 + jitter uniform(0, 1)=0.5 -> 1.5
        mock_sleep.assert_called_once_with(1.5)

    def test_jitter_disabled(self):
        """jitter=False should give exact delay values."""
        func = MagicMock(side_effect=[ValueError("fail"), "ok"])

        with patch("sbj_retry.time.sleep") as mock_sleep:
            retry(func, max_attempts=3, delay=1, backoff=1, jitter=False)()

        mock_sleep.assert_called_once_with(1)


class TestMaxDelay:
    """Tests for the max_delay parameter."""

    def test_caps_sleep_time(self):
        """max_delay should cap the sleep time."""
        func = MagicMock(side_effect=[ValueError("f"), ValueError("f"), ValueError("f"), "ok"])

        with patch("sbj_retry.time.sleep") as mock_sleep:
            retry(func, max_attempts=5, delay=1, backoff=10, max_delay=5, jitter=False)()

        # delay=1, then 1*10=10 capped to 5, then 10*10=100 capped to 5
        mock_sleep.assert_has_calls([call(1), call(5), call(5)])
        assert mock_sleep.call_count == 3

    def test_caps_with_jitter(self):
        """max_delay should cap even after jitter is added."""
        func = MagicMock(side_effect=[ValueError("fail"), "ok"])

        with patch("sbj_retry.time.sleep") as mock_sleep, \
             patch("sbj_retry.random.uniform", return_value=100):
            retry(func, max_attempts=3, delay=1, backoff=1, jitter=True, max_delay=3)()

        # delay=1 + jitter=100 -> 101, capped to 3
        mock_sleep.assert_called_once_with(3)

    def test_no_cap_by_default(self):
        """Without max_delay, delay should grow uncapped."""
        func = MagicMock(side_effect=[ValueError("f"), ValueError("f"), "ok"])

        with patch("sbj_retry.time.sleep") as mock_sleep:
            retry(func, max_attempts=5, delay=1, backoff=100, jitter=False)()

        # delay=1, then 1*100=100
        mock_sleep.assert_has_calls([call(1), call(100)])


class TestOnRetry:
    """Tests for the on_retry callback."""

    def test_callback_called_on_failure(self):
        """on_retry should be called after each failed attempt."""
        callback = MagicMock()
        func = MagicMock(side_effect=[ValueError("e1"), ValueError("e2"), "ok"])

        with patch("sbj_retry.time.sleep"):
            retry(func, max_attempts=5, delay=1, backoff=1, jitter=False, on_retry=callback)()

        assert callback.call_count == 2
        # First call: attempt 1, exception, sleep_time
        assert callback.call_args_list[0][0][0] == 1
        assert isinstance(callback.call_args_list[0][0][1], ValueError)
        assert callback.call_args_list[0][0][2] == 1
        # Second call: attempt 2
        assert callback.call_args_list[1][0][0] == 2

    def test_callback_not_called_on_success(self):
        """on_retry should not be called when the first attempt succeeds."""
        callback = MagicMock()
        func = MagicMock(return_value="ok")

        retry(func, max_attempts=3, delay=0, on_retry=callback)()

        callback.assert_not_called()

    def test_callback_not_called_after_last_attempt(self):
        """on_retry should not be called after the final failed attempt."""
        callback = MagicMock()
        func = MagicMock(side_effect=ValueError("fail"))

        with patch("sbj_retry.time.sleep"):
            with pytest.raises(ValueError):
                retry(func, max_attempts=2, delay=1, backoff=1, jitter=False, on_retry=callback)()

        # Only called once (after attempt 1, not after attempt 2)
        assert callback.call_count == 1

    def test_no_callback_by_default(self):
        """Should work fine without on_retry."""
        func = MagicMock(side_effect=[ValueError("fail"), "ok"])

        result = retry(func, max_attempts=3, delay=0)()

        assert result == "ok"


class TestExceptionFiltering:
    """Tests for the exceptions parameter."""

    def test_retries_on_matching_exception(self):
        """Should retry when exception matches the filter."""
        func = MagicMock(side_effect=[ConnectionError("fail"), "ok"])

        result = retry(func, max_attempts=3, delay=0, exceptions=(ConnectionError,))()

        assert result == "ok"
        assert func.call_count == 2

    def test_raises_immediately_on_non_matching_exception(self):
        """Should not retry when exception doesn't match the filter."""
        func = MagicMock(side_effect=TypeError("wrong type"))

        with pytest.raises(TypeError, match="wrong type"):
            retry(func, max_attempts=5, delay=0, exceptions=(ConnectionError,))()

        assert func.call_count == 1

    def test_multiple_exception_types(self):
        """Should retry on any of the specified exception types."""
        func = MagicMock(side_effect=[
            ConnectionError("net"),
            TimeoutError("timeout"),
            "ok"
        ])

        result = retry(func, max_attempts=5, delay=0, exceptions=(ConnectionError, TimeoutError))()

        assert result == "ok"
        assert func.call_count == 3

    def test_default_catches_all_exceptions(self):
        """Default exceptions=(Exception,) should catch all standard exceptions."""
        func = MagicMock(side_effect=[ValueError("v"), TypeError("t"), "ok"])

        result = retry(func, max_attempts=5, delay=0)()

        assert result == "ok"
        assert func.call_count == 3


class TestDecoratorUsage:
    """Tests for using retry as a decorator."""

    def test_decorator_no_args(self):
        """@retry should work without parentheses."""
        call_count = 0

        @retry
        def flaky():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ValueError("not yet")
            return "done"

        with patch("sbj_retry.time.sleep"):
            result = flaky()

        assert result == "done"
        assert call_count == 3

    def test_decorator_with_args(self):
        """@retry(max_attempts=3) should work with keyword arguments."""
        call_count = 0

        @retry(max_attempts=3, delay=0)
        def flaky():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise ValueError("not yet")
            return "done"

        result = flaky()

        assert result == "done"
        assert call_count == 2

    def test_decorator_preserves_function_name(self):
        """Decorated function should preserve original name."""
        @retry
        def my_function():
            pass

        assert my_function.__name__ == "my_function"

    def test_decorator_passes_arguments(self):
        """Decorated function should accept and pass arguments."""
        @retry(max_attempts=2, delay=0)
        def add(a, b):
            return a + b

        assert add(2, 3) == 5

    def test_decorator_with_exception_filter(self):
        """Decorator with exceptions parameter should filter correctly."""
        @retry(max_attempts=5, delay=0, exceptions=(ConnectionError,))
        def flaky():
            raise TypeError("unhandled")

        with pytest.raises(TypeError):
            flaky()


class TestRetryCall:
    """Tests for the retry_call convenience function."""

    def test_basic_call(self):
        """retry_call should execute the function and return result."""
        func = MagicMock(return_value="ok")

        result = retry_call(func, max_attempts=3, delay=0)

        assert result == "ok"
        func.assert_called_once()

    def test_passes_positional_args(self):
        """retry_call should pass positional args to the function."""
        func = MagicMock(side_effect=[ValueError("fail"), "result"])

        result = retry_call(func, "arg1", "arg2", max_attempts=3, delay=0)

        assert result == "result"
        func.assert_called_with("arg1", "arg2")

    def test_passes_keyword_args(self):
        """retry_call should pass keyword args to the function."""
        def func(name, greeting="hello"):
            return f"{greeting} {name}"

        result = retry_call(func, "world", greeting="hi", max_attempts=1, delay=0)

        assert result == "hi world"

    def test_retries_on_failure(self):
        """retry_call should retry on failure."""
        func = MagicMock(side_effect=[ValueError("fail"), ValueError("fail"), "ok"])

        result = retry_call(func, max_attempts=5, delay=0)

        assert result == "ok"
        assert func.call_count == 3

    def test_raises_after_max_attempts(self):
        """retry_call should raise after all attempts exhausted."""
        func = MagicMock(side_effect=ValueError("fail"))

        with pytest.raises(ValueError, match="fail"):
            retry_call(func, max_attempts=3, delay=0)

        assert func.call_count == 3

    def test_with_all_options(self):
        """retry_call should pass through all retry options."""
        callback = MagicMock()
        func = MagicMock(side_effect=[ConnectionError("fail"), "ok"])

        with patch("sbj_retry.time.sleep") as mock_sleep:
            result = retry_call(
                func,
                max_attempts=5,
                delay=1,
                backoff=2,
                max_delay=10,
                jitter=False,
                exceptions=(ConnectionError,),
                on_retry=callback,
            )

        assert result == "ok"
        mock_sleep.assert_called_once_with(1)
        callback.assert_called_once()


class TestLogging:
    """Tests for logging output."""

    def test_logs_attempt_number(self, caplog):
        """Should log attempt numbers instead of printing."""
        func = MagicMock(side_effect=[ValueError("fail"), "ok"])

        with caplog.at_level(logging.INFO, logger="sbj_retry"):
            retry(func, max_attempts=3, delay=0)()

        assert "Attempt 1 of 3" in caplog.text
        assert "Attempt 2 of 3" in caplog.text

    def test_no_output_without_logging_config(self, capsys):
        """Should not print to stdout."""
        func = MagicMock(side_effect=[ValueError("fail"), "ok"])

        retry(func, max_attempts=3, delay=0)()

        captured = capsys.readouterr()
        assert captured.out == ""
