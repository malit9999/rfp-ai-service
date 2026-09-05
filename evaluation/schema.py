"""평가 자료구조.

좌표는 **정규화된 추출 텍스트** 기준이다(docs/EXTRACTION_CONTRACT.md §1).
document_id 와 extracted_text_sha256 이 모두 같을 때만 겹침을 인정한다.
"""

from __future__ import annotations

from dataclasses import dataclass, field

ANSWERABLE_TYPES = frozenset({"single", "followup", "filter"})
UNANSWERABLE_TYPE = "unanswerable"

#: 허용하는 등급. 0(무관)은 라벨로 쓰지 않는다 — 무관하면 라벨하지 않는다.
ALLOWED_GRADES = frozenset({1, 2})


class EvalDataError(Exception):
    """평가를 계속하면 안 되는 자료 오류. 0점으로 넘어가지 않는다."""


@dataclass(frozen=True)
class Chunk:
    chunk_id: str
    document_id: str
    extracted_text_sha256: str
    char_start: int
    char_end: int

    def __post_init__(self) -> None:
        if self.char_start < 0:
            raise EvalDataError(f"chunk char_start 가 음수다: {self.chunk_id}")
        if self.char_end <= self.char_start:
            raise EvalDataError(f"chunk 구간이 비었다: {self.chunk_id}")

    @property
    def length(self) -> int:
        return self.char_end - self.char_start


@dataclass(frozen=True)
class Evidence:
    document_id: str
    extracted_text_sha256: str
    char_start: int
    char_end: int
    relevance_grade: int = 2

    def __post_init__(self) -> None:
        if self.char_start < 0:
            raise EvalDataError("evidence char_start 가 음수다")
        if self.char_end <= self.char_start:
            raise EvalDataError("evidence 구간이 비었다")
        if self.relevance_grade not in ALLOWED_GRADES:
            raise EvalDataError(
                f"relevance_grade 는 {sorted(ALLOWED_GRADES)} 만 허용한다: "
                f"{self.relevance_grade}"
            )

    @property
    def length(self) -> int:
        return self.char_end - self.char_start


@dataclass(frozen=True)
class Question:
    """평가 문항.

    라벨 규칙(문서에도 적는다):
      - evidence 길이를 인위적으로 제한하지 않는다
      - 답을 뒷받침하는 **최소한의 완결된 의미 단위**로 라벨링한다
      - 논리적으로 독립된 근거일 때만 여러 span으로 나눈다
      - strict 지표에 맞추려고 ground truth 를 자르지 않는다
    """

    qid: str
    qtype: str
    evidence: tuple[Evidence, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        if self.qtype not in ANSWERABLE_TYPES | {UNANSWERABLE_TYPE}:
            raise EvalDataError(f"알 수 없는 유형: {self.qtype}")
        if self.qtype == UNANSWERABLE_TYPE and self.evidence:
            raise EvalDataError(f"답변불가 문항에 evidence 가 있다: {self.qid}")
        if self.qtype in ANSWERABLE_TYPES and not self.evidence:
            raise EvalDataError(f"답변 가능 문항에 evidence 가 없다: {self.qid}")

    @property
    def answerable(self) -> bool:
        return self.qtype in ANSWERABLE_TYPES

    @property
    def evidence_total_length(self) -> int:
        """겹치는 span 을 합집합으로 계산한 총 근거 길이."""
        from evaluation.intervals import union_length_by_doc

        return union_length_by_doc(
            [(e.document_id, e.char_start, e.char_end) for e in self.evidence]
        )

    @property
    def evidence_span_count(self) -> int:
        return len(self.evidence)


@dataclass(frozen=True)
class Ranking:
    """검색 결과. chunk_id 를 순위 순서대로 담는다.

    같은 chunk 가 두 번 들어오면 거부한다 — 중복을 허용하면 같은 근거가
    DCG 에 두 번 더해져 nDCG 가 부풀려진다.
    """

    qid: str
    chunk_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        seen: set[str] = set()
        dup = [c for c in self.chunk_ids if c in seen or seen.add(c)]
        if dup:
            raise EvalDataError(
                f"[{self.qid}] 검색 결과에 중복 chunk_id 가 있다: {sorted(set(dup))[:3]}"
            )


def validate_chunks(chunks: list[Chunk]) -> None:
    """chunk_id 중복을 거부한다. 중복이면 qrel·순위 대조가 모두 어긋난다."""
    seen: set[str] = set()
    dup = [c.chunk_id for c in chunks if c.chunk_id in seen or seen.add(c.chunk_id)]
    if dup:
        raise EvalDataError(f"chunk_id 가 중복된다: {sorted(set(dup))[:3]}")


def validate_ks(ks: tuple[int, ...]) -> tuple[int, ...]:
    """k 목록 검증 — 양의 정수, 중복 없음."""
    if not ks:
        raise EvalDataError("ks 가 비었다")
    bad = [k for k in ks if not isinstance(k, int) or isinstance(k, bool) or k < 1]
    if bad:
        raise EvalDataError(f"ks 는 양의 정수여야 한다: {bad}")
    if len(set(ks)) != len(ks):
        raise EvalDataError(f"ks 에 중복이 있다: {ks}")
    return ks
