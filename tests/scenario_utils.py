import os

import pytest
import re
import scenario

try:
    from scenario import ModelConfig  # newer exports
except ImportError:  # older scenario versions
    from scenario.config import ModelConfig
from langchain_core.messages import (
    AIMessage,
    HumanMessage,
    SystemMessage,
    convert_to_openai_messages,
)
from langgraph.checkpoint.memory import InMemorySaver

from graph_builder import build_graph


_CONFIGURED = False


def _configure_scenario() -> bool:
    global _CONFIGURED
    if _CONFIGURED:
        return True

    model = os.getenv("SCENARIO_MODEL")
    api_base = os.getenv("SCENARIO_API_BASE")
    api_key = os.getenv("SCENARIO_API_KEY") or os.getenv("OPENAI_API_KEY")
    ollama_model = os.getenv("OLLAMA_MODEL")
    ollama_base = os.getenv("OLLAMA_BASE_URL")

    if model:
        scenario.configure(
            default_model=ModelConfig(
                model=model,
                api_base=api_base,
                api_key=api_key,
                temperature=0.1,
            )
        )
        _CONFIGURED = True
        return True

    if ollama_model and ollama_base:
        base = ollama_base.rstrip("/")
        if not base.endswith("/v1"):
            base = f"{base}/v1"
        model_name = (
            ollama_model
            if "/" in ollama_model
            else f"openai/{ollama_model}"
        )
        scenario.configure(
            default_model=ModelConfig(
                model=model_name,
                api_base=base,
                api_key=os.getenv("SCENARIO_API_KEY") or "ollama",
                temperature=0.1,
            )
        )
        _CONFIGURED = True
        return True

    if api_key:
        scenario.configure(default_model="openai/gpt-4.1-mini")
        _CONFIGURED = True
        return True

    return False


def _ollama_openai_base() -> str | None:
    base = os.getenv("OLLAMA_BASE_URL")
    if not base:
        return None
    base = base.rstrip("/")
    if not base.endswith("/v1"):
        base = f"{base}/v1"
    return base


def _normalize_model_name(model: str) -> str:
    if "/" in model:
        return model
    return f"openai/{model}"


def make_judge(criteria: list[str]) -> scenario.JudgeAgent:
    model = os.getenv("SCENARIO_JUDGE_MODEL")
    api_base = os.getenv("SCENARIO_JUDGE_API_BASE")
    api_key = os.getenv("SCENARIO_JUDGE_API_KEY")
    temperature = os.getenv("SCENARIO_JUDGE_TEMPERATURE")

    if not model:
        model = os.getenv("OLLAMA_JUDGE_MODEL") or os.getenv("OLLAMA_MODEL")
        if model:
            model = _normalize_model_name(model)

    if not api_base:
        api_base = _ollama_openai_base()

    if not api_key and api_base:
        api_key = "ollama"

    kwargs: dict = {"criteria": criteria}
    if model:
        kwargs["model"] = model
    if api_base:
        kwargs["api_base"] = api_base
    if api_key:
        kwargs["api_key"] = api_key
    if temperature is not None:
        try:
            kwargs["temperature"] = float(temperature)
        except ValueError:
            pass

    return scenario.JudgeAgent(**kwargs)


def _has_db_config() -> bool:
    if os.getenv("SUPASEBASE_DB_URL"):
        return True
    required = [
        "SUPASEBASE_DB_HOST",
        "SUPASEBASE_DB_NAME",
        "SUPASEBASE_DB_USER",
        "SUPASEBASE_DB_PASSWORD",
        "SUPASEBASE_DB_PORT",
    ]
    return all(os.getenv(key) for key in required)


def require_scenario_env() -> None:
    if not _configure_scenario():
        pytest.skip(
            "Set SCENARIO_MODEL (and optional SCENARIO_API_BASE/SCENARIO_API_KEY) "
            "or OPENAI_API_KEY to run scenario tests."
        )
    if not _has_db_config():
        pytest.skip(
            "Set SUPASEBASE_DB_URL or SUPASEBASE_DB_* values to run scenario tests."
        )


