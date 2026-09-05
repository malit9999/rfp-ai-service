"""반열린 구간 [start, end) 연산.

문서별로 분리해서 계산한다 — 다른 문서의 좌표는 서로 겹치지 않는다.
"""

from __future__ import annotations

from collections.abc import Iterable

Span = tuple[str, int, int]  # (document_id, start, end)


def _merge(spans: list[tuple[int, int]]) -> list[tuple[int, int]]:
    if not spans:
        return []
    spans = sorted(spans)
    out = [spans[0]]
    for s, e in spans[1:]:
        ls, le = out[-1]
        if s <= le:
            out[-1] = (ls, max(le, e))
        else:
            out.append((s, e))
    return out


def _by_doc(spans: Iterable[Span]) -> dict[str, list[tuple[int, int]]]:
    grouped: dict[str, list[tuple[int, int]]] = {}
    for doc, s, e in spans:
        grouped.setdefault(doc, []).append((s, e))
    return {d: _merge(v) for d, v in grouped.items()}


def union_length_by_doc(spans: Iterable[Span]) -> int:
    return sum(e - s for v in _by_doc(spans).values() for s, e in v)


def intersection_length_by_doc(a: Iterable[Span], b: Iterable[Span]) -> int:
    """두 구간 집합을 각각 합집합으로 만든 뒤 교집합 길이를 잰다."""
    ga, gb = _by_doc(a), _by_doc(b)
    total = 0
    for doc, ia in ga.items():
        ib = gb.get(doc)
        if not ib:
            continue
        i = j = 0
        while i < len(ia) and j < len(ib):
            s = max(ia[i][0], ib[j][0])
            e = min(ia[i][1], ib[j][1])
            if e > s:
                total += e - s
            if ia[i][1] < ib[j][1]:
                i += 1
            else:
                j += 1
    return total


def overlap_length(a_start: int, a_end: int, b_start: int, b_end: int) -> int:
    return max(0, min(a_end, b_end) - max(a_start, b_start))
