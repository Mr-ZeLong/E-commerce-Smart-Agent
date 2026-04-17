from app.context.masking import mask_context_parts


class TestMaskContextParts:
    def test_short_strings_passthrough(self):
        parts = ["short", "also short"]
        result = mask_context_parts(parts, max_chars=500)
        assert result == parts

    def test_long_string_gets_masked(self):
        long_text = "a" * 600
        result = mask_context_parts([long_text], max_chars=500)
        assert len(result) == 1
        assert "masked" in result[0]
        assert "original_length=600" in result[0]
        assert result[0].startswith("a" * 200)

    def test_mixed_short_and_long(self):
        parts = ["short", "b" * 550]
        result = mask_context_parts(parts, max_chars=500)
        assert result[0] == "short"
        assert "masked" in result[1]

    def test_newlines_replaced_in_masked_output(self):
        long_text = "line1\nline2\n" + "c" * 600
        result = mask_context_parts([long_text], max_chars=500)
        assert "\n" not in result[0]
        assert "masked" in result[0]

    def test_empty_list(self):
        assert mask_context_parts([], max_chars=500) == []
