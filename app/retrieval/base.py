"""검색 파이프라인 인터페이스.

라우터는 이 프로토콜만 알고, 어떤 검색기가 붙어 있는지는 모른다.
Dense·Hybrid를 나중에 붙일 때 라우터를 고치지 않기 위한 경계다.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable


@dataclass(frozen=True)
class Chunk:
    """색인 단위. 표와 본문을 구분해 두는 것은 RFP 질문의 상당수가 표에 있기 때문이다."""

    chunk_id: str
    document: str
    text: str
    kind: str = "unknown"
    meta: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class ScoredChunk:
    chunk: Chunk
    score: float


@runtime_checkable
class Retriever(Protocol):
    """검색기 계약.

    - `name`은 상태 보고와 응답에 그대로 실린다.
    - `search`는 점수 내림차순으로 최대 `top_k`개를 돌려준다.
    - 색인이 비어 있으면 예외가 아니라 빈 리스트다. "근거 없음"은 정상 상태다.
    """

    name: str

    def size(self) -> int: ...

    def search(self, query: str, top_k: int) -> list[ScoredChunk]: ...
