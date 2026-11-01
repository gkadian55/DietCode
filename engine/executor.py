"""Asynchronous DAG execution for DietCode.

The executor deliberately keeps orchestration separate from the FastAPI layer:
callers provide a validated task graph and receive one result record per task.
Independent branches are scheduled concurrently, while each task waits for all
of its declared parents.
"""

from __future__ import annotations

import asyncio
import logging
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

import litellm
from dotenv import load_dotenv

logger = logging.getLogger(__name__)
load_dotenv(Path(__file__).resolve().parents[1] / ".env")

# DietCode uses stable IDs for pricing and UI state. LiteLLM requires provider
# qualified names for providers such as Google and Anthropic.
PRIMARY_MODEL = os.getenv("DIETCODE_PRIMARY_MODEL", "gemini-3-8-flash")
LOCAL_MODEL = os.getenv("DIETCODE_LOCAL_MODEL", "ollama/qwen2.5-coder:7b")
OLLAMA_API_BASE = os.getenv("OLLAMA_API_BASE", "http://127.0.0.1:11434")
LOCAL_ROUTING_ENABLED = os.getenv("DIETCODE_LOCAL_ROUTING", "true").lower() in {
    "1", "true", "yes", "on"
}
LOCAL_TASK_TERMS = (
    "boilerplate", "documentation", "document", "format", "lint",
    "unit test", "tests", "testing", "qa", "frontend", "client ui",
    "dashboard", "simple", "crud", "schema migration",
)
PRIMARY_TASK_TERMS = (
    "architecture", "protocol", "security", "distributed", "algorithm",
    "fault-tolerant", "observability", "system design", "deep audit",
)
LITELLM_MODEL_ALIASES = {
    "claude-3-5-sonnet": "anthropic/claude-3-5-sonnet-20241022",
    "claude-3-5-haiku": "anthropic/claude-3-5-haiku-20241022",
    "gpt-4o": "openai/gpt-4o",
    "gpt-4o-mini": "openai/gpt-4o-mini",
    "gemini-2-0-flash": "gemini/gemini-2.0-flash",
    "gemini-3-8-flash": "gemini/gemini-3.8-flash",
    "gemini-1-5-pro": "gemini/gemini-1.5-pro",
}


@dataclass(frozen=True)
class _TaskSpec:
    """Normalized task definition used internally by the executor."""

    task_id: str
    prompt: str
    model: str
    depends_on: tuple[str, ...]