class SupportAgentAdapter(scenario.AgentAdapter):
    def __init__(self) -> None:
        self.graph = build_graph(checkpointer=InMemorySaver())

    async def call(self, input: scenario.AgentInput) -> scenario.AgentReturnTypes:
        messages = []
        for message in input.messages:
            role = message.get("role")
            content = message.get("content")
            if not isinstance(content, str):
                content = str(content)

            if role == "user":
                messages.append(HumanMessage(content=content))
            elif role == "assistant":
                messages.append(AIMessage(content=content))
            elif role == "system":
                messages.append(SystemMessage(content=content))

        result = await self.graph.ainvoke(
            {"messages": messages},
            {"configurable": {"thread_id": input.thread_id}},
        )

        return convert_to_openai_messages(result["messages"])


def _extract_text(content) -> str:
    if isinstance(content, list):
        parts: list[str] = []
        for part in content:
            if isinstance(part, str):
                parts.append(part)
            elif isinstance(part, dict) and "text" in part:
                parts.append(str(part["text"]))
        return " ".join(p for p in parts if p).strip()
    if content is None:
        return ""
    return str(content).strip()


def _last_assistant_text(messages) -> str:
    for message in reversed(messages):
        if message.get("role") == "assistant":
            return _extract_text(message.get("content"))
    return ""


def _count_list_items(text: str) -> int:
    return sum(1 for line in text.splitlines() if line.strip().startswith("- "))


def _count_sentences(text: str) -> int:
    parts = [p for p in re.split(r"[.!?]+", text) if p.strip()]
    return len(parts)


def evaluate_last_assistant(
    state,
    *,
    must_include: list[str] | None = None,
    must_include_any: list[str] | None = None,
    must_not_include: list[str] | None = None,
    min_list_items: int | None = None,
    max_list_items: int | None = None,
    min_sentences: int | None = None,
    max_sentences: int | None = None,
) -> scenario.ScenarioResult:
    text = _last_assistant_text(state.messages)
    text_lower = text.lower()

    if must_include:
        missing = [s for s in must_include if s.lower() not in text_lower]
        if missing:
            return scenario.ScenarioResult(
                success=False,
                messages=state.messages,
                reasoning=f"Missing required text: {', '.join(missing)}",
            )

    if must_include_any:
        if not any(s.lower() in text_lower for s in must_include_any):
            return scenario.ScenarioResult(
                success=False,
                messages=state.messages,
                reasoning="Missing any of the required attributes.",
            )

    if must_not_include:
        found = [s for s in must_not_include if s.lower() in text_lower]
        if found:
            return scenario.ScenarioResult(
                success=False,
                messages=state.messages,
                reasoning=f"Found forbidden text: {', '.join(found)}",
            )

    if min_list_items is not None or max_list_items is not None:
        count = _count_list_items(text)
        if min_list_items is not None and count < min_list_items:
            return scenario.ScenarioResult(
                success=False,
                messages=state.messages,
                reasoning=f"Expected at least {min_list_items} list items, got {count}.",
            )
        if max_list_items is not None and count > max_list_items:
            return scenario.ScenarioResult(
                success=False,
                messages=state.messages,
                reasoning=f"Expected at most {max_list_items} list items, got {count}.",
            )

    if min_sentences is not None or max_sentences is not None:
        count = _count_sentences(text)
        if min_sentences is not None and count < min_sentences:
            return scenario.ScenarioResult(
                success=False,
                messages=state.messages,
                reasoning=f"Expected at least {min_sentences} sentences, got {count}.",
            )
        if max_sentences is not None and count > max_sentences:
            return scenario.ScenarioResult(
                success=False,
                messages=state.messages,
                reasoning=f"Expected at most {max_sentences} sentences, got {count}.",
            )

    return scenario.ScenarioResult(success=True, messages=state.messages)
