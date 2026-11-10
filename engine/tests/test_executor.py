import asyncio
import unittest
from unittest.mock import patch

from engine.executor import DAGExecutor, ExecutionSettings


class ExecutorSettingsTests(unittest.TestCase):
    def test_selected_mode_uses_primary_model(self):
        settings = ExecutionSettings(
            mode="selected",
            primary_model="openai/gpt-4o",
            local_model="ollama/qwen2.5-coder:7b",
        )
        self.assertEqual(
            DAGExecutor._route_model("claude-3-5-sonnet", "write code", settings),
            "openai/gpt-4o",
        )

    def test_ollama_only_mode_uses_local_model(self):
        settings = ExecutionSettings(
            mode="ollama_only",
            primary_model="openai/gpt-4o",
            local_model="ollama/qwen2.5-coder:7b",
        )
        self.assertEqual(
            DAGExecutor._route_model("gpt-4o", "design architecture", settings),
            "ollama/qwen2.5-coder:7b",
        )

    def test_hybrid_mode_routes_routine_work_locally(self):
        settings = ExecutionSettings(
            mode="hybrid",
            primary_model="gemini-3-8-flash",
            local_model="ollama/qwen2.5-coder:7b",
        )
        with patch.object(DAGExecutor, "_is_ollama_online", return_value=True):
            self.assertEqual(
                DAGExecutor._route_model("gpt-4o", "write unit tests and documentation", settings),
                "ollama/qwen2.5-coder:7b",
            )

    def test_parent_context_is_compacted_and_deduplicated(self):
        result = {"status": "completed", "text": "abcdef" * 20}
        messages = DAGExecutor._build_messages(
            "continue the task",
            [result, result],
            max_context_chars=30,
        )
        content = messages[0]["content"]
        self.assertEqual(content.count("Parent task"), 1)
        self.assertIn("[compacted", content)
        self.assertIn("Current task:\ncontinue the task", content)

    def test_fallback_disabled_returns_failure(self):
        graph = {
            "task": {
                "prompt": "write a test",
                "model": "ollama/qwen2.5-coder:7b",
                "depends_on": [],
            }
        }
        executor = DAGExecutor(
            settings=ExecutionSettings(
                mode="ollama_only",
                allow_fallback=False,
                request_timeout=1,
            )
        )
        with patch.object(DAGExecutor, "_has_credentials_for", return_value=False):
            results = asyncio.run(executor.execute(graph))
        self.assertEqual(results["task"]["status"], "failed")
        self.assertIn("Ollama offline", results["task"]["error"])

    def test_provider_errors_are_categorized(self):
        cases = {
            "HTTP 429 quota exceeded": "quota_exceeded",
            "invalid api key": "invalid_credentials",
            "request timed out": "timeout",
            "model not found": "model_unavailable",
            "Ollama connection refused": "ollama_offline",
        }
        for message, category in cases.items():
            with self.subTest(message=message):
                self.assertEqual(DAGExecutor._classify_error(message), category)


if __name__ == "__main__":
    unittest.main()
