"""macro 집계와 보고.

**분모와 제외 문항 수를 표시하지 않는 평균은 만들지 않는다.**
Mean 자료구조가 n·excluded 를 항상 함께 들고 다니고, 포맷터는 그 값 없이는 출력하지 않는다.
"""

from __future__ import annotations

from dataclasses import dataclass

from evaluation.metrics import CRITERIA, METRICS_VERSION, QuestionResult
from evaluation.schema import EvalDataError, validate_ks


@dataclass(frozen=True)
class Mean:
    """평균은 값 하나로 존재하지 않는다 — 분모와 제외 수가 함께 붙는다."""

    value: float | None
    n: int          # 평균에 실제로 들어간 문항 수 (분모)
    excluded: int   # 도달 불가로 빠진 문항 수

    def __str__(self) -> str:
        if self.value is None:
            return f"측정 불가 (n=0, 제외 {self.excluded})"
        return f"{self.value:.5f} (n={self.n}, 제외 {self.excluded})"


def _mean(values: list[float | None]) -> Mean:
    kept = [v for v in values if v is not None]
    excluded = len(values) - len(kept)
    if not kept:
        return Mean(None, 0, excluded)
    return Mean(sum(kept) / len(kept), len(kept), excluded)


@dataclass
class Aggregate:
    metrics_version: str
    answerable_count: int
    strict_reachable_count: int
    ks: tuple[int, ...]
    coverage: dict[int, Mean]
    returned_count: dict[int, Mean]
    ranked: dict[str, dict[str, dict[int, Mean]]]

    @property
    def strict_reachability_rate(self) -> float | None:
        if self.answerable_count == 0:
            return None
        return self.strict_reachable_count / self.answerable_count


def aggregate(results: list[QuestionResult], ks: tuple[int, ...]) -> Aggregate:
    ks = validate_ks(ks)
    if not results:
        raise EvalDataError("집계할 결과가 없다")
    qids = [r.qid for r in results]
    if len(set(qids)) != len(qids):
        raise EvalDataError("집계 대상에 같은 qid 가 두 번 들어 있다")
    if any(not r.answerable for r in results):
        raise EvalDataError("답변불가 문항이 순위 집계에 섞여 있다")

    agg = Aggregate(
        metrics_version=METRICS_VERSION,
        answerable_count=len(results),
        strict_reachable_count=sum(1 for r in results if r.strict_reachable),
        ks=ks,
        # Coverage 는 기준과 무관하고 모든 answerable 문항을 포함한다
        coverage={k: _mean([r.coverage[k] for r in results]) for k in ks},
        returned_count={k: _mean([float(r.returned_count[k]) for r in results]) for k in ks},
        ranked={},
    )
    for crit in CRITERIA:
        agg.ranked[crit] = {
            "hit": {k: _mean([r.ranked[crit]["hit"].get(k) for r in results]) for k in ks},
            "precision": {k: _mean([r.ranked[crit]["precision"].get(k) for r in results]) for k in ks},
            "ndcg": {k: _mean([r.ranked[crit]["ndcg"].get(k) for r in results]) for k in ks},
            "mrr": {0: _mean([r.ranked[crit]["mrr"].get(0) for r in results])},
        }
    return agg


def format_report(agg: Aggregate) -> str:
    """사람이 읽는 보고. 평균에는 반드시 n·제외 수가 붙는다."""
    L: list[str] = []
    L.append(f"metrics_version : {agg.metrics_version}")
    L.append(f"answerable      : {agg.answerable_count}문항")
    rate = agg.strict_reachability_rate
    L.append(
        f"strict 도달 가능 : {agg.strict_reachable_count}/{agg.answerable_count}"
        + (f"  (strict_reachability_rate = {rate:.4f})" if rate is not None else "")
    )
    L.append("")
    L.append("[ EvidenceCoverage@k — 기준 무관 단일 값 · 모든 answerable 문항 포함 ]")
    for k in agg.ks:
        L.append(f"  Coverage@{k:<3} {agg.coverage[k]}")
    L.append("")
    L.append("[ returned_count@k ]")
    for k in agg.ks:
        L.append(f"  returned@{k:<3} {agg.returned_count[k]}")
    for crit in CRITERIA:
        L.append("")
        L.append(f"[ 순위 지표 — {crit} 기준 ]")
        L.append(f"  MRR         {agg.ranked[crit]['mrr'][0]}")
        for name in ("hit", "precision", "ndcg"):
            for k in agg.ks:
                L.append(f"  {name}@{k:<8} {agg.ranked[crit][name][k]}")
    return "\n".join(L)
