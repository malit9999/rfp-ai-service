"""metrics-v1 회귀 테스트.

기대값은 **손으로 계산해 확정한 값**이다(민성님 검산 + 재검산).
구현이 이 값을 바꾸면 테스트가 깨진다.
"""

import pytest

from evaluation import (
    Chunk, EvalDataError, Evidence, Question, Ranking,
    aggregate, build_qrels, evaluate_question, format_report,
)

H = "sha-doc001"
KS = (1, 3, 5)


def chunks():
    return [
        Chunk(f"c{i}", "doc-001", H, i * 100, (i + 1) * 100) for i in range(5)
    ]


Q1 = Question("q1", "single", (Evidence("doc-001", H, 100, 200, 2),))
R1 = Ranking("q1", ("c3", "c1", "c0", "c4", "c2"))
Q2 = Question("q2", "single", (Evidence("doc-001", H, 90, 210, 2),))
R2 = Ranking("q2", ("c0", "c3", "c4", "c1", "c2"))


def res(q, r):
    return evaluate_question(chunks(), q, r, ks=KS)


# ── qrel 변환 ────────────────────────────────────────────────
def test_q1_qrels_identical_for_both_criteria():
    assert build_qrels(chunks(), Q1, "any") == {"c1": 2}
    assert build_qrels(chunks(), Q1, "strict") == {"c1": 2}


def test_q2_any_has_three_relevant_chunks():
    assert build_qrels(chunks(), Q2, "any") == {"c0": 2, "c1": 2, "c2": 2}


def test_q2_strict_has_only_the_covering_chunk():
    # c0·c2 는 10/120 = 0.083 < 0.5 → 탈락
    assert build_qrels(chunks(), Q2, "strict") == {"c1": 2}


def test_half_open_interval_excludes_boundary():
    """c0=[0,100) 은 evidence [100,200) 과 겹치지 않는다."""
    assert "c0" not in build_qrels(chunks(), Q1, "any")


# ── q1 기대값 ────────────────────────────────────────────────
@pytest.mark.parametrize("crit", ["any", "strict"])
def test_q1_ranked_metrics(crit):
    r = res(Q1, R1).ranked[crit]
    assert r["hit"][1] == 0.0
    assert r["hit"][3] == 1.0
    assert r["hit"][5] == 1.0
    assert r["mrr"][0] == pytest.approx(0.5)
    assert r["precision"][1] == pytest.approx(0.0)
    assert r["precision"][3] == pytest.approx(1 / 3)
    assert r["precision"][5] == pytest.approx(0.2)
    assert r["ndcg"][1] == pytest.approx(0.0)
    assert r["ndcg"][3] == pytest.approx(0.63093, abs=1e-5)
    assert r["ndcg"][5] == pytest.approx(0.63093, abs=1e-5)


def test_q1_coverage():
    c = res(Q1, R1).coverage
    assert c[1] == pytest.approx(0.0)
    assert c[3] == pytest.approx(1.0)
    assert c[5] == pytest.approx(1.0)


# ── q2 기대값 (기준별로 갈린다) ───────────────────────────────
def test_q2_any():
    r = res(Q2, R2).ranked["any"]
    assert r["hit"][1] == 1.0
    assert r["hit"][3] == 1.0
    assert r["mrr"][0] == pytest.approx(1.0)
    assert r["precision"][1] == pytest.approx(1.0)
    assert r["precision"][3] == pytest.approx(1 / 3)
    assert r["precision"][5] == pytest.approx(0.6)
    assert r["ndcg"][1] == pytest.approx(1.0)
    assert r["ndcg"][3] == pytest.approx(0.46928, abs=1e-5)
    assert r["ndcg"][5] == pytest.approx(0.85293, abs=1e-5)


def test_q2_strict():
    r = res(Q2, R2).ranked["strict"]
    assert r["hit"][1] == 0.0
    assert r["hit"][3] == 0.0
    assert r["hit"][5] == 1.0
    assert r["mrr"][0] == pytest.approx(0.25)
    assert r["precision"][3] == pytest.approx(0.0)
    assert r["precision"][5] == pytest.approx(0.2)
    assert r["ndcg"][3] == pytest.approx(0.0)
    assert r["ndcg"][5] == pytest.approx(0.43068, abs=1e-5)


def test_q2_coverage_is_criterion_independent():
    c = res(Q2, R2).coverage
    assert c[1] == pytest.approx(10 / 120)
    assert c[3] == pytest.approx(10 / 120)
    assert c[5] == pytest.approx(1.0)


def test_ndcg_never_exceeds_one():
    """chunk qrel 변환 전에는 q2 any nDCG@5 가 1.8 을 넘었다."""
    for q, r in [(Q1, R1), (Q2, R2)]:
        for crit in ("any", "strict"):
            for k in KS:
                v = res(q, r).ranked[crit]["ndcg"][k]
                if v is not None:
                    assert 0.0 <= v <= 1.0


