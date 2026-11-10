"""Local Gemini DAG simulator for validating dependency and context flow.

This script intentionally ignores each task's assigned model. Every task is
sent to one Gemini model using GEMINI_API_KEY from the project .env file.
It does not use the database, OpenRouter, or the production executor.
"""

from __future__ import annotations

import argparse
import asyncio
import os
import random
import sys
from pathlib import Path
from typing import Any, Mapping

import litellm
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent / ".env")

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

SIMULATOR_MODEL = os.getenv(
    "GEMINI_SIMULATOR_MODEL",
    "gemini/gemini-3.5-flash-lite",
)
REQUEST_TIMEOUT = float(os.getenv("GEMINI_SIMULATOR_TIMEOUT", "60"))
MAX_RETRIES = int(os.getenv("GEMINI_SIMULATOR_RETRIES", "2"))

MOCK_GRAPH: dict[str, dict[str, Any]] = {
    "design": {
        "prompt": "Design a small Python todo API. Return a concise architecture and endpoint plan.",
        "model": "claude-3-5-sonnet",
        "depends_on": [],
    },
    "implementation": {
        "prompt": "Implement the todo API described by the parent task. Return a compact Python code sample.",
        "model": "gpt-4o",
        "depends_on": ["design"],
    },
    "tests": {
        "prompt": "Write focused tests for the implementation described by the parent task.",
        "model": "gpt-4o-mini",
        "depends_on": ["implementation"],
    },
    "review": {
        "prompt": "Review the implementation and tests. List concrete fixes or confirm that they are sound.",
        "model": "gemini-1-5-pro",
        "depends_on": ["implementation", "tests"],
    },
}


def validate_graph(graph: Mapping[str, Mapping[str, Any]]) -> None:
    if not graph:
        raise ValueError("The simulator graph cannot be empty")

    for task_id, task in graph.items():
        if not isinstance(task_id, str) or not task_id.strip():
            raise ValueError("Task IDs must be non-empty strings")
        if not isinstance(task, Mapping):
            raise TypeError(f"Task {task_id!r} must be a mapping")
        if not isinstance(task.get("prompt"), str) or not task["prompt"].strip():
            raise ValueError(f"Task {task_id!r} requires a non-empty prompt")
        dependencies = task.get("depends_on", [])
        if not isinstance(dependencies, list):
            raise TypeError(f"Task {task_id!r}.depends_on must be a list")
        missing = [parent for parent in dependencies if parent not in graph]
        if missing:
            raise ValueError(f"Task {task_id!r} depends on unknown task(s): {missing}")

    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(task_id: str) -> None:
        if task_id in visiting:
            raise ValueError("The simulator graph must be acyclic")
        if task_id in visited:
            return
        visiting.add(task_id)
        for parent_id in graph[task_id].get("depends_on", []):
            visit(parent_id)
        visiting.remove(task_id)
        visited.add(task_id)

    for task_id in graph:
        visit(task_id)


def build_prompt(
    task: Mapping[str, Any],
    parent_results: list[dict[str, Any]],
) -> list[dict[str, str]]:
    parent_context = "\n\n".join(
        f"Parent task output ({index}):\n{result.get('text', '')}"
        if result.get("status") == "completed"
        else f"Parent task failure ({index}):\n{result.get('error', 'Unknown error')}"
        for index, result in enumerate(parent_results, start=1)
    )
    if not parent_context:
        return [{"role": "user", "content": task["prompt"]}]
    return [{
        "role": "user",
        "content": (
            "Use the following completed parent-task outputs as context.\n\n"
            f"{parent_context}\n\nCurrent task:\n{task['prompt']}"
        ),
    }]


def response_text(response: Any) -> str:
    try:
        content = response.choices[0].message.content
    except (AttributeError, IndexError, KeyError, TypeError) as exc:
        raise ValueError("Gemini response did not contain message content") from exc
    return str(content or "")


def is_transient_provider_error(exc: Exception) -> bool:
    message = str(exc).lower()
    return any(
        marker in message
        for marker in ("429", "500", "502", "503", "504", "rate limit", "temporarily")
    )


