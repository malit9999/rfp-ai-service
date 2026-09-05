# 검색 실험 계획 (Retrieval Experiment Plan)

> 작성 2026-09-05 · 이 문서는 **실행 전에 규칙을 먼저 고정하려고** 쓴다.
> 수치를 낸 뒤에 기준을 바꾸면 비교가 성립하지 않는다.

## 0. 범위

**이번 실험이 다루는 것** — 검색 품질뿐이다.
질문을 넣으면 어떤 근거 chunk가 나오는지, 검색기를 바꾸면 그것이 어떻게 달라지는지.

**다루지 않는 것**

- LLM 답변 생성 — 생성기가 없으므로 faithfulness·answer_relevancy 같은 생성 지표는 계산할 수 없다.
  RAGAS는 이 실험의 지표가 아니다.
- 화면(UI) — 결과는 JSON과 표로 남긴다.

이 실험은 **재현(reproduction)이 아니라 신규 측정**이다. 다른 문서·다른 질문·다른 지표이므로,
부트캠프 팀 프로젝트에서 나온 수치와 같은 표에 두거나 "재현했다"고 쓰지 않는다.

## 1. 용어를 먼저 정확히

현재 이 저장소의 `KeywordRetriever`는 **BM25가 아니다.** 토큰 겹침(term frequency)에
문서 빈도 역가중을 곱한 방식이고, BM25의 길이 정규화(b)나 포화 항(k1)이 없다.

문서·코드·결과표 어디서도 이것을 BM25라고 부르지 않는다.
`Hybrid`라는 말도 **실제 BM25를 구현한 뒤부터** 쓴다.

## 2. 실험 대상 — 검색기 사다리

한 번에 하나씩 올린다. 각 단계는 직전 단계와만 비교한다.

| # | 이름 | 내용 | 비교 대상 |
|---|---|---|---|
| R0 | `keyword` | 현재 구현 (토큰 겹침 + 문서 빈도 역가중) | 기준선 |
| R1 | `bm25` | 실제 BM25 (k1·b 명시) | R0 |
| R2 | `dense` | 로컬 임베딩 모델 | R0 · R1 |
| R3 | `hybrid-rrf` | R1 + R2 를 RRF로 결합 | R1 · R2 |
| R4 | `hybrid-rrf-rerank` | R3 + Reranker (실패 시 R3 결과 유지) | R3 |

**제약**: Dense와 Reranker의 모델은 로컬에서 도는 것을 쓴다. API 키를 요구하는 임베딩은
쓰지 않는다 — 키·네트워크 없이 `pytest -q`가 도는 성질을 유지하기 위해서다.
모델 다운로드가 필요한 테스트는 opt-in 마커로 분리하고 기본 CI에서는 제외한다.

## 3. 코퍼스와 청킹 — 고정이 아니라 버전 관리

청킹 규칙을 "절대 바꾸지 않는다"고 두면 **청크 크기·오버랩 자체를 실험할 수 없다.**
바꿔도 되게 하되, 바꾸면 새 실험 ID가 되도록 한다.

```yaml
corpus_version: rfp-demo-v1        # 문서 집합이 바뀌면 올린다
chunker_version: fixed-500-overlap-80-v1
config_hash: <청킹 파라미터의 sha256 앞 8자리>
experiment_id: <corpus_version>__<chunker_version>__<retriever>
```

- 문서 원본은 저장소에 두지 않는다. `inputs.sha256`으로 대조만 가능하게 한다.
- 청킹 파라미터를 바꾸면 `chunker_version`을 올리고 **기존 결과는 폐기하지 않는다.**
  다른 `experiment_id`의 결과로 남긴다.
- `experiment_id`가 다른 결과끼리는 같은 표에 넣지 않는다.

각 chunk는 자기가 어느 원문 범위를 담고 있는지 함께 저장한다.

```json
{
  "chunk_id": "rfp-demo-v1/doc-001#0007",
  "document_id": "doc-001",
  "page": 12,
  "section": "3.2 예산",
  "char_start": 8412,
  "char_end": 8907
}
```

## 4. 평가셋 — 정답은 chunk가 아니라 원문 위치에 건다

**chunk ID로 정답을 라벨링하지 않는다.** 청킹이 바뀌면 라벨이 통째로 무효가 되기 때문이다.
정답은 원문 좌표에 건다.