class DAGExecutor:
    """Execute a dependency graph through LiteLLM's asynchronous API."""

    def __init__(
        self,
        *,
        max_concurrency: int = 8,
        request_timeout: float = 120.0,
        max_retries: int = 2,
    ) -> None:
        if max_concurrency < 1:
            raise ValueError("max_concurrency must be at least 1")
        if request_timeout <= 0:
            raise ValueError("request_timeout must be positive")
        if max_retries < 0:
            raise ValueError("max_retries cannot be negative")

        self._semaphore = asyncio.Semaphore(max_concurrency)
        self._request_timeout = request_timeout
        self._max_retries = max_retries

    async def execute(
        self,
        graph: Mapping[str, Mapping[str, Any]],
    ) -> dict[str, dict[str, Any]]:
        """Execute *graph* and return results keyed by task ID.

        Every task produces a result, including tasks whose API request fails.
        A failed parent does not crash the graph; its error is included in the
        child's context so the child can decide how to recover.
        """
        specs = self._normalize_graph(graph)
        self._validate_dependencies(specs)

        loop = asyncio.get_running_loop()
        completion_futures = {
            task_id: loop.create_future() for task_id in specs
        }
        workers = [
            asyncio.create_task(self._run_task(spec, completion_futures))
            for spec in specs.values()
        ]

        # A worker always resolves its own future, so gather should not abort
        # the remaining branches even when an unexpected orchestration error
        # occurs.
        await asyncio.gather(*workers)
        return {
            task_id: future.result()
            for task_id, future in completion_futures.items()
        }

    async def _run_task(
        self,
        spec: _TaskSpec,
        completion_futures: Mapping[str, asyncio.Future[dict[str, Any]]],
    ) -> None:
        try:
            parent_results = await asyncio.gather(
                *(completion_futures[parent_id] for parent_id in spec.depends_on)
            )
            result = await self._execute_task(spec, parent_results)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            # This guard covers orchestration failures as well as API failures
            # that escaped the request retry loop.
            logger.exception("Unexpected failure while running task %s", spec.task_id)
            result = self._failed_result(
                spec,
                f"Unexpected executor error: {self._exception_text(exc)}",
            )

        completion_futures[spec.task_id].set_result(result)

    async def _execute_task(
        self,
        spec: _TaskSpec,
        parent_results: list[dict[str, Any]],
    ) -> dict[str, Any]:
        messages = self._build_messages(spec.prompt, parent_results)

        try:
            routed_model = self._route_model(spec.model, spec.prompt)
            response = await self._complete_with_retries(routed_model, messages)
            text = self._response_text(response)
            prompt_tokens, completion_tokens = self._response_usage(response)
            return {
                "status": "completed",
                "text": text,
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "total_tokens": prompt_tokens + completion_tokens,
                "model": spec.model,
                "routed_model": routed_model,
                "error": None,
            }
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            logger.error("Task %s failed: %s", spec.task_id, exc)
            return self._failed_result(spec, self._exception_text(exc))

    async def _complete_with_retries(
        self,
        model: str,
        messages: list[dict[str, str]],
    ) -> Any:
        litellm_model = LITELLM_MODEL_ALIASES.get(model, model)
        request_options = {}
        if litellm_model.startswith("ollama/"):
            request_options["api_base"] = OLLAMA_API_BASE
        last_error: Exception | None = None
        for attempt in range(self._max_retries + 1):
            try:
                async with self._semaphore:
                    return await asyncio.wait_for(
                        litellm.acompletion(
                            model=litellm_model,
                            messages=messages,
                            **request_options,
                        ),
                        timeout=self._request_timeout,
                    )
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                last_error = exc
                if attempt >= self._max_retries:
                    break
                delay = min(2**attempt, 8)
                logger.warning(
                    "LiteLLM request failed (attempt %d/%d); retrying in %ss: %s",
                    attempt + 1,
                    self._max_retries + 1,
                    delay,
                    exc,
                )
                await asyncio.sleep(delay)

        assert last_error is not None
        raise last_error

    @staticmethod
    def _route_model(requested_model: str, prompt: str) -> str:
        """Route routine work locally while reserving the primary model for complexity."""
        if requested_model.startswith("ollama/"):
            return requested_model
        if not LOCAL_ROUTING_ENABLED:
            return PRIMARY_MODEL

        normalized_prompt = prompt.lower()
        if any(term in normalized_prompt for term in PRIMARY_TASK_TERMS):
            return PRIMARY_MODEL
        if any(term in normalized_prompt for term in LOCAL_TASK_TERMS):
            return LOCAL_MODEL
        return PRIMARY_MODEL

    @staticmethod
    def _exception_text(exc: Exception) -> str:
        return str(exc) or repr(exc) or type(exc).__name__

    @staticmethod
    def _build_messages(
        prompt: str,
        parent_results: list[dict[str, Any]],
    ) -> list[dict[str, str]]:
        if not parent_results:
            return [{"role": "user", "content": prompt}]

        parent_context = "\n\n".join(
            f"Parent task {index} output:\n{result.get('text', '')}"
            if result.get("status") == "completed"
            else (
                f"Parent task {index} failed:\n"
                f"{result.get('error', 'Unknown parent failure')}"
            )
            for index, result in enumerate(parent_results, start=1)
        )
        return [{
            "role": "user",
            "content": (
                "Use the following completed parent-task context when useful.\n\n"
                f"{parent_context}\n\nCurrent task:\n{prompt}"
            ),
        }]

    @staticmethod
    def _response_text(response: Any) -> str:
        try:
            content = response.choices[0].message.content
        except (AttributeError, IndexError, KeyError, TypeError) as exc:
            raise ValueError("LiteLLM response did not contain message content") from exc
        if content is None:
            return ""
        return str(content)

    @staticmethod
    def _response_usage(response: Any) -> tuple[int, int]:
        usage = getattr(response, "usage", None)
        if usage is None and isinstance(response, Mapping):
            usage = response.get("usage")
        if usage is None:
            raise ValueError("LiteLLM response did not contain token usage")

        def read(field: str) -> int:
            value = getattr(usage, field, None)
            if value is None and isinstance(usage, Mapping):
                value = usage.get(field)
            if value is None:
                raise ValueError(f"LiteLLM response usage is missing {field}")
            return int(value)

        return read("prompt_tokens"), read("completion_tokens")

    @staticmethod
    def _normalize_graph(
        graph: Mapping[str, Mapping[str, Any]],
    ) -> dict[str, _TaskSpec]:
        if not isinstance(graph, Mapping):
            raise TypeError("graph must be a mapping of task IDs to task definitions")

        specs: dict[str, _TaskSpec] = {}
        for task_id, task in graph.items():
            if not isinstance(task_id, str) or not task_id.strip():
                raise ValueError("task IDs must be non-empty strings")
            if not isinstance(task, Mapping):
                raise TypeError(f"Task {task_id!r} must be a mapping")

            prompt = task.get("prompt")
            model = task.get("model")
            depends_on = task.get("depends_on", [])
            if not isinstance(prompt, str) or not prompt.strip():
                raise ValueError(f"Task {task_id!r} requires a non-empty prompt")
            if not isinstance(model, str) or not model.strip():
                raise ValueError(f"Task {task_id!r} requires a non-empty model")
            if isinstance(depends_on, (str, bytes)) or not isinstance(depends_on, list):
                raise TypeError(f"Task {task_id!r}.depends_on must be a list")
            if any(not isinstance(parent, str) for parent in depends_on):
                raise TypeError(f"Task {task_id!r}.depends_on must contain strings")

            specs[task_id] = _TaskSpec(
                task_id=task_id,
                prompt=prompt,
                model=model,
                depends_on=tuple(dict.fromkeys(depends_on)),
            )
        return specs

    @staticmethod
    def _validate_dependencies(specs: Mapping[str, _TaskSpec]) -> None:
        for spec in specs.values():
            missing = [parent for parent in spec.depends_on if parent not in specs]
            if missing:
                raise ValueError(
                    f"Task {spec.task_id!r} depends on unknown task(s): {missing}"
                )

        visiting: set[str] = set()
        visited: set[str] = set()

        def visit(task_id: str) -> None:
            if task_id in visiting:
                raise ValueError("graph must be acyclic")
            if task_id in visited:
                return
            visiting.add(task_id)
            for parent_id in specs[task_id].depends_on:
                visit(parent_id)
            visiting.remove(task_id)
            visited.add(task_id)

        for task_id in specs:
            visit(task_id)

    @staticmethod
    def _failed_result(spec: _TaskSpec, error: str) -> dict[str, Any]:
        return {
            "status": "failed",
            "text": "",
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "total_tokens": 0,
            "model": spec.model,
            "routed_model": None,
            "error": error,
        }


async def main() -> None:
    """Run a local mock graph; no provider credentials or network are needed."""
    class MockResponse:
        choices = [type("Choice", (), {
            "message": type("Message", (), {"content": "Mock task output"})()
        })()]
        usage = type("Usage", (), {
            "prompt_tokens": 12,
            "completion_tokens": 8,
        })()

    async def mock_acompletion(**_: Any) -> MockResponse:
        await asyncio.sleep(0.01)
        return MockResponse()

    original_acompletion = litellm.acompletion
    litellm.acompletion = mock_acompletion
    try:
        graph = {
            "design": {
                "prompt": "Design the service API.",
                "model": "gpt-4o-mini",
                "depends_on": [],
            },
            "implementation": {
                "prompt": "Implement the service from the design.",
                "model": "claude-3-5-sonnet",
                "depends_on": ["design"],
            },
            "tests": {
                "prompt": "Write tests for the service.",
                "model": "gemini/gemini-3.8-flash",
                "depends_on": ["implementation"],
            },
        }
        results = await DAGExecutor().execute(graph)
        for task_id, result in results.items():
            print(task_id, result)
    finally:
        litellm.acompletion = original_acompletion


if __name__ == "__main__":
    asyncio.run(main())