# ── macro 집계 ───────────────────────────────────────────────
def test_macro_means_and_denominator():
    a = aggregate([res(Q1, R1), res(Q2, R2)], KS)
    assert a.answerable_count == 2
    assert a.strict_reachable_count == 2
    assert a.strict_reachability_rate == pytest.approx(1.0)
    assert a.ranked["any"]["hit"][3].value == pytest.approx(1.0)
    assert a.ranked["any"]["hit"][3].n == 2
    assert a.ranked["strict"]["hit"][3].value == pytest.approx(0.5)
    assert a.ranked["any"]["mrr"][0].value == pytest.approx(0.75)
    assert a.ranked["strict"]["mrr"][0].value == pytest.approx(0.375)
    assert a.ranked["any"]["ndcg"][3].value == pytest.approx(0.55010, abs=1e-5)
    assert a.ranked["strict"]["ndcg"][3].value == pytest.approx(0.31546, abs=1e-5)
    assert a.coverage[3].value == pytest.approx((1.0 + 10 / 120) / 2)
    assert a.coverage[3].n == 2


def test_report_always_shows_n_and_excluded():
    txt = format_report(aggregate([res(Q1, R1), res(Q2, R2)], KS))
    for line in txt.split("\n"):
        if "0." in line and ("@" in line or "MRR" in line):
            assert "n=" in line and "제외" in line, line


# ── 경계: strict 도달 불가 ────────────────────────────────────
def long_evidence_question():
    """evidence 1200자 — chunk 500자로는 어떤 단일 chunk 도 50% 를 못 덮는다."""
    return Question("q_long", "single", (Evidence("doc-002", "sha-doc002", 0, 1200, 2),))


def long_chunks():
    return [Chunk(f"L{i}", "doc-002", "sha-doc002", i * 500, (i + 1) * 500) for i in range(4)]


def test_strict_unreachable_is_task_level_none():
    r = evaluate_question(long_chunks(), long_evidence_question(),
                          Ranking("q_long", ("L0", "L1", "L2")), ks=KS)
    assert r.strict_reachable is False
    assert r.strict_qrel_size == 0
    assert r.any_qrel_size == 3
    for m in ("hit", "precision", "ndcg"):
        assert all(v is None for v in r.ranked["strict"][m].values())
    assert r.ranked["strict"]["mrr"][0] is None
    # any 는 정상 계산되고 Coverage 도 살아 있다
    assert r.ranked["any"]["hit"][1] == 1.0
    assert r.coverage[1] == pytest.approx(500 / 1200)
    assert r.coverage[3] == pytest.approx(1.0)   # top-3 = L0,L1,L2 로 evidence 전체를 덮는다


def test_unreachable_excluded_from_strict_macro_with_counts():
    rs = [res(Q1, R1), evaluate_question(
        long_chunks(), long_evidence_question(), Ranking("q_long", ("L0", "L1")), ks=KS)]
    a = aggregate(rs, KS)
    assert a.answerable_count == 2
    assert a.strict_reachable_count == 1
    assert a.strict_reachability_rate == pytest.approx(0.5)
    assert a.ranked["strict"]["hit"][3].n == 1          # 분모가 1로 줄었다
    assert a.ranked["strict"]["hit"][3].excluded == 1   # 제외 1건이 표시된다
    assert a.coverage[3].n == 2                         # Coverage 는 2문항 전부 포함
    assert "제외 1" in format_report(a)


# ── 경계: 자료 오류는 중단 ───────────────────────────────────
def test_any_qrel_zero_raises_instead_of_none():
    q = Question("q_bad", "single", (Evidence("doc-999", H, 0, 50, 2),))
    with pytest.raises(EvalDataError, match="any 기준 qrel 이 0개"):
        evaluate_question(chunks(), q, Ranking("q_bad", ("c0",)), ks=KS)


def test_hash_mismatch_raises():
    q = Question("q_h", "single", (Evidence("doc-001", "다른해시", 100, 200, 2),))
    with pytest.raises(EvalDataError, match="extracted_text_sha256"):
        evaluate_question(chunks(), q, Ranking("q_h", ("c1",)), ks=KS)


def test_unknown_chunk_id_raises():
    with pytest.raises(EvalDataError, match="없는 chunk_id"):
        evaluate_question(chunks(), Q1, Ranking("q1", ("c1", "없는청크")), ks=KS)


def test_unanswerable_rejected_from_ranking_task():
    q = Question("q3", "unanswerable", ())
    with pytest.raises(EvalDataError, match="threshold sweep"):
        evaluate_question(chunks(), q, Ranking("q3", ("c2", "c0", "c1")), ks=KS)


def test_unanswerable_with_evidence_rejected():
    with pytest.raises(EvalDataError, match="답변불가 문항에 evidence"):
        Question("x", "unanswerable", (Evidence("doc-001", H, 0, 10, 2),))


# ── 경계: 반환 부족 ──────────────────────────────────────────
def test_precision_denominator_is_k_even_when_fewer_returned():
    r = evaluate_question(chunks(), Q1, Ranking("q1", ("c1",)), ks=KS)
    assert r.returned_count[5] == 1
    assert r.ranked["any"]["precision"][1] == pytest.approx(1.0)
    assert r.ranked["any"]["precision"][5] == pytest.approx(1 / 5)  # k 로 나눈다


