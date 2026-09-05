from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app
from app.retrieval.base import Chunk

CHUNKS = [
    Chunk(chunk_id="a#0", document="a.txt", text="사업 예산 총액은 3억원이다", kind="text"),
    Chunk(chunk_id="c#0", document="c.txt", text="평가 배점은 기술 80점 가격 20점", kind="table"),
]


def client(**kwargs) -> TestClient:
    return TestClient(create_app(Settings(**kwargs), CHUNKS))


def test_retrieve_returns_evidence_with_source():
    res = client().post("/retrieve", json={"query": "예산 총액"})
    assert res.status_code == 200
    body = res.json()
    assert body["retriever"] == "keyword"
    assert body["chunks"][0]["document"] == "a.txt"
    assert body["chunks"][0]["chunk_id"] == "a#0"


def test_retrieve_top_k_is_capped_by_settings():
    res = client(max_top_k=1).post("/retrieve", json={"query": "사업", "top_k": 50})
    assert res.json()["top_k"] == 1


def test_retrieve_rejects_empty_query():
    assert client().post("/retrieve", json={"query": ""}).status_code == 422


def test_ask_never_answers_without_a_generator():
    body = client().post("/ask", json={"query": "예산 총액"}).json()
    assert body["answer"] is None
    assert body["answer_status"] == "evidence_only"
    assert body["evidence"]


def test_ask_marks_no_evidence_separately():
    body = client().post("/ask", json={"query": "항공권 예약"}).json()
    assert body["answer_status"] == "no_evidence"
    assert body["evidence"] == []


def test_table_chunk_kind_is_preserved():
    body = client().post("/retrieve", json={"query": "배점 기술"}).json()
    assert body["chunks"][0]["kind"] == "table"


def test_unimplemented_retriever_returns_503_fixed_message():
    res = TestClient(create_app(Settings(retriever="dense"), CHUNKS)).post(
        "/retrieve", json={"query": "예산"}
    )
    assert res.status_code == 503
    assert res.json() == {"detail": "요청한 검색기는 아직 구현되지 않았습니다."}
