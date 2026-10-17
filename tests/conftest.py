import os
import uuid
from dataclasses import replace
import pytest
from app.config import Settings
from app.graph import GraphRepository


@pytest.fixture
def graph_repo():
    if os.getenv("RUN_GRAPH_TESTS") != "1":
        pytest.skip(
            "Set RUN_GRAPH_TESTS=1 with a reachable FalkorDB to run actual graph integration checks."
        )
    owned_name = "pg_test_" + uuid.uuid4().hex
    repo = GraphRepository(replace(Settings.load(), graph=owned_name))
    try:
        repo.initialize()
        yield repo
    finally:
        assert repo.settings.graph == owned_name and owned_name.startswith("pg_test_")
        repo.delete_test_graph()
