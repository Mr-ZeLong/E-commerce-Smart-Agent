"""Tests for observation masking utilities."""

from app.context.masking import mask_observation


def test_mask_observation_passes_small_values():
    data = {"status": "success", "count": 3}
    result = mask_observation(data, max_chars=500)
    assert result == data


def test_mask_observation_masks_large_string():
    data = {"description": "x" * 600}
    result = mask_observation(data, max_chars=500)
    assert result["description"]["_masked"] is True
    assert "original_length" in result["description"]


def test_mask_observation_mixed_values():
    data = {"status": "ok", "long_text": "a" * 1000, "count": 42}
    result = mask_observation(data, max_chars=500)
    assert result["status"] == "ok"
    assert result["count"] == 42
    assert result["long_text"]["_masked"] is True


def test_mask_observation_respects_custom_threshold():
    data = {"text": "x" * 50}
    result = mask_observation(data, max_chars=100)
    assert result["text"] == "x" * 50
    result = mask_observation(data, max_chars=10)
    assert result["text"]["_masked"] is True
