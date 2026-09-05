"""metrics-v1 — 검색 평가 지표.

핵심 규칙
  - 좌표(evidence)를 **현재 chunker 의 chunk qrel 로 변환**한 뒤 순위 지표를 잰다.
    그래야 nDCG 가 1을 넘지 않는다. 대신 순위 지표는 chunker 에 묶인다.
  - strict 로 도달 불가능한 문항은 **task 수준에서 먼저 판정**하고(None),
    지표별로 예외 처리하지 않는다.
  - answerable 문항인데 any qrel 이 0개면 결과가 아니라 **자료 오류**다. 중단한다.
  - EvidenceCoverage@k 는 기준과 무관한 단일 값이고 모든 answerable 문항을 포함한다.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

from evaluation.intervals import intersection_length_by_doc, overlap_length
from evaluation.schema import (
    Chunk,
    EvalDataError,
    Question,
    Ranking,
    validate_chunks,
    validate_ks,
)

METRICS_VERSION = "metrics-v1"
CRITERIA = ("any", "strict")
STRICT_MIN_RATIO = 0.5
DEFAULT_KS = (1, 3, 5, 10)


# ── qrel 변환 ────────────────────────────────────────────────
def build_qrels(chunks: list[Chunk], question: Question, criterion: str) -> dict[str, int]:
    """evidence 좌표 → chunk 단위 qrel. grade 는 통과한 evidence 의 최댓값."""
    if criterion not in CRITERIA:
        raise EvalDataError(f"알 수 없는 기준: {criterion}")
    validate_chunks(chunks)

    qrels: dict[str, int] = {}
    for c in chunks:
        best = 0
        for e in question.evidence:
            if c.document_id != e.document_id:
                continue
            if c.extracted_text_sha256 != e.extracted_text_sha256:
                raise EvalDataError(
                    f"[{question.qid}] 같은 document_id({c.document_id}) 인데 "
                    f"extracted_text_sha256 이 다르다 — 좌표를 비교할 수 없다"
                )
            ov = overlap_length(c.char_start, c.char_end, e.char_start, e.char_end)
            if ov <= 0:
                continue
            if criterion == "strict" and ov / e.length < STRICT_MIN_RATIO:
                continue
            best = max(best, e.relevance_grade)
        if best >= 1:  # relevance_grade >= 1 을 적중으로 본다
            qrels[c.chunk_id] = best
    return qrels


# ── 개별 지표 ────────────────────────────────────────────────
def _dcg(grades: list[int]) -> float:
    return sum((2**g - 1) / math.log2(i + 2) for i, g in enumerate(grades))


def _ndcg_at_k(ranked_grades: list[int], qrel_grades: list[int], k: int) -> float | None:
    ideal = sorted(qrel_grades, reverse=True)[:k]
    idcg = _dcg(ideal)
    if idcg == 0:
        return None  # 도달 불가 판정이 먼저 걸리므로 여기 오면 자료 이상
    return _dcg(ranked_grades[:k]) / idcg


def _mrr(ranked_grades: list[int]) -> float:
    for i, g in enumerate(ranked_grades):
        if g >= 1:
            return 1.0 / (i + 1)
    return 0.0


# ── 문항 단위 결과 ───────────────────────────────────────────
@dataclass
class QuestionResult:
    qid: str
    qtype: str
    answerable: bool
    evidence_total_length: int
    evidence_span_count: int
    strict_reachable: bool
    any_qrel_size: int
    strict_qrel_size: int
    returned_count: dict[int, int] = field(default_factory=dict)
    coverage: dict[int, float] = field(default_factory=dict)
    # criterion -> metric -> k -> value(None 가능)
    ranked: dict[str, dict[str, dict[int, float | None]]] = field(default_factory=dict)


def evaluate_question(
    chunks: list[Chunk],
    question: Question,
    ranking: Ranking,
    ks: tuple[int, ...] = DEFAULT_KS,
) -> QuestionResult:
    ks = validate_ks(ks)
    validate_chunks(chunks)
    if ranking.qid != question.qid:
        raise EvalDataError(
            f"질문과 검색 결과의 qid 가 다르다: question={question.qid} ranking={ranking.qid}"
        )

    by_id = {c.chunk_id: c for c in chunks}
    unknown = [cid for cid in ranking.chunk_ids if cid not in by_id]
    if unknown:
        raise EvalDataError(f"[{question.qid}] 청크 목록에 없는 chunk_id: {unknown[:3]}")

    if not question.answerable:
        raise EvalDataError(
            f"[{question.qid}] 답변불가 문항은 순위 지표 대상이 아니다 — "
            "threshold sweep 으로 따로 평가한다"
        )

    qrels = {c: build_qrels(chunks, question, c) for c in CRITERIA}

    # answerable 인데 any qrel 이 0개 → 결과가 아니라 자료 오류
    if not qrels["any"]:
        raise EvalDataError(
            f"[{question.qid}] answerable 문항인데 any 기준 qrel 이 0개다. "
            "좌표·document_id·extracted_text_sha256·chunk 커버리지를 확인하라"
        )

    strict_reachable = bool(qrels["strict"])

    res = QuestionResult(
        qid=question.qid,
        qtype=question.qtype,
        answerable=True,
        evidence_total_length=question.evidence_total_length,
        evidence_span_count=question.evidence_span_count,
        strict_reachable=strict_reachable,
        any_qrel_size=len(qrels["any"]),
        strict_qrel_size=len(qrels["strict"]),
    )

    ev_spans = [(e.document_id, e.char_start, e.char_end) for e in question.evidence]
    for k in ks:
        top = ranking.chunk_ids[:k]
        res.returned_count[k] = len(top)
        got = [(by_id[c].document_id, by_id[c].char_start, by_id[c].char_end) for c in top]
        denom = question.evidence_total_length
        res.coverage[k] = intersection_length_by_doc(got, ev_spans) / denom if denom else 0.0

    for crit in CRITERIA:
        if crit == "strict" and not strict_reachable:
            res.ranked[crit] = {m: {k: None for k in ks} for m in ("hit", "precision", "ndcg")}
            res.ranked[crit]["mrr"] = {0: None}
            continue
        g = qrels[crit]
        ranked_grades = [g.get(cid, 0) for cid in ranking.chunk_ids]
        res.ranked[crit] = {
            "hit": {k: float(any(x >= 1 for x in ranked_grades[:k])) for k in ks},
            # 분모는 k 로 고정한다. 반환 부족은 returned_count 로 따로 보고한다
            "precision": {k: sum(1 for x in ranked_grades[:k] if x >= 1) / k for k in ks},
            "ndcg": {k: _ndcg_at_k(ranked_grades, list(g.values()), k) for k in ks},
            "mrr": {0: _mrr(ranked_grades)},
        }
    return res
