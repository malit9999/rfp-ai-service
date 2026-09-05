"""외부 의존 없이 도는 기준 검색기.

BM25가 아니라 **토큰 겹침 + 문서 빈도 역가중**이다. 목적은 성능이 아니라
"라우터부터 응답 스키마까지 실제로 한 번 통하는 경로"를 갖는 것이다.
성능 비교 대상으로 쓰면 안 된다.
"""

from __future__ import annotations

import math
import re
from collections import Counter
from pathlib import Path

from app.retrieval.base import Chunk, ScoredChunk

# 한글·영문·숫자만 남긴다. 형태소 분석은 하지 않는다(의존성을 늘리지 않으려고).
_TOKEN = re.compile(r"[0-9A-Za-z가-힣]+")


def tokenize(text: str) -> list[str]:
    return [t.lower() for t in _TOKEN.findall(text)]


class KeywordRetriever:
    name = "keyword"

    def __init__(self, chunks: list[Chunk] | None = None) -> None:
        self._chunks: list[Chunk] = []
        self._tokens: list[Counter[str]] = []
        self._doc_freq: Counter[str] = Counter()
        for chunk in chunks or []:
            self.add(chunk)

    def add(self, chunk: Chunk) -> None:
        tokens = Counter(tokenize(chunk.text))
        self._chunks.append(chunk)
        self._tokens.append(tokens)
        self._doc_freq.update(tokens.keys())

    def size(self) -> int:
        return len(self._chunks)

    def search(self, query: str, top_k: int) -> list[ScoredChunk]:
        terms = tokenize(query)
        if not terms or not self._chunks:
            return []

        n = len(self._chunks)
        scored: list[ScoredChunk] = []
        for chunk, tokens in zip(self._chunks, self._tokens, strict=True):
            total = sum(tokens.values()) or 1
            score = 0.0
            for term in terms:
                tf = tokens.get(term, 0)
                if not tf:
                    continue
                # 흔한 단어일수록 가중치를 낮춘다.
                idf = math.log(1 + n / (1 + self._doc_freq[term]))
                score += (tf / total) * idf
            if score > 0:
                scored.append(ScoredChunk(chunk=chunk, score=round(score, 6)))

        scored.sort(key=lambda s: (-s.score, s.chunk.chunk_id))
        return scored[:top_k]


def load_corpus(directory: str | Path) -> list[Chunk]:
    """디렉터리의 .txt/.md를 한 파일 = 한 chunk로 읽는다.

    실제 RFP는 HWP·PDF이고 표 분리가 필요하다. 그 부분은 아직 없다 —
    여기서는 파이프라인이 통하는지 확인할 수 있는 최소 로더만 둔다.
    """
    root = Path(directory)
    if not root.is_dir():
        return []

    chunks: list[Chunk] = []
    for path in sorted(root.rglob("*")):
        if path.suffix.lower() not in {".txt", ".md"} or not path.is_file():
            continue
        text = path.read_text(encoding="utf-8", errors="replace").strip()
        if not text:
            continue
        chunks.append(
            Chunk(
                chunk_id=f"{path.stem}#0",
                document=path.name,
                text=text,
                kind="text",
            )
        )
    return chunks
