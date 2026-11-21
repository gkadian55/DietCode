"""Approved OpenRouter model catalog with cached pricing."""

from __future__ import annotations

import logging
import os
import threading
import time
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Any

import httpx

logger = logging.getLogger(__name__)

OPENROUTER_API_URL = "https://openrouter.ai/api/v1/models"
CATALOG_REFRESH_SECONDS = 6 * 60 * 60

# Stable DietCode model keys are mapped to explicit OpenRouter model IDs.
APPROVED_OPENROUTER_MODELS = {
    "gemini-2-0-flash": "google/gemini-2.0-flash-001",
    "gemini-3-5-flash-lite": "google/gemini-3.5-flash-lite",
    "claude-3-5-sonnet": "anthropic/claude-3.5-sonnet",
    "claude-3-5-haiku": "anthropic/claude-3.5-haiku",
    "gpt-4o": "openai/gpt-4o",
    "gpt-4o-mini": "openai/gpt-4o-mini",
}
LEGACY_MODEL_KEYS = {
    "openai/gpt-4o": "gpt-4o",
    "openai/gpt-4o-mini": "gpt-4o-mini",
    "gemini-3-8-flash": "gemini-3-5-flash-lite",
    "gemini/gemini-3.5-flash-lite": "gemini-3-5-flash-lite",
    "anthropic/claude-3-5-sonnet-20241022": "claude-3-5-sonnet",
    "anthropic/claude-3-5-haiku-20241022": "claude-3-5-haiku",
}


@dataclass(frozen=True)
class CatalogModel:
    key: str
    openrouter_id: str
    input_price_per_million: Decimal
    output_price_per_million: Decimal
    synced_at: float


class OpenRouterCatalog:
    """Thread-safe in-memory catalog refreshed at startup and every six hours."""

    def __init__(self) -> None:
        self._models: dict[str, CatalogModel] = {}
        self._last_refresh: float | None = None
        self._lock = threading.Lock()

    @property
    def last_refresh(self) -> float | None:
        return self._last_refresh

    def get(self, model_key: str) -> CatalogModel | None:
        normalized_key = model_key.lower().strip()
        model_key = LEGACY_MODEL_KEYS.get(normalized_key, normalized_key)
        with self._lock:
            model = self._models.get(model_key)
            if model is None:
                return None
            if time.time() - model.synced_at >= CATALOG_REFRESH_SECONDS:
                return None
            return model

    def refresh(self) -> bool:
        """Refresh approved models; retain the last good cache on failure."""
        api_key = os.getenv("OPENROUTER_API_KEY", "").strip()
        if not api_key:
            logger.warning("OpenRouter catalog unavailable: OPENROUTER_API_KEY is missing")
            return False

        try:
            response = httpx.get(
                OPENROUTER_API_URL,
                headers={"Authorization": f"Bearer {api_key}"},
                timeout=20,
            )
            response.raise_for_status()
            payload = response.json()
            models_by_id = {
                item.get("id"): item
                for item in payload.get("data", [])
                if isinstance(item, dict) and item.get("id")
            }
            synced_at = time.time()
            refreshed: dict[str, CatalogModel] = {}
            for key, openrouter_id in APPROVED_OPENROUTER_MODELS.items():
                item = models_by_id.get(openrouter_id)
                pricing = item.get("pricing", {}) if item else {}
                input_price = _price_per_million(pricing.get("prompt"))
                output_price = _price_per_million(pricing.get("completion"))
                if item is None or input_price is None or output_price is None:
                    logger.warning(
                        "OpenRouter model %s is unavailable or has no pricing",
                        openrouter_id,
                    )
                    continue
                refreshed[key] = CatalogModel(
                    key=key,
                    openrouter_id=openrouter_id,
                    input_price_per_million=input_price,
                    output_price_per_million=output_price,
                    synced_at=synced_at,
                )

            with self._lock:
                self._models = refreshed
                self._last_refresh = synced_at
            logger.info("OpenRouter catalog refreshed: %d approved models available", len(refreshed))
            return True
        except (httpx.HTTPError, AttributeError, ValueError, TypeError) as err:
            logger.warning("OpenRouter catalog refresh failed: %s", err)
            return False


def _price_per_million(value: Any) -> Decimal | None:
    try:
        price = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return None
    if price < 0:
        return None
    return (price * Decimal("1000000")).quantize(Decimal("0.000001"))


catalog = OpenRouterCatalog()
