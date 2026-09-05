"""설정 값 하나로 검색기를 고른다.

구현되지 않은 이름은 조용히 keyword로 떨어지지 않는다. 그러면 화면에는 결과가 뜨는데
실제로는 다른 검색기가 돌고 있는 상태가 되기 때문이다. 대신 요청 시점에 503으로 끊는다.
"""

from __future__ import annotations

from app.config import IMPLEMENTED_RETRIEVERS, KNOWN_RETRIEVERS, Settings
from app.retrieval.base import Chunk, Retriever, ScoredChunk
from app.retrieval.keyword import KeywordRetriever, load_corpus

NOT_IMPLEMENTED_DETAIL = "요청한 검색기는 아직 구현되지 않았습니다."


class UnavailableRetriever:
    """이름만 있고 구현이 없는 검색기 자리.

    search()가 불리면 예외를 던진다 — 라우터가 이것을 503 고정 문구로 바꾼다.
    """

    def __init__(self, name: str) -> None:
        self.name = name

    def size(self) -> int:
        return 0

    def search(self, query: str, top_k: int) -> list[ScoredChunk]:
        raise NotImplementedError(NOT_IMPLEMENTED_DETAIL)


def build_retriever(settings: Settings, chunks: list[Chunk] | None = None) -> Retriever:
    if settings.retriever not in IMPLEMENTED_RETRIEVERS:
        # 아는 이름이든 오타든 동작은 같다. 구현이 없으면 쓰지 않는다.
        name = settings.retriever if settings.retriever in KNOWN_RETRIEVERS else "unknown"
        return UnavailableRetriever(name)

    if chunks is None:
        chunks = load_corpus(settings.corpus_dir) if settings.corpus_dir else []
    return KeywordRetriever(chunks)
