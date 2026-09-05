from fastapi.testclient import TestClient

from app.config import Settings, load_settings
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
    assert by_name["generation"]["status"] == "not_implemented"


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


def test_generation_never_ready_even_with_key_and_model(monkeypatch):
    """환경 변수가 채워져 있어도 생성기는 ready가 되지 않는다.

    키와 모델명이 있다는 것은 "설정이 있다"는 뜻이지 "코드가 있다"는 뜻이 아니다.
    값만 보고 ready로 보고하면 /ask가 answer: null을 돌려주는 실제 동작과 어긋난다.
    """
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    monkeypatch.setenv("RFP_ANSWER_MODEL", "gpt-5.4-mini")

    settings = load_settings()
    app = create_app(settings, [Chunk(chunk_id="a#0", document="a.txt", text="예산", kind="text")])
    body = TestClient(app).get("/health").json()

    generation = next(c for c in body["components"] if c["name"] == "generation")
    assert generation["status"] == "not_implemented"
    assert body["status"] == "degraded"


def test_ask_matches_health_when_generation_env_is_set(monkeypatch):
    """/health가 not_implemented면 /ask도 답변을 만들지 않는다 — 둘이 어긋나면 안 된다."""
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    monkeypatch.setenv("RFP_ANSWER_MODEL", "gpt-5.4-mini")

    app = create_app(
        load_settings(),
        [Chunk(chunk_id="a#0", document="a.txt", text="예산 총액은 3억원", kind="text")],
    )
    client = TestClient(app)

    generation = next(
        c for c in client.get("/health").json()["components"] if c["name"] == "generation"
    )
    body = client.post("/ask", json={"query": "예산 총액"}).json()

    assert generation["status"] == "not_implemented"
    assert body["answer"] is None
    assert body["answer_status"] == "evidence_only"
