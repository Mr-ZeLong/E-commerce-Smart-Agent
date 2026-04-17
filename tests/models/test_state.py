from app.models.state import history_reducer


class TestHistoryReducer:
    def test_appends_without_compaction_marker(self):
        left = [{"role": "user", "content": "hi"}]
        right = [{"role": "assistant", "content": "hello"}]
        result = history_reducer(left, right)
        assert result == [
            {"role": "user", "content": "hi"},
            {"role": "assistant", "content": "hello"},
        ]

    def test_replaces_when_compaction_marker_present(self):
        left = [
            {"role": "user", "content": "q1"},
            {"role": "assistant", "content": "a1"},
        ]
        right = [{"role": "system", "content": "[summary]", "compacted": True}]
        result = history_reducer(left, right)
        assert result == [{"role": "system", "content": "[summary]", "compacted": True}]

    def test_empty_lists(self):
        assert history_reducer([], []) == []
        assert history_reducer([], [{"role": "user", "content": "hi"}]) == [
            {"role": "user", "content": "hi"}
        ]

    def test_multiple_compacted_messages_replace(self):
        left = [{"role": "user", "content": "old"}]
        right = [
            {"role": "system", "content": "[summary]", "compacted": True},
            {"role": "assistant", "content": "new"},
        ]
        result = history_reducer(left, right)
        assert result == right
