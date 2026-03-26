import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from saas.adapters.mirofish_adapter import MiroFishAdapter, MiroFishConfig, SimulationResult


def test_mirofish_config_creation():
    config = MiroFishConfig(
        llm_api_key="test-key",
        llm_base_url="http://localhost:8000/v1",
        llm_model_name="test-model",
        zep_api_key="test-zep",
        seed_text="Some seed text about markets",
        goal="Predict market reaction",
        max_rounds=50,
    )
    assert config.llm_api_key == "test-key"
    assert config.max_rounds == 50


def test_mirofish_config_to_env_dict():
    config = MiroFishConfig(
        llm_api_key="key",
        llm_base_url="http://localhost:8000/v1",
        llm_model_name="model",
        zep_api_key="zep",
        seed_text="seed",
        goal="goal",
        max_rounds=100,
    )
    env = config.to_env_dict()
    assert env["LLM_API_KEY"] == "key"
    assert env["LLM_BASE_URL"] == "http://localhost:8000/v1"
    assert env["LLM_MODEL_NAME"] == "model"
    assert env["ZEP_API_KEY"] == "zep"
    assert env["OASIS_DEFAULT_MAX_ROUNDS"] == "100"


def test_simulation_result_from_files():
    result = SimulationResult(
        report_markdown="# Prediction\nMarkets will rise.",
        chat_log=[
            {"agent": "Agent_1", "message": "I think markets go up"},
            {"agent": "Agent_2", "message": "Agree, bullish sentiment"},
        ],
        total_rounds=50,
        total_actions=1200,
    )
    assert "Markets will rise" in result.report_markdown
    assert len(result.chat_log) == 2
    assert result.total_rounds == 50


def test_adapter_build_env_from_config_and_routing():
    adapter = MiroFishAdapter(mirofish_path="/fake/path")
    config = MiroFishConfig(
        llm_api_key="key",
        llm_base_url="http://vllm:8000/v1",
        llm_model_name="Qwen2.5-32B-Instruct-AWQ",
        zep_api_key="zep",
        seed_text="seed",
        goal="goal",
        max_rounds=200,
    )
    env = adapter.build_env(config)
    assert env["LLM_API_KEY"] == "key"
    assert env["LLM_BASE_URL"] == "http://vllm:8000/v1"
    assert env["LLM_MODEL_NAME"] == "Qwen2.5-32B-Instruct-AWQ"
