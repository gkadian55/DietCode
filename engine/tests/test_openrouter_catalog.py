import os
import unittest
from unittest.mock import patch

from engine.openrouter_catalog import OpenRouterCatalog


class OpenRouterCatalogTests(unittest.TestCase):
    @patch.dict(os.environ, {"OPENROUTER_API_KEY": "test-key"}, clear=False)
    @patch("engine.openrouter_catalog.httpx.get")
    def test_refresh_keeps_only_approved_models_with_prices(self, get):
        get.return_value.raise_for_status.return_value = None
        get.return_value.json.return_value = {
            "data": [
                {
                    "id": "openai/gpt-4o",
                    "pricing": {"prompt": "0.0000025", "completion": "0.00001"},
                },
                {"id": "openai/gpt-4o-mini", "pricing": {}},
                {"id": "unapproved/model", "pricing": {"prompt": "1", "completion": "1"}},
            ]
        }

        catalog = OpenRouterCatalog()
        self.assertTrue(catalog.refresh())
        model = catalog.get("gpt-4o")
        self.assertIsNotNone(model)
        self.assertEqual(model.input_price_per_million, 2.5)
        self.assertIsNone(catalog.get("gpt-4o-mini"))
        self.assertFalse(catalog.get("unapproved/model"))

    @patch.dict(os.environ, {}, clear=True)
    def test_missing_key_does_not_make_cloud_available(self):
        catalog = OpenRouterCatalog()
        self.assertFalse(catalog.refresh())
        self.assertIsNone(catalog.get("gpt-4o"))


if __name__ == "__main__":
    unittest.main()
