
import re
import time

from openai import (
    OpenAI,
    APITimeoutError,
    AuthenticationError,
    RateLimitError,
)

MAX_RATE_LIMIT_RETRIES = 3

def generate_sql(prompt, api_key, model_name, base_url):
    client = OpenAI(api_key=api_key, base_url=base_url, timeout=30.0, max_retries=0)
    response = _call_with_rate_limit_retry(client, model_name, prompt, api_key)

    text = response.choices[0].message.content
    if not text or not text.strip():
        raise ValueError("The model returned no text.")

    usage = response.usage
    return {
        "text": text,
        "prompt_tokens": usage.prompt_tokens if usage else None,
        "completion_tokens": usage.completion_tokens if usage else None,
        "total_tokens": usage.total_tokens if usage else None,
    }

def _call_with_rate_limit_retry(client, model_name, prompt, api_key):
    for attempt in range(MAX_RATE_LIMIT_RETRIES + 1):
        try:
            return client.chat.completions.create(
                model=model_name,
                messages=[{"role": "user", "content": prompt}],
                temperature=0,
            )
        except APITimeoutError:
            raise TimeoutError("The LLM call timed out after 30 seconds.")
        except AuthenticationError as err:
            raise ValueError(f"API key was rejected by the provider: {_hide_key(err, api_key)}")
        except RateLimitError as err:
            if attempt >= MAX_RATE_LIMIT_RETRIES:
                raise RuntimeError(
                    f"LLM call failed after {MAX_RATE_LIMIT_RETRIES} rate-limit retries: {_hide_key(err, api_key)}"
                )
            time.sleep(_extract_wait_seconds(str(err)))
        except Exception as err:
            raise RuntimeError(f"LLM call failed: {_hide_key(err, api_key)}")

def _extract_wait_seconds(error_text):
    match = re.search(r"try again in ([\d.]+)s", error_text)
    if match:
        return float(match.group(1)) + 0.5
    return 5.0

def _hide_key(err, api_key):
    text = str(err)
    if api_key and api_key in text:
        text = text.replace(api_key, "***")
    return text