def test_empty_ranking_scores_zero_not_error():
    r = evaluate_question(chunks(), Q1, Ranking("q1", ()), ks=KS)
    assert r.returned_count[3] == 0
    assert r.ranked["any"]["hit"][3] == 0.0
    assert r.ranked["any"]["mrr"][0] == 0.0
    assert r.coverage[3] == pytest.approx(0.0)


# ── 경계: 여러 evidence span ─────────────────────────────────
def test_multiple_spans_use_union_length():
    q = Question("q_multi", "single", (
        Evidence("doc-001", H, 100, 200, 2),
        Evidence("doc-001", H, 150, 250, 1),   # 겹친다 → 합집합 150자
    ))
    r = evaluate_question(chunks(), q, Ranking("q_multi", ("c1",)), ks=KS)
    assert r.evidence_total_length == 150
    assert r.evidence_span_count == 2
    assert r.coverage[1] == pytest.approx(100 / 150)


def test_chunk_grade_is_max_of_passing_evidence():
    q = Question("q_grade", "single", (
        Evidence("doc-001", H, 100, 200, 1),
        Evidence("doc-001", H, 120, 180, 2),
    ))
    assert build_qrels(chunks(), q, "any")["c1"] == 2


# ── 입력 검증 ────────────────────────────────────────────────
def test_duplicate_chunk_id_rejected():
    dup = chunks() + [Chunk("c1", "doc-001", H, 900, 1000)]
    with pytest.raises(EvalDataError, match="chunk_id 가 중복"):
        evaluate_question(dup, Q1, R1, ks=KS)


def test_duplicate_chunk_id_rejected_in_build_qrels():
    dup = chunks() + [Chunk("c0", "doc-001", H, 900, 1000)]
    with pytest.raises(EvalDataError, match="chunk_id 가 중복"):
        build_qrels(dup, Q1, "any")


def test_duplicate_ranking_entry_rejected_at_construction():
    with pytest.raises(EvalDataError, match="중복 chunk_id"):
        Ranking("q1", ("c1", "c3", "c1"))


def test_duplicate_ranking_never_reaches_ndcg():
    """중복 순위는 DCG 를 부풀린다 — 계산되기 전에 막혀야 한다."""
    try:
        r = Ranking("q1", ("c1", "c1"))
    except EvalDataError:
        return  # 생성 단계에서 막혔다 (기대 동작)
    pytest.fail(f"중복 ranking 이 생성됐다: {r}")


def test_qid_mismatch_rejected():
    with pytest.raises(EvalDataError, match="qid 가 다르다"):
        evaluate_question(chunks(), Q1, Ranking("다른질문", ("c1",)), ks=KS)


def test_negative_char_start_rejected_chunk():
    with pytest.raises(EvalDataError, match="chunk char_start 가 음수"):
        Chunk("cx", "doc-001", H, -1, 100)


def test_negative_char_start_rejected_evidence():
    with pytest.raises(EvalDataError, match="evidence char_start 가 음수"):
        Evidence("doc-001", H, -5, 100, 2)


@pytest.mark.parametrize("grade", [0, 3, -1, 10])
def test_relevance_grade_must_be_1_or_2(grade):
    with pytest.raises(EvalDataError, match="relevance_grade"):
        Evidence("doc-001", H, 100, 200, grade)


@pytest.mark.parametrize("grade", [1, 2])
def test_relevance_grade_allowed(grade):
    assert Evidence("doc-001", H, 100, 200, grade).relevance_grade == grade


@pytest.mark.parametrize("ks", [(), (0, 3), (-1,), (3, 3), (1, 2, 2)])
def test_invalid_ks_rejected(ks):
    with pytest.raises(EvalDataError):
        evaluate_question(chunks(), Q1, R1, ks=ks)


def test_bool_is_not_a_valid_k():
    with pytest.raises(EvalDataError, match="양의 정수"):
        evaluate_question(chunks(), Q1, R1, ks=(True, 3))


def test_aggregate_rejects_duplicate_qid():
    r = res(Q1, R1)
    with pytest.raises(EvalDataError, match="같은 qid"):
        aggregate([r, r], KS)


def test_aggregate_validates_ks():
    with pytest.raises(EvalDataError):
        aggregate([res(Q1, R1)], (3, 3))


# ── q_long 두 경우 구분 ──────────────────────────────────────
def test_q_long_returns_three_chunks():
    r = evaluate_question(long_chunks(), long_evidence_question(),
                          Ranking("q_long", ("L0", "L1", "L2")), ks=KS)
    assert r.returned_count[3] == 3
    assert r.coverage[3] == pytest.approx(1.0)
    assert r.strict_reachable is False


def test_q_long_returns_two_chunks():
    r = evaluate_question(long_chunks(), long_evidence_question(),
                          Ranking("q_long", ("L0", "L1")), ks=KS)
    assert r.returned_count[3] == 2
    assert r.coverage[3] == pytest.approx(1000 / 1200)
    assert r.strict_reachable is False
