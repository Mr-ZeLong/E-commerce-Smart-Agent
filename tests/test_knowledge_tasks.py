import json
import os
import tempfile
from unittest.mock import MagicMock, patch

import pytest

from app.tasks.knowledge_tasks import load_documents, sync_knowledge_document


class TestLoadDocuments:
    def test_load_md_file(self):
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".md", delete=False, encoding="utf-8"
        ) as f:
            f.write("# Hello")
            path = f.name
        try:
            docs = load_documents(path)
            assert len(docs) == 1
            assert "# Hello" in docs[0].page_content
        finally:
            os.unlink(path)

    def test_load_json_file(self):
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False, encoding="utf-8"
        ) as f:
            json.dump({"key": "value"}, f)
            path = f.name
        try:
            docs = load_documents(path)
            assert len(docs) == 1
            assert '"key": "value"' in docs[0].page_content
        finally:
            os.unlink(path)

    def test_load_unsupported_file_raises(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".xyz", delete=False) as f:
            path = f.name
        try:
            with pytest.raises(ValueError, match="Unsupported file type"):
                load_documents(path)
        finally:
            os.unlink(path)


class TestRunEtlScript:
    def test_run_etl_script_success(self):
        from app.tasks.knowledge_tasks import _run_etl_script

        with patch("app.tasks.knowledge_tasks.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(stdout="ok", returncode=0)
            result = _run_etl_script("/tmp/data", recreate=False)
            assert result["status"] == "success"
            assert "ok" in result["output"]
            mock_run.assert_called_once()
            assert "--no-recreate" in mock_run.call_args.args[0]

    def test_run_etl_script_failure(self):
        from app.tasks.knowledge_tasks import _run_etl_script

        with patch("app.tasks.knowledge_tasks.subprocess.run") as mock_run:
            import subprocess

            mock_run.side_effect = subprocess.CalledProcessError(1, cmd=[], stderr="err")
            with pytest.raises(RuntimeError, match="ETL script failed"):
                _run_etl_script("/tmp/data")


class TestSyncKnowledgeDocument:
    def test_sync_knowledge_document_not_found(self):
        with pytest.raises(ValueError, match="Knowledge document 99999 not found"):
            sync_knowledge_document.run(99999)
