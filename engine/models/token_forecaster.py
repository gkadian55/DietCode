import os
import pickle
import re

import numpy as np
from sklearn.ensemble import GradientBoostingRegressor
from sklearn.multioutput import MultiOutputRegressor

MODEL_FILE = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "data", "token_forecaster.pkl"))

# Benchmarked Model Cost and Performance Profiles
MODEL_PROFILES = {
    "claude-3-5-sonnet": {
        "displayName": "Claude 3.5 Sonnet",
        "provider": "Anthropic",
        "color": "#f97316",  # orange
        "inputCostPerM": 3.00,
        "outputCostPerM": 15.00,
        "tokensPerSec": 75,
        "reasoningScore": 96,
        "bestFor": ["Complex Systems", "Full-Stack Refactor", "Multi-file Architecture"]
    },
    "gpt-4o": {
        "displayName": "ChatGPT (GPT-4o)",
        "provider": "OpenAI",
        "color": "#10b981",  # emerald green
        "inputCostPerM": 2.50,
        "outputCostPerM": 10.00,
        "tokensPerSec": 85,
        "reasoningScore": 93,
        "bestFor": ["Algorithm Design", "API Orchestration", "General Problem Solving"]
    },
    "gemini-2-0-flash": {
        "displayName": "Gemini 2.0 Flash",
        "provider": "Google",
        "color": "#6366f1",  # indigo
        "inputCostPerM": 0.10,
        "outputCostPerM": 0.40,
        "tokensPerSec": 150,
        "reasoningScore": 88,
        "bestFor": ["High-Throughput IO", "Rapid Prototyping", "Cost-Critical Batches"]
    },
    "gemini-1-5-pro": {
        "displayName": "Gemini 1.5 Pro",
        "provider": "Google",
        "color": "#8b5cf6",  # purple
        "inputCostPerM": 1.25,
        "outputCostPerM": 5.00,
        "tokensPerSec": 65,
        "reasoningScore": 92,
        "bestFor": ["Long Context Dependency", "Deep Code Audit", "Large Codebases"]
    },
    "claude-3-5-haiku": {
        "displayName": "Claude 3.5 Haiku",
        "provider": "Anthropic",
        "color": "#fb923c",
        "inputCostPerM": 0.80,
        "outputCostPerM": 4.00,
        "tokensPerSec": 125,
        "reasoningScore": 86,
        "bestFor": ["Unit Test Generation", "Documentation", "Fast Micro-Tasks"]
    },
    "gpt-4o-mini": {
        "displayName": "GPT-4o Mini",
        "provider": "OpenAI",
        "color": "#34d399",
        "inputCostPerM": 0.15,
        "outputCostPerM": 0.60,
        "tokensPerSec": 140,
        "reasoningScore": 83,
        "bestFor": ["Data Parsing", "Boilerplate Code", "Simple Regex & Schema"]
    }
}


