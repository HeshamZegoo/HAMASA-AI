import unittest

from backend.app.tooling import (
    RELIABILITY_AND_TASK_EXECUTION_GUIDANCE,
    TOOL_CAPABILITIES_PROMPT,
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

    def test_guidance_requires_tool_first_execution_before_limitation_claims(self):
        guidance = RELIABILITY_AND_TASK_EXECUTION_GUIDANCE
        self.assertIn('Before saying "I can\'t"', guidance)
        self.assertIn("inspect the tools, integrations", guidance)
        self.assertIn("execute, inspect the result", guidance)
        self.assertIn("closest safe alternative", guidance)

    def test_guidance_uses_relevant_tools_not_every_unrelated_tool(self):
        guidance = RELIABILITY_AND_TASK_EXECUTION_GUIDANCE
        self.assertIn("every tool relevant to the task", guidance)
        self.assertIn("Avoid redundant calls", guidance)
        self.assertIn("Continue through all safe independent steps", guidance)

    def test_guidance_distinguishes_prompt_tuning_from_weight_training(self):
        self.assertIn("real training job", RELIABILITY_AND_TASK_EXECUTION_GUIDANCE)

    def test_guidance_requires_verified_actions_and_test_results(self):
        self.assertIn("Claim success only after a successful result", RELIABILITY_AND_TASK_EXECUTION_GUIDANCE)
        self.assertIn("Never fabricate a tool call", RELIABILITY_AND_TASK_EXECUTION_GUIDANCE)

    def test_guidance_preserves_current_task_context_and_language(self):
        self.assertIn("latest user's language and dialect", RELIABILITY_AND_TASK_EXECUTION_GUIDANCE)

    def test_guidance_describes_real_github_read_and_external_tool_boundaries(self):
        guidance = " ".join((RELIABILITY_AND_TASK_EXECUTION_GUIDANCE + TOOL_CAPABILITIES_PROMPT).split())
        self.assertIn("isolated code-execution sandbox", guidance)
        self.assertIn("interactive browser automation", guidance)
        self.assertIn("github_read_file", guidance)
        self.assertIn("Gmail or Calendar", guidance)
        self.assertIn("image-generation service", guidance)
        self.assertIn("write alone is not proof", guidance)

    def test_large_commercial_site_requests_are_not_downgraded_to_mockups(self):
        guidance = RELIABILITY_AND_TASK_EXECUTION_GUIDANCE
        self.assertIn("Jumia or Amazon", guidance)
        self.assertIn("interactive frontend/demo", guidance)
        self.assertIn("Do not stop at explaining limitations", guidance)
        self.assertIn("demo checkout", guidance)
        self.assertIn("Do not ask the user to choose", guidance)


if __name__ == "__main__":
    unittest.main()
