import pytest

from app.tasks.knowledge_tasks import sync_knowledge_document


class TestSyncKnowledgeDocument:
    def test_sync_knowledge_document_not_found(self):
        with pytest.raises(ValueError, match="Knowledge document 99999 not found"):
            sync_knowledge_document.run(99999)
