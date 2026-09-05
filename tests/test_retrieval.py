import pytest

from app.config import Settings
from app.retrieval import KeywordRetriever, UnavailableRetriever, build_retriever
from app.retrieval.base import Chunk
from app.retrieval.keyword import load_corpus, tokenize

CHUNKS = [
    Chunk(chunk_id="a#0", document="a.txt", text="사업 예산 총액은 3억원이다", kind="text"),
    Chunk(chunk_id="b#0", document="b.txt", text="제출 서류는 사업자등록증과 실적증명서", kind="text"),
    Chunk(chunk_id="c#0", document="c.txt", text="평가 배점은 기술 80점 가격 20점", kind="table"),
]


def test_tokenize_keeps_hangul_and_numbers():
    assert tokenize("예산 3억원, RFP-2026!") == ["예산", "3억원", "rfp", "2026"]


def test_search_ranks_matching_chunk_first():
    hits = KeywordRetriever(CHUNKS).search("예산 총액", top_k=3)
    assert hits
    assert hits[0].chunk.chunk_id == "a#0"


def test_search_respects_top_k():
    assert len(KeywordRetriever(CHUNKS).search("사업", top_k=1)) == 1


def test_no_match_returns_empty_not_error():
    """근거 없음은 정상 상태다 — 억지로 무언가를 돌려주지 않는다."""
    assert KeywordRetriever(CHUNKS).search("항공권 예약", top_k=5) == []


def test_empty_index_returns_empty():
    assert KeywordRetriever([]).search("예산", top_k=5) == []


def test_scores_are_descending():
    hits = KeywordRetriever(CHUNKS).search("사업 예산 제출", top_k=5)
    assert [h.score for h in hits] == sorted((h.score for h in hits), reverse=True)


def test_unimplemented_retriever_raises_instead_of_falling_back():
    """dense를 요청했는데 keyword가 도는 상황을 만들지 않는다."""
    retriever = build_retriever(Settings(retriever="dense"))
    assert isinstance(retriever, UnavailableRetriever)
    with pytest.raises(NotImplementedError):
        retriever.search("예산", top_k=3)


def test_unknown_retriever_name_is_not_treated_as_known():
    assert build_retriever(Settings(retriever="typo")).name == "unknown"


def test_load_corpus_reads_text_files(tmp_path):
    (tmp_path / "one.txt").write_text("예산 3억원", encoding="utf-8")
    (tmp_path / "two.md").write_text("제출 서류", encoding="utf-8")
    (tmp_path / "skip.pdf").write_bytes(b"%PDF-")
    (tmp_path / "empty.txt").write_text("   ", encoding="utf-8")

    chunks = load_corpus(tmp_path)
    assert [c.document for c in chunks] == ["one.txt", "two.md"]


def test_load_corpus_missing_dir_is_empty():
    assert load_corpus("/tmp/directory-that-should-not-exist-rfp") == []
