from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path


MODULE_PATH = Path(__file__).parents[1] / "build_public_llm_price_catalog.py"
SPEC = importlib.util.spec_from_file_location("build_public_llm_price_catalog", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class PublicPriceCatalogTests(unittest.TestCase):
    def test_only_token_priced_chat_models_are_normalized(self) -> None:
        source = {
            "sample_spec": {},
            "vendor/model": {
                "mode": "chat", "litellm_provider": "vendor",
                "input_cost_per_token": 0.000001, "output_cost_per_token": 0.000004,
            },
            "vendor/image": {"mode": "image_generation", "output_cost_per_image": 0.1},
        }

        catalog = MODULE.normalize(source, "https://example.test/map.json", "2026-07-13T00:00:00+00:00")

        self.assertEqual(catalog["statistics"], {"api_models": 1, "providers": 1})
        self.assertEqual(catalog["entries"][0]["input_price_per_1m"], 1)
        self.assertEqual(catalog["entries"][0]["output_price_per_1m"], 4)

    def test_compute_base_catalog_is_merged(self) -> None:
        catalog = {"entries": [], "statistics": {}}
        base = {
            "entries": [{"id": "compute:vendor:gpu", "type": "rented_compute"}],
            "sources": [{"provider": "vendor"}],
            "reference_only": [{"provider": "dynamic"}],
        }

        merged = MODULE.merge_base_catalog(catalog, base)

        self.assertEqual(merged["statistics"]["compute_offers"], 1)
        self.assertEqual(merged["entries"][0]["id"], "compute:vendor:gpu")
        self.assertEqual(merged["reference_only"][0]["provider"], "dynamic")


if __name__ == "__main__":
    unittest.main()
