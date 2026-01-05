"""Tests for sbj_retry module."""

import pytest
from unittest.mock import patch, MagicMock
from sbj_retry import retry


class TestRetry:
    """Tests for the retry function."""

    def test_succeeds_on_first_attempt(self):
        """Function that succeeds immediately should return result."""
        func = MagicMock(return_value="success")

        result = retry(func, max_attempts=3, delay=0)

        assert result == "success"
        assert func.call_count == 1

    def test_succeeds_after_failures(self):
        """Function that fails then succeeds should return result."""
        func = MagicMock(side_effect=[ValueError("fail"), ValueError("fail"), "success"])

        result = retry(func, max_attempts=5, delay=0)

        assert result == "success"
        assert func.call_count == 3

    def test_raises_after_max_attempts(self):
        """Function that always fails should raise the last exception."""
        func = MagicMock(side_effect=ValueError("always fails"))

        with pytest.raises(ValueError, match="always fails"):
            retry(func, max_attempts=3, delay=0)

        assert func.call_count == 3

    def test_default_max_attempts(self):
        """Default max_attempts should be 20."""
        func = MagicMock(side_effect=ValueError("fail"))

        with pytest.raises(ValueError):
            retry(func, delay=0)

        assert func.call_count == 20

    def test_delay_between_attempts(self):
        """Should sleep between failed attempts."""
        func = MagicMock(side_effect=[ValueError("fail"), "success"])

        with patch('sbj_retry.time.sleep') as mock_sleep:
            result = retry(func, max_attempts=3, delay=2)

        assert result == "success"
        mock_sleep.assert_called_once_with(2)

    def test_no_delay_after_last_attempt(self):
        """Should not sleep after the final failed attempt."""
        func = MagicMock(side_effect=ValueError("fail"))

        with patch('sbj_retry.time.sleep') as mock_sleep:
            with pytest.raises(ValueError):
                retry(func, max_attempts=3, delay=1)

        # Should sleep twice (after attempt 1 and 2), not after attempt 3
        assert mock_sleep.call_count == 2

    def test_different_exception_types(self):
        """Should handle different exception types."""
        func = MagicMock(side_effect=ConnectionError("network error"))

        with pytest.raises(ConnectionError, match="network error"):
            retry(func, max_attempts=2, delay=0)

    def test_with_lambda(self):
        """Should work with lambda functions."""
        counter = {"count": 0}

        def flaky_func(x):
            counter["count"] += 1
            if counter["count"] < 3:
                raise ValueError("not yet")
            return x * 2

        result = retry(lambda: flaky_func(5), max_attempts=5, delay=0)

        assert result == 10
        assert counter["count"] == 3

    def test_preserves_return_value_type(self):
        """Should preserve the return value type."""
        # Test with dict
        func_dict = MagicMock(return_value={"key": "value"})
        assert retry(func_dict, max_attempts=1, delay=0) == {"key": "value"}

        # Test with list
        func_list = MagicMock(return_value=[1, 2, 3])
        assert retry(func_list, max_attempts=1, delay=0) == [1, 2, 3]

        # Test with None
        func_none = MagicMock(return_value=None)
        assert retry(func_none, max_attempts=1, delay=0) is None

    def test_single_attempt(self):
        """Should work with max_attempts=1."""
        func_success = MagicMock(return_value="ok")
        assert retry(func_success, max_attempts=1, delay=0) == "ok"

        func_fail = MagicMock(side_effect=RuntimeError("error"))
        with pytest.raises(RuntimeError):
            retry(func_fail, max_attempts=1, delay=0)
