import os
from dotenv import load_dotenv
from langchain_ollama import ChatOllama
from langchain_groq import ChatGroq

load_dotenv(".env", override=False)


def _get_env_float(key: str, default: float) -> float:
    value = os.getenv(key)
    if value is None or value == "":
        return default
    try:
        return float(value)
    except ValueError:
        return default


def _get_env_int(key: str, default: int) -> int:
    value = os.getenv(key)
    if value is None or value == "":
        return default
    try:
        return int(value)
    except ValueError:
        return default


def get_llm():
    provider = os.getenv("LLM_PROVIDER", "ollama").strip().lower()

    if provider == "groq":
        if ChatGroq is None:
            raise RuntimeError(
                "langchain-groq is not installed. Add it to your dependencies."
            )
        api_key = os.getenv("GROQ_API_KEY")
        model_name = os.getenv("GROQ_MODEL")
        if not api_key:
            raise RuntimeError("GROQ_API_KEY is not set.")
        if not model_name:
            raise RuntimeError("GROQ_MODEL is not set.")

        return ChatGroq(
            groq_api_key=api_key,
            model_name=model_name,
            temperature=_get_env_float("GROQ_TEMPERATURE", 0.0),
            max_tokens=_get_env_int("GROQ_MAX_TOKENS", 1024),
            streaming=True,
        )

    return ChatOllama(
        model=os.getenv("OLLAMA_MODEL"),
        base_url=os.getenv("OLLAMA_BASE_URL"),
        temperature=_get_env_float("OLLAMA_TEMPERATURE", 0.0),
        num_predict=_get_env_int("OLLAMA_NUM_PREDICT", 1024),
        num_ctx=_get_env_int("OLLAMA_NUM_CTX", 2048),
        streaming=True,
    )
