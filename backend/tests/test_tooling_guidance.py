import unittest

from backend.app.tooling import (
    RELIABILITY_AND_TASK_EXECUTION_GUIDANCE,
    build_tool_capabilities_prompt,
)


class AssistantBehaviorGuidanceTests(unittest.TestCase):
    def test_runtime_status_is_explicit_and_authoritative(self):
        prompt = build_tool_capabilities_prompt({
            "chat": True,
            "web_search": False,
            "vision": True,
            "file_generation": False,
            "transcription": True,
            "speech": True,
            "memory": False,
            "accounts": True,
        })
        self.assertIn("AI chat and reasoning: AVAILABLE", prompt)
        self.assertIn("Live web search: UNAVAILABLE", prompt)
        self.assertIn("Image understanding: AVAILABLE", prompt)
        self.assertIn("DOCX/PDF/XLSX file generation: UNAVAILABLE", prompt)

    def test_guidance_distinguishes_prompt_tuning_from_weight_training(self):
        self.assertIn("not model-weight training", RELIABILITY_AND_TASK_EXECUTION_GUIDANCE)
        self.assertIn("real training job", RELIABILITY_AND_TASK_EXECUTION_GUIDANCE)

    def test_guidance_requires_verified_actions_and_test_results(self):
        self.assertIn("Claim success only after receiving a successful result", RELIABILITY_AND_TASK_EXECUTION_GUIDANCE)
        self.assertIn("do not claim tests passed unless they ran", RELIABILITY_AND_TASK_EXECUTION_GUIDANCE)

    def test_guidance_preserves_current_task_context_and_language(self):
        self.assertIn("Do not make the user repeat information", RELIABILITY_AND_TASK_EXECUTION_GUIDANCE)
        self.assertIn("latest user's language and dialect", RELIABILITY_AND_TASK_EXECUTION_GUIDANCE)


if __name__ == "__main__":
    unittest.main()