async def mock_completion(
    task_id: str,
    task: Mapping[str, Any],
    parent_results: list[dict[str, Any]],
) -> dict[str, Any]:
    await asyncio.sleep(0.01)
    parent_ids = task.get("depends_on", [])
    context_note = (
        f" Context received from: {', '.join(parent_ids)}."
        if parent_ids
        else ""
    )
    return {
        "status": "completed",
        "text": f"[Mock Gemini output for {task_id}] {task['prompt']}{context_note}",
        "model": "mock-gemini",
        "prompt_tokens": 0,
        "completion_tokens": 0,
    }


async def execute_graph(
    graph: Mapping[str, Mapping[str, Any]],
    *,
    mock: bool = False,
) -> dict[str, dict[str, Any]]:
    validate_graph(graph)
    if not mock and not os.getenv("GEMINI_API_KEY"):
        raise RuntimeError(
            "GEMINI_API_KEY is missing. Add it to the project .env file before running the simulator."
        )

    loop = asyncio.get_running_loop()
    futures = {task_id: loop.create_future() for task_id in graph}

    async def run_task(task_id: str) -> None:
        task = graph[task_id]
        parent_ids = task.get("depends_on", [])
        parent_results = await asyncio.gather(*(futures[parent] for parent in parent_ids))
        messages = build_prompt(task, parent_results)

        print(f"\n[WAIT COMPLETE] {task_id} | parents: {parent_ids or 'none'}")
        print(f"[EXECUTING] {task_id} | assigned model ignored | Gemini: {SIMULATOR_MODEL}")
        try:
            if mock:
                result = await mock_completion(task_id, task, parent_results)
            else:
                response = None
                for attempt in range(MAX_RETRIES + 1):
                    try:
                        response = await asyncio.wait_for(
                            litellm.acompletion(
                                model=SIMULATOR_MODEL,
                                messages=messages,
                                api_key=os.environ["GEMINI_API_KEY"],
                            ),
                            timeout=REQUEST_TIMEOUT,
                        )
                        break
                    except asyncio.CancelledError:
                        raise
                    except Exception as exc:
                        if attempt >= MAX_RETRIES or not is_transient_provider_error(exc):
                            raise
                        delay = min(8.0, 2 ** attempt) + random.uniform(0, 0.25)
                        print(
                            f"[RETRYING] {task_id} after transient provider error "
                            f"(attempt {attempt + 1}/{MAX_RETRIES}); waiting {delay:.1f}s"
                        )
                        await asyncio.sleep(delay)

                if response is None:
                    raise RuntimeError("Gemini returned no response")
                result = {
                    "status": "completed",
                    "text": response_text(response),
                    "model": SIMULATOR_MODEL,
                    "prompt_tokens": getattr(response.usage, "prompt_tokens", 0),
                    "completion_tokens": getattr(response.usage, "completion_tokens", 0),
                }
            print(f"[COMPLETED] {task_id}")
            print(result["text"])
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            result = {
                "status": "failed",
                "text": "",
                "model": SIMULATOR_MODEL,
                "error": f"{type(exc).__name__}: {exc}",
            }
            print(f"[FAILED] {task_id}: {result['error']}")
        futures[task_id].set_result(result)

    await asyncio.gather(*(asyncio.create_task(run_task(task_id)) for task_id in graph))
    return {task_id: future.result() for task_id, future in futures.items()}


async def main() -> None:
    global SIMULATOR_MODEL
    parser = argparse.ArgumentParser(description="Run the local Gemini DAG simulator")
    parser.add_argument(
        "--mock",
        action="store_true",
        help="Run without Gemini or an API key to validate DAG execution and context flow.",
    )
    parser.add_argument(
        "--model",
        default=SIMULATOR_MODEL,
        help="Gemini model passed to LiteLLM (default: GEMINI_SIMULATOR_MODEL or gemini/gemini-3.5-flash-lite)",
    )
    args = parser.parse_args()
    SIMULATOR_MODEL = args.model

    results = await execute_graph(MOCK_GRAPH, mock=args.mock)
    completed = sum(result["status"] == "completed" for result in results.values())
    print(f"\nSimulation finished: {completed}/{len(results)} tasks completed.")


if __name__ == "__main__":
    asyncio.run(main())
