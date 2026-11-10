"""Verify that DietCode's per-task model routing reduces estimated cost.

This is a local, deterministic verification of the existing forecasting and
model-selection logic. It does not call any LLM provider or require API keys.
"""

from __future__ import annotations

from dataclasses import dataclass

from engine.models.token_forecaster import TokenForecaster


@dataclass(frozen=True)
class MockTask:
    task_id: str
    title: str
    description: str
    category: str
    upstream_count: int
    depth: int


MOCK_DAG = (
    MockTask(
        "architecture",
        "Design the application architecture",
        "Define services, database schema, API contracts, and security boundaries.",
        "Architecture",
        0,
        1,
    ),
    MockTask(
        "backend",
        "Implement the backend API",
        "Build REST handlers, validation, persistence, and business logic.",
        "Backend",
        1,
        2,
    ),
    MockTask(
        "frontend",
        "Build the frontend dashboard",
        "Create responsive UI views, forms, and client state synchronization.",
        "Frontend",
        1,
        2,
    ),
    MockTask(
        "tests",
        "Write integration tests",
        "Verify API contracts, edge cases, validation, and error handling.",
        "QA & Testing",
        2,
        3,
    ),
    MockTask(
        "documentation",
        "Write project documentation",
        "Document setup, usage, API behavior, and troubleshooting steps.",
        "Documentation",
        1,
        2,
    ),
)


def verify_arbitrage() -> None:
    forecaster = TokenForecaster()
    routed_cost = 0.0
    baseline_cost = 0.0

    print("DietCode model-routing arbitrage verification")
    print("=" * 72)
    print(f"{'Task':<18} {'Routed model':<24} {'Routed cost':>14} {'GPT-4o cost':>14}")
    print("-" * 72)

    for task in MOCK_DAG:
        forecast = forecaster.forecast_node(
            title=task.title,
            description=task.description,
            upstream_count=task.upstream_count,
            depth=task.depth,
            category=task.category,
        )
        evaluations = forecast["modelEvaluations"]
        routed_model = forecast["recommendedAgent"]["id"]
        routed_task_cost = evaluations[routed_model]["totalCost"]
        baseline_task_cost = evaluations["gpt-4o"]["totalCost"]

        routed_cost += routed_task_cost
        baseline_cost += baseline_task_cost
        print(
            f"{task.task_id:<18} {routed_model:<24} "
            f"${routed_task_cost:>13.6f} ${baseline_task_cost:>13.6f}"
        )

    saved_cost = baseline_cost - routed_cost
    savings_percent = (saved_cost / baseline_cost * 100) if baseline_cost else 0.0

    print("-" * 72)
    print(f"{'Total routed cost:':<42} ${routed_cost:.6f}")
    print(f"{'All GPT-4o baseline:':<42} ${baseline_cost:.6f}")
    print(f"{'Estimated cost saved:':<42} ${saved_cost:.6f}")
    print(f"{'Percentage saved:':<42} {savings_percent:.2f}%")
    print("=" * 72)

    if routed_cost >= baseline_cost:
        raise RuntimeError(
            "Arbitrage verification failed: routed cost is not lower than the GPT-4o baseline."
        )


if __name__ == "__main__":
    verify_arbitrage()
