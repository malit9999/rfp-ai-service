from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app
from app.retrieval.base import Chunk


def client(**kwargs):
    settings = Settings(**{"retriever": "keyword", **kwargs})
    chunks = [Chunk(chunk_id="a#0", document="a.txt", text="예산 총액은 3억원이다", kind="text")]
    return TestClient(create_app(settings, chunks))


def test_health_reports_every_component():
    res = client().get("/health")
    assert res.status_code == 200
    body = res.json()
    names = {c["name"] for c in body["components"]}
    assert names == {"retriever:keyword", "reranker", "generation"}


def test_health_is_degraded_while_parts_are_missing():
    """미구현 부분이 있는 동안 상태를 ok로 보고하지 않는다."""
    body = client().get("/health").json()
    assert body["status"] == "degraded"
    by_name = {c["name"]: c for c in body["components"]}
    assert by_name["reranker"]["status"] == "not_implemented"
    assert by_name["generation"]["status"] == "disabled"


def test_health_counts_indexed_chunks():
    body = client().get("/health").json()
    retriever = next(c for c in body["components"] if c["name"].startswith("retriever:"))
    assert retriever["status"] == "ready"
    assert retriever["detail"] == "indexed_chunks=1"


def test_unimplemented_retriever_is_reported_not_hidden():
    body = client(retriever="dense").get("/health").json()
    retriever = next(c for c in body["components"] if c["name"].startswith("retriever:"))
    assert retriever["name"] == "retriever:dense"
    assert retriever["status"] == "not_implemented"
