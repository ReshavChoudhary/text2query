
import os

from dotenv import load_dotenv

GROQ_BASE_URL = "https://api.groq.com/openai/v1"

DEFAULT_MODEL = "openai/gpt-oss-120b"

def load_config():
    load_dotenv()

    api_key = os.environ.get("GROQ_API_KEY", "").strip()
    if not api_key:
        raise ValueError("GROQ_API_KEY is not set. Add it to your .env file (see .env.example).")

    model_name = os.environ.get("TEXT2SQL_MODEL", "").strip()
    if not model_name:
        model_name = DEFAULT_MODEL

    base_url = os.environ.get("TEXT2SQL_BASE_URL", "").strip()
    if not base_url:
        base_url = GROQ_BASE_URL

    return {
        "api_key": api_key,
        "model_name": model_name,
        "base_url": base_url,
    }
