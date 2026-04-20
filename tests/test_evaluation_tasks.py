from unittest.mock import patch

import pytest

from app.tasks.evaluation_tasks import _run_few_shot_evaluation


@pytest.mark.asyncio
async def test_run_few_shot_evaluation():
    with (
        patch("app.tasks.evaluation_tasks.create_llm") as mock_create_llm,
        patch("app.tasks.evaluation_tasks.compare_few_shot_performance") as mock_compare,
    ):
        mock_llm = object()
        mock_create_llm.return_value = mock_llm
        mock_compare.return_value = {
            "baseline_accuracy": 0.80,
            "few_shot_accuracy": 0.85,
            "improvement": 0.05,
            "meets_target": True,
        }

        result = await _run_few_shot_evaluation()

        mock_create_llm.assert_called_once_with(
            mock_create_llm.call_args[0][0],
            temperature=0.0,
            default_config={
                "metadata": {"agent_name": "few_shot_evaluator"},
                "tags": ["evaluation", "internal"],
            },
        )
        mock_compare.assert_called_once_with(mock_llm)
        assert result["improvement"] == 0.05
        assert result["meets_target"] is True
