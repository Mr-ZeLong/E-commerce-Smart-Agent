from unittest.mock import Mock, patch

from app.tasks.autoheal import check_celery_workers, clear_redis_cache


class TestCheckCeleryWorkers:
    @patch("app.tasks.autoheal.Control")
    def test_restarts_stuck_worker(self, mock_control_class):
        mock_control = Mock()
        mock_control_class.return_value = mock_control

        mock_control.inspect.return_value.stats.return_value = {"worker1": {"uptime": 4000}}
        mock_control.inspect.return_value.active.return_value = {"worker1": [{"task": "some.task"}]}

        result = check_celery_workers.run()

        assert result["restarted_workers"] == 1
        mock_control.broadcast.assert_called_once_with("shutdown", destination=["worker1"])

    @patch("app.tasks.autoheal.Control")
    def test_no_restart_when_worker_fresh(self, mock_control_class):
        mock_control = Mock()
        mock_control_class.return_value = mock_control

        mock_control.inspect.return_value.stats.return_value = {"worker1": {"uptime": 100}}
        mock_control.inspect.return_value.active.return_value = {"worker1": [{"task": "some.task"}]}

        result = check_celery_workers.run()

        assert result["restarted_workers"] == 0
        mock_control.broadcast.assert_not_called()

    @patch("app.tasks.autoheal.Control")
    def test_no_restart_when_no_active_tasks(self, mock_control_class):
        mock_control = Mock()
        mock_control_class.return_value = mock_control

        mock_control.inspect.return_value.stats.return_value = {"worker1": {"uptime": 4000}}
        mock_control.inspect.return_value.active.return_value = {"worker1": []}

        result = check_celery_workers.run()

        assert result["restarted_workers"] == 0

    @patch("app.tasks.autoheal.Control")
    def test_handles_inspect_failure(self, mock_control_class):
        mock_control = Mock()
        mock_control_class.return_value = mock_control
        mock_control.inspect.return_value.stats.side_effect = RuntimeError("boom")

        result = check_celery_workers.run()

        assert result["restarted_workers"] == 0
        assert "error" in result


class TestClearRedisCache:
    @patch("app.tasks.autoheal.sync_redis.from_url")
    def test_clears_cache_when_memory_high(self, mock_from_url):
        mock_client = Mock()
        mock_from_url.return_value = mock_client

        mock_client.info.side_effect = [
            {"used_memory": 600 * 1024 * 1024},
            {"used_memory": 400 * 1024 * 1024},
        ]
        mock_client.scan_iter.return_value = ["cache:key1", "cache:key2"]

        result = clear_redis_cache.run(memory_threshold_mb=512.0)

        assert result["keys_removed"] == 6
        assert result["memory_before_mb"] >= 512.0
        mock_client.close.assert_called_once()

    @patch("app.tasks.autoheal.sync_redis.from_url")
    def test_no_clear_when_memory_low(self, mock_from_url):
        mock_client = Mock()
        mock_from_url.return_value = mock_client

        mock_client.info.return_value = {"used_memory": 100 * 1024 * 1024}

        result = clear_redis_cache.run(memory_threshold_mb=512.0)

        assert result["keys_removed"] == 0
        mock_client.delete.assert_not_called()
        mock_client.close.assert_called_once()

    @patch("app.tasks.autoheal.sync_redis.from_url")
    def test_handles_redis_connection_error(self, mock_from_url):
        mock_from_url.side_effect = ConnectionError("refused")

        result = clear_redis_cache.run()

        assert "error" in result
