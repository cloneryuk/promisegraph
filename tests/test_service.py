from types import SimpleNamespace
from unittest.mock import Mock
import pytest
from app.config import Settings
from app.demo import examples
from app.graph import ReviewConflict
from app.schemas import DocumentInput
from app.service import Service


def test_live_proposals_cannot_be_auto_accepted_by_rehearsal():
    repo = Mock(settings=Settings())
    repo.document.return_value = {"id": "existing", "state": "ready", "mode": "live"}
    item = examples()["baseline"][0]
    service = Service(repo, model=SimpleNamespace())
    with pytest.raises(ReviewConflict, match="different extraction mode"):
        service.ingest(
            DocumentInput.model_validate(item["document"]), "rehearsal", item["fixture"]
        )
    repo.save_facts.assert_not_called()
    repo.review.assert_not_called()


def test_concurrent_same_document_ingestion_is_rejected():
    repo = Mock(settings=Settings())
    repo.document.return_value = {
        "id": "existing",
        "state": "extracting",
        "mode": "live",
    }
    service = Service(repo, model=SimpleNamespace())
    with pytest.raises(ReviewConflict, match="already extracting"):
        service.ingest(
            DocumentInput.model_validate(examples()["baseline"][0]["document"])
        )
    repo.save_document.assert_not_called()