class TokenForecaster:
    def __init__(self):
        self.model = None
        self._load_or_train()

    def _extract_features(self, title: str | None, description: str | None, upstream_count: int | None = 0, depth: int | None = 1) -> np.ndarray:
        """Extract cognitive and tokenomic feature vectors from task text and DAG location."""
        safe_title = str(title or "")
        safe_desc = str(description or "")
        text = f"{safe_title} {safe_desc}".lower()
        words = re.findall(r"\b\w+\b", text)
        word_count = len(words)
        char_count = len(text)

        safe_upstream = max(0, int(upstream_count or 0))
        safe_depth = max(1, int(depth or 1))

        # Technical complexity indicators
        code_keywords = [
            "class", "def", "interface", "async", "await", "model", "schema", "database",
            "sql", "api", "rest", "graphql", "socket", "worker", "queue", "thread", "concurrency",
            "mutex", "cache", "redis", "docker", "test", "benchmark", "optimize", "pipeline",
            "distributed", "consensus", "state", "dag", "token", "ast", "compiler", "parser"
        ]
        keyword_hits = sum(1 for kw in code_keywords if kw in text)

        # Depth & structure signals
        is_architecture = 1.0 if any(k in text for k in ["architect", "design", "plan", "spec", "schema"]) else 0.0
        is_implementation = 1.0 if any(k in text for k in ["implement", "build", "create", "engine", "service", "handler"]) else 0.0
        is_testing = 1.0 if any(k in text for k in ["test", "verify", "benchmark", "validate", "mock", "suite"]) else 0.0
        is_refactor = 1.0 if any(k in text for k in ["refactor", "optimize", "clean", "audit", "profile"]) else 0.0

        features = [
            float(word_count),
            float(char_count),
            float(keyword_hits),
            float(safe_upstream),
            float(safe_depth),
            is_architecture,
            is_implementation,
            is_testing,
            is_refactor,
            float(keyword_hits) / max(1.0, float(word_count))  # density
        ]
        return np.array(features, dtype=np.float32)

    def _generate_synthetic_training_data(self, n_samples: int = 2500):
        """Generates realistic synthetic agent execution traces to pre-train our local model."""
        np.random.seed(42)
        x_data = []
        y_data = []  # [input_tokens, output_tokens]

        archetypes = [
            {"words": 15, "kw": 3, "upstream": 0, "depth": 1, "is_arch": 1, "is_impl": 0, "is_test": 0, "is_refactor": 0, "in_base": 650, "out_base": 1200},
            {"words": 30, "kw": 8, "upstream": 1, "depth": 2, "is_arch": 0, "is_impl": 1, "is_test": 0, "is_refactor": 0, "in_base": 1800, "out_base": 3200},
            {"words": 45, "kw": 12, "upstream": 2, "depth": 3, "is_arch": 0, "is_impl": 1, "is_test": 0, "is_refactor": 0, "in_base": 2800, "out_base": 4200},
            {"words": 20, "kw": 6, "upstream": 2, "depth": 3, "is_arch": 0, "is_impl": 0, "is_test": 1, "is_refactor": 0, "in_base": 2100, "out_base": 2400},
            {"words": 18, "kw": 5, "upstream": 1, "depth": 2, "is_arch": 0, "is_impl": 0, "is_test": 0, "is_refactor": 1, "in_base": 1500, "out_base": 1800},
            {"words": 10, "kw": 2, "upstream": 0, "depth": 1, "is_arch": 0, "is_impl": 0, "is_test": 0, "is_refactor": 0, "in_base": 400, "out_base": 600},
        ]

        for _ in range(n_samples):
            arch_idx = int(np.random.choice(len(archetypes)))
            arch = archetypes[arch_idx]

            # Add stochastic variance
            words = max(5, int(float(arch["words"]) * float(np.random.normal(1.0, 0.25))))
            chars = words * int(float(np.random.normal(6.5, 1.2)))
            kw = max(0, int(float(arch["kw"]) * float(np.random.normal(1.0, 0.3))))
            upstream = max(0, int(arch["upstream"] + int(np.random.choice([-1, 0, 1], p=[0.2, 0.6, 0.2]))))
            depth = max(1, int(arch["depth"] + int(np.random.choice([-1, 0, 1], p=[0.15, 0.7, 0.15]))))
            density = float(kw) / max(1.0, float(words))

            feat = [
                float(words), float(chars), float(kw), float(upstream), float(depth),
                float(arch["is_arch"]), float(arch["is_impl"]), float(arch["is_test"]), float(arch["is_refactor"]),
                density
            ]

            # Upstream dependencies accumulate context into input tokens
            upstream_token_bleed = upstream * float(np.random.uniform(350, 950))
            in_tok = int(float(arch["in_base"]) * float(np.random.normal(1.0, 0.18)) + upstream_token_bleed + words * 12)
            out_tok = int(float(arch["out_base"]) * float(np.random.normal(1.0, 0.22)) + kw * 85)

            x_data.append(feat)
            y_data.append([max(150, in_tok), max(200, out_tok)])

        return np.array(x_data, dtype=np.float32), np.array(y_data, dtype=np.float32)

    def _load_or_train(self):
        os.makedirs(os.path.dirname(MODEL_FILE), exist_ok=True)
        if os.path.exists(MODEL_FILE):
            try:
                with open(MODEL_FILE, "rb") as f:
                    self.model = pickle.load(f)
                return
            except (pickle.PickleError, EOFError, OSError) as e:
                print(f"[TokenForecaster] Could not load existing model ({e}), retraining...")

        print("[TokenForecaster] Training local multi-target gradient boosted regressor...")
        x_train, y_train = self._generate_synthetic_training_data()
        base_gbr = GradientBoostingRegressor(n_estimators=120, max_depth=5, learning_rate=0.08, random_state=42)
        self.model = MultiOutputRegressor(base_gbr)
        self.model.fit(x_train, y_train)

        with open(MODEL_FILE, "wb") as f:
            pickle.dump(self.model, f)
        print("[TokenForecaster] Self-trained model successfully trained and saved to disk.")

    def forecast_node(self, title: str | None, description: str | None, upstream_count: int | None = 0, depth: int | None = 1):
        """Fast inference (<2ms) predicting tokens, latency, cost per LLM, and the Pareto-optimal agent."""
        safe_upstream = max(0, int(upstream_count or 0))
        safe_depth = max(1, int(depth or 1))

        feat = self._extract_features(title, description, safe_upstream, safe_depth).reshape(1, -1)
        pred = self.model.predict(feat)[0]

        in_tokens = int(max(100, round(float(pred[0]))))
        out_tokens = int(max(150, round(float(pred[1]))))
        total_tokens = in_tokens + out_tokens

        # Complexity rating 1-100
        safe_text = f"{title or ''} {description or ''}".lower()
        complexity_score = min(99, max(25, int(
            (out_tokens / 50) + (safe_upstream * 8) + (15 if "complex" in safe_text or "distributed" in safe_text else 0)
        )))

        # Evaluate across all LLM models
        evaluations = {}
        candidate_scores = []

        for model_id, prof in MODEL_PROFILES.items():
            in_cost = (in_tokens / 1_000_000.0) * prof["inputCostPerM"]
            out_cost = (out_tokens / 1_000_000.0) * prof["outputCostPerM"]
            total_cost = round(in_cost + out_cost, 6)
            latency_sec = round(out_tokens / prof["tokensPerSec"], 2)

            evaluations[model_id] = {
                "id": model_id,
                "name": prof["displayName"],
                "provider": prof["provider"],
                "color": prof["color"],
                "inputCost": round(in_cost, 6),
                "outputCost": round(out_cost, 6),
                "totalCost": total_cost,
                "latencySec": latency_sec,
                "reasoningScore": prof["reasoningScore"]
            }

            # Efficiency Score calculation (Pareto tradeoff between reasoning capability, cost, and latency)
            if complexity_score > 75:
                # Premium reasoning task (favor Claude 3.5 Sonnet / GPT-4o)
                score = (prof["reasoningScore"] * 2.0) - (total_cost * 1500) - (latency_sec * 0.5)
            elif complexity_score > 45:
                # Balanced task
                score = (prof["reasoningScore"] * 1.0) - (total_cost * 3000) - (latency_sec * 1.0)
            else:
                # Simple/boilerplate task (favor Gemini Flash / GPT-4o-mini)
                score = (prof["reasoningScore"] * 0.5) - (total_cost * 6000) - (latency_sec * 1.5)

            candidate_scores.append((model_id, score))

        # Select highest Pareto score as recommended agent
        candidate_scores.sort(key=lambda x: x[1], reverse=True)
        recommended_agent_id = candidate_scores[0][0]
        recommended_profile = MODEL_PROFILES[recommended_agent_id]

        return {
            "predictedTokens": {
                "input": in_tokens,
                "output": out_tokens,
                "total": total_tokens
            },
            "complexityScore": complexity_score,
            "recommendedAgent": {
                "id": recommended_agent_id,
                "name": recommended_profile["displayName"],
                "provider": recommended_profile["provider"],
                "color": recommended_profile["color"],
                "estimatedCost": evaluations[recommended_agent_id]["totalCost"],
                "estimatedLatency": evaluations[recommended_agent_id]["latencySec"],
                "rationale": f"Optimal Pareto match for {complexity_score}/100 complexity requirement."
            },
            "modelEvaluations": evaluations
        }
