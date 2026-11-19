import unittest
from unittest.mock import patch

from backend.app import main


class VisionModelRoutingTests(unittest.TestCase):
    def test_nvidia_integrate_uses_supported_default_vision_model(self):
        with patch.object(main, "BASE_URL", "https://integrate.api.nvidia.com/v1"):
            with patch.object(main, "MODEL", "meta/llama-3.3-70b-instruct"):
                with patch.dict("os.environ", {"AI_VISION_MODEL": ""}):
                    self.assertEqual(
                        main._vision_model_name(),
                        "nvidia/nemotron-3-nano-omni-30b-a3b-reasoning",
                    )

    def test_explicit_vision_model_overrides_provider_default(self):
        with patch.object(main, "BASE_URL", "https://integrate.api.nvidia.com/v1"):
            with patch.dict("os.environ", {"AI_VISION_MODEL": "custom/vision-model"}):
                self.assertEqual(main._vision_model_name(), "custom/vision-model")

    def test_unknown_text_only_provider_does_not_claim_vision(self):
        with patch.object(main, "BASE_URL", "https://example.invalid/v1"):
            with patch.object(main, "MODEL", "meta/llama-text-only"):
                with patch.dict("os.environ", {"AI_VISION_MODEL": ""}):
                    self.assertEqual(main._vision_model_name(), "")

    def test_known_openai_vision_model_can_be_used_without_extra_setting(self):
        with patch.object(main, "BASE_URL", "https://api.openai.com/v1"):
            with patch.object(main, "MODEL", "gpt-4o-mini"):
                with patch.dict("os.environ", {"AI_VISION_MODEL": ""}):
                    self.assertEqual(main._vision_model_name(), "gpt-4o-mini")


if __name__ == "__main__":
    unittest.main()