```yaml
- qid: q014
  question: "이 사업의 총 예산은 얼마인가?"
  type: single          # single | followup | filter | unanswerable
  evidence:
    - document_id: doc-001
      page: 12
      section: "3.2 예산"
      evidence_start: 8450
      evidence_end: 8612
      relevance_grade: 2   # 2=직접 답, 1=부분 근거, 0=무관
```

**판정 방식** — 검색된 chunk의 `[char_start, char_end)` 와 정답 `[evidence_start, evidence_end)` 가
겹치면 적중으로 본다. 겹침 기준은 다음 두 개를 모두 기록한다.

- `overlap_any` — 1자라도 겹치면 적중
- `overlap_ratio ≥ 0.5` — 정답 구간의 절반 이상을 덮으면 적중

느슨한 기준과 엄격한 기준을 함께 보고해야, 청크가 커서 우연히 걸린 경우를 구분할 수 있다.

**규모**: 질문 20~30개. 유형 배분을 먼저 정하고 라벨링한다.
이 규모에서 평균값의 차이는 통계적 의미가 거의 없다 — 결과에 반드시 함께 적는다.

## 5. 지표

### 5.1 답변 가능한 질문 (single · followup · filter)

`k ∈ {1, 3, 5, 10}` 에서 전부 계산한다.

- `Recall@k` — 정답 evidence 중 덮인 비율
- `Precision@k` — 반환한 chunk 중 정답과 겹치는 비율
- `Hit@k` — 상위 k에 정답이 하나라도 있으면 1
- `MRR` — 첫 정답의 역순위
- `nDCG@k` — `relevance_grade`를 이득으로 사용

### 5.2 답변불가 질문 — **평균에 섞지 않는다**

정답이 빈 집합이라 Recall이 정의되지 않는다. 별도 지표로 본다.

- `false_evidence_rate` — 근거가 없는데 근거를 반환한 비율
- `abstention_accuracy@θ` — 점수 임계값 θ를 적용했을 때 올바르게 기권한 비율
- `empty_return_rate` — 빈 결과를 정확히 돌려준 비율

임계값 θ는 답변 가능한 질문의 점수 분포에서 정하고, 그 근거를 함께 기록한다.

### 5.3 보고 규칙

- **평균만 보고하지 않는다.** 문항별 결과를 `metrics.json`에 전부 남긴다.
- **실패한 질문을 공개한다.** 어떤 유형에서 왜 틀렸는지 함께 적는다.
- 검색기가 기준선을 이기지 못해도 그대로 싣는다. 음성 결과도 결과다.

## 6. 산출물 위치

```
evidence/<experiment_id>/
├── README.md         무엇을·왜·무엇을 확인했나
├── config.yaml       corpus/chunker/retriever 설정 + config_hash
├── environment.txt   python·라이브러리 버전, OS
├── inputs.sha256     원본 문서 해시
├── metrics.json      집계 + 문항별 결과
├── failures.md       틀린 질문과 원인
└── commands.txt      실행한 명령 그대로
```

## 7. 순서

1. 공개 가능한 RFP 문서 1~3건 선정 · `inputs.sha256` 기록
2. 청킹 구현 (`char_start`/`char_end` 포함) · `chunker_version` 부여
3. 질문 20~30개 작성 · 원문 좌표로 정답 라벨링
4. 평가 스크립트 구현 (§5 지표 전부)
5. **R0 `keyword` 기준선 측정**
6. R1 `bm25` 구현·측정
7. R2 `dense` 구현·측정
8. R3 `hybrid-rrf` 구현·측정
9. R4 Reranker 구현·측정 (실패 시 R3 결과 유지)
10. 문항별 실패 분석 · 답변불가 질문 별도 평가

## 8. 중단·보류 기준

- 라벨링에서 정답 구간이 모호한 질문은 평가셋에서 **뺀다.** 억지로 라벨링하지 않는다.
- 로컬 Dense 모델이 CI 제약(키·네트워크 없음)을 깨면 opt-in으로 분리하고, 그 사실을 결과에 적는다.
- 어느 단계에서 멈추더라도 그 시점까지의 결과는 `evidence/`에 남기고 공개한다.
