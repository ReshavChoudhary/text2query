
import sys
import os
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import httpx
from openai import APITimeoutError, AuthenticationError, RateLimitError

from chain.llm_client import generate_sql, _extract_wait_seconds

FAKE_REQUEST = httpx.Request("POST", "https://api.groq.com/openai/v1/chat/completions")

def _mock_response(text, prompt_tokens=120, completion_tokens=15, total_tokens=135):
    message = MagicMock()
    message.content = text
    choice = MagicMock()
    choice.message = message
    usage = MagicMock()
    usage.prompt_tokens = prompt_tokens
    usage.completion_tokens = completion_tokens
    usage.total_tokens = total_tokens
    response = MagicMock()
    response.choices = [choice]
    response.usage = usage
    return response

def test_successful_call_returns_text_and_token_counts():
    with patch("chain.llm_client.OpenAI") as MockOpenAI:
        MockOpenAI.return_value.chat.completions.create.return_value = _mock_response(
            "SELECT * FROM customers;"
        )
        result = generate_sql("a prompt", "fake-key", "openai/gpt-oss-120b", "https://api.groq.com/openai/v1")
        assert result["text"] == "SELECT * FROM customers;"
        assert result["prompt_tokens"] == 120
        assert result["completion_tokens"] == 15
        assert result["total_tokens"] == 135

def test_timeout_raises_timeout_error():
    with patch("chain.llm_client.OpenAI") as MockOpenAI:
        MockOpenAI.return_value.chat.completions.create.side_effect = APITimeoutError(
            request=FAKE_REQUEST
        )
        try:
            generate_sql("a prompt", "fake-key", "model", "url")
            assert False, "expected TimeoutError"
        except TimeoutError:
            pass

def test_auth_error_raises_value_error_and_hides_key():
    with patch("chain.llm_client.OpenAI") as MockOpenAI:
        fake_response = httpx.Response(
            401, request=FAKE_REQUEST, json={"error": {"message": "invalid api key sk-secret-abc123"}}
        )
        MockOpenAI.return_value.chat.completions.create.side_effect = AuthenticationError(
            message="invalid api key sk-secret-abc123", response=fake_response, body=None
        )
        try:
            generate_sql("a prompt", "sk-secret-abc123", "model", "url")
            assert False, "expected ValueError"
        except ValueError as err:
            assert "sk-secret-abc123" not in str(err), "API key leaked into error message!"

def test_empty_reply_raises_value_error():
    with patch("chain.llm_client.OpenAI") as MockOpenAI:
        MockOpenAI.return_value.chat.completions.create.return_value = _mock_response("   ")
        try:
            generate_sql("a prompt", "fake-key", "model", "url")
            assert False, "expected ValueError"
        except ValueError:
            pass

def _fake_rate_limit_error(wait_text="1.5s"):
    fake_response = httpx.Response(
        429, request=FAKE_REQUEST,
        json={"error": {"message": f"Rate limit reached. Please try again in {wait_text}"}},
    )
    return RateLimitError(
        message=f"Rate limit reached. Please try again in {wait_text}",
        response=fake_response, body=None,
    )

def test_rate_limit_retries_then_succeeds():
    with patch("chain.llm_client.OpenAI") as MockOpenAI, patch("chain.llm_client.time.sleep") as mock_sleep:
        MockOpenAI.return_value.chat.completions.create.side_effect = [
            _fake_rate_limit_error("0.01s"),
            _mock_response("SELECT * FROM customers;"),
        ]
        result = generate_sql("a prompt", "fake-key", "model", "url")
        assert result["text"] == "SELECT * FROM customers;"
        assert mock_sleep.called, "expected generate_sql to sleep before retrying after a 429"

def test_rate_limit_exhausted_raises_runtime_error():
    with patch("chain.llm_client.OpenAI") as MockOpenAI, patch("chain.llm_client.time.sleep"):
        MockOpenAI.return_value.chat.completions.create.side_effect = _fake_rate_limit_error("0.01s")
        try:
            generate_sql("a prompt", "fake-key", "model", "url")
            assert False, "expected RuntimeError after exhausting rate-limit retries"
        except RuntimeError:
            pass

def test_extract_wait_seconds_parses_groq_message():
    seconds = _extract_wait_seconds("Rate limit reached. Please try again in 1.71s.")
    assert seconds == 2.21, f"expected 1.71 + 0.5 safety margin, got {seconds}"

def test_extract_wait_seconds_falls_back_when_unparseable():
    seconds = _extract_wait_seconds("some unrelated error text with no wait time")
    assert seconds == 5.0, f"expected the default fallback of 5.0, got {seconds}"

ALL_TESTS = [
    test_successful_call_returns_text_and_token_counts,
    test_timeout_raises_timeout_error,
    test_auth_error_raises_value_error_and_hides_key,
    test_empty_reply_raises_value_error,
    test_rate_limit_retries_then_succeeds,
    test_rate_limit_exhausted_raises_runtime_error,
    test_extract_wait_seconds_parses_groq_message,
    test_extract_wait_seconds_falls_back_when_unparseable,
]

if __name__ == "__main__":
    failures = 0
    for test_func in ALL_TESTS:
        try:
            test_func()
            print(f"[PASS] {test_func.__name__}")
        except AssertionError as err:
            failures += 1
            print(f"[FAIL] {test_func.__name__}: {err}")

    print(f"\n{len(ALL_TESTS) - failures}/{len(ALL_TESTS)} passed.")
    sys.exit(1 if failures else 0)
