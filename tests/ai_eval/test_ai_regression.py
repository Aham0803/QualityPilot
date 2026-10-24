"""
AI Evaluation & Regression Suite.
Evaluates LLM standardizer output against fixed golden set (asserting >= 85% accuracy),
and asserts graceful handling of malformed JSON / low-confidence outputs.
"""

import json
import pytest
from src.ai.llm_client import LLMStewardClient
from src.ai.schemas import StandardizeLocationOutput

@pytest.fixture
def llm_client():
    return LLMStewardClient()

def test_ai_golden_set_regression(llm_client):
    with open("tests/ai_eval/golden_200_locations.json", "r", encoding="utf-8") as f:
        golden_cases = json.load(f)

    sys_prompt = "You are a data steward assistant. Standardize the city value."

    correct = 0
    total = len(golden_cases)

    for item in golden_cases:
        raw_val = item["input"]
        exp_city = item["expected_city"]
        
        output = llm_client.execute_structured_prompt(
            prompt_name="standardize_city",
            system_prompt=sys_prompt,
            user_prompt=raw_val,
            output_schema=StandardizeLocationOutput
        )

        if output.standardized_city.lower() == exp_city.lower():
            correct += 1

    accuracy = (correct / total) * 100.0
    print(f"\n[AI Evaluation] Accuracy on golden set: {accuracy:.1f}% ({correct}/{total})")
    assert accuracy >= 85.0, f"AI regression detected! Accuracy {accuracy}% dropped below 85% threshold."

def test_ai_low_confidence_and_garbage_handling(llm_client):
    sys_prompt = "You are a data steward assistant. Standardize the city value."
    output = llm_client.execute_structured_prompt(
        prompt_name="standardize_city",
        system_prompt=sys_prompt,
        user_prompt="xkcd9999_gibberish_123",
        output_schema=StandardizeLocationOutput
    )
    # Must assign low confidence for garbage
    assert output.confidence < 0.50
