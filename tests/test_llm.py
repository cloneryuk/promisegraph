import pytest
from app.config import Settings
from app.llm import Gemini, ModelUnavailable
import app.llm as module


class Response:
    def __init__(self, status):
        self.status_code = status

    def json(self):
        return {
            "candidates": [{"content": {"role": "model", "parts": [{"text": "ok"}]}}]
        }


def stub(monkeypatch, statuses):
    results = iter(statuses)
    calls = []

    class Client:
        def __init__(self, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def post(self, *args, **kwargs):
            calls.append(1)
            return Response(next(results))

    monkeypatch.setattr(module.httpx, "Client", Client)
    monkeypatch.setattr(module.time, "sleep", lambda _: None)
    return calls


def test_transient_provider_failure_retried_once(monkeypatch):
    calls = stub(monkeypatch, [503, 200])
    _, raw = Gemini(Settings(api_key="test")).generate([], "test")
    assert len(calls) == 2 and raw["_promisegraph_http_attempts"] == [
        {"status_code": 503},
        {"status_code": 200},
    ]


def test_quota_failure_not_retried_in_a_burst(monkeypatch):
    calls = stub(monkeypatch, [429])
    with pytest.raises(ModelUnavailable) as exc:
        Gemini(Settings(api_key="test")).generate([], "test")
    assert len(calls) == 1 and exc.value.raw_response["http_attempts"] == [
        {"status_code": 429}
    ]


def test_repeated_provider_failure_is_not_a_fixture(monkeypatch):
    calls = stub(monkeypatch, [503, 503])
    with pytest.raises(ModelUnavailable):
        Gemini(Settings(api_key="test")).generate([], "test")
    assert len(calls) == 2
