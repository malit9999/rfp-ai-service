# rfp-service

> **2026-09-05에 새로 작성한 개인 확장 API 프로토타입입니다.**
> 부트캠프 팀 프로젝트(RFP-AI)에서 확인한 구조를 개인 작업으로 다시 세우는 첫 단계이며,
> **팀 저장소 코드를 옮겨 오지 않았습니다** — 이 저장소의 코드는 빈 저장소에서 새로 썼습니다.
> 운영용 서비스가 아니라 계약(스키마·상태 보고)을 먼저 고정하려는 골격입니다.

공공입찰 제안요청서(RFP) 질의응답을 서비스로 만들기 위한 최소 골격입니다.

## 구현 상태

| 구성 | 상태 |
|---|---|
| Keyword retrieval | **구현됨** (유일하게 동작하는 검색기) |
| Dense retrieval | **미구현** — 이름만 있고 요청하면 503 |
| Hybrid retrieval | **미구현** — 이름만 있고 요청하면 503 |
| Reranker | **미구현** — 재정렬 단계 없음 |
| LLM 답변 생성기 | **미구현** — `answer`는 항상 `null`, `/health`도 항상 `not_implemented` |
| HWP · PDF 표 추출 | **미구현** — `.txt` / `.md`만 읽음 |

Keyword 검색기는 BM25가 아니라 **토큰 겹침 + 문서 빈도 역가중**입니다.
파이프라인이 실제로 통하는지 확인하려는 것이지 검색 성능을 주장하는 코드가 아닙니다.

## 설계 정책 — 없는 것을 있는 것처럼 보이지 않게

1. **생성기가 없으면 `answer`는 `null`** — 근거 없이 문장을 만드는 경로 자체를 두지 않았습니다.
   근거를 찾은 경우 `answer_status: "evidence_only"`, 못 찾은 경우 `"no_evidence"`로 구분합니다.
2. **미구현 구성이 하나라도 있으면 `/health`는 `ok`가 아니라 `degraded`** 입니다.
   지금 실제로 나오는 값은 `ready`와 `not_implemented` 둘뿐입니다
   (`disabled`는 "구현은 됐지만 꺼 둔 상태"를 위해 스키마에만 남겨 둔 값입니다).
   **환경 변수가 채워져 있다고 해서 ready가 되지 않습니다** — `OPENAI_API_KEY`와
   `RFP_ANSWER_MODEL`을 둘 다 넣어도 생성기는 `not_implemented`입니다. 설정이 있다는 것은
   코드가 있다는 뜻이 아니고, 값만 보고 ready로 보고하면 `/ask`의 실제 동작과 어긋납니다.
   서비스는 이 두 값을 **읽지도 않습니다.**
3. **지원하지 않는 retriever를 요청하면 503** — 조용히 keyword로 폴백하지 않습니다.
   화면에는 결과가 뜨는데 실제로는 다른 검색기가 도는 상태를 만들지 않으려는 것입니다.
4. **오류 응답은 고정 문구만** — 예외 원문·내부 경로·설정값을 싣지 않습니다.
5. **API 키와 모델 설정을 읽지도, 담지도 않습니다** — 생성기를 구현하지 않았기 때문입니다.
   설정 객체에는 관련 필드 자체가 없습니다. 생성기를 실제로 연결할 때 구현과 함께 설정을 추가합니다.

## 실행

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env          # 키 없이도 그대로 뜬다
uvicorn app.main:app --reload --port 8000
```

문서를 넣으려면 `.env`의 `RFP_CORPUS_DIR`에 `.txt` / `.md`가 든 디렉터리를 지정합니다.
비워 두면 빈 색인으로 뜹니다.

## API

### `GET /health`

```bash
curl -s localhost:8000/health
```

```json
{
  "status": "degraded",
  "service": "rfp-service",
  "components": [
    { "name": "retriever:keyword", "status": "ready", "detail": "indexed_chunks=2" },
    { "name": "reranker", "status": "not_implemented", "detail": "검색 후보 재정렬 단계가 아직 없습니다." },
    { "name": "generation", "status": "not_implemented", "detail": "답변 생성기가 아직 구현되지 않아 근거만 돌려줍니다." }
  ]
}
```

### `POST /retrieve`

```bash
curl -s -X POST localhost:8000/retrieve \
  -H 'content-type: application/json' \
  -d '{"query": "예산 총액", "top_k": 2}'
```

```json
{
  "query": "예산 총액",
  "retriever": "keyword",
  "top_k": 2,
  "chunks": [
    {
      "chunk_id": "budget#0",
      "document": "budget.txt",
      "kind": "text",
      "score": 0.086643,
      "text": "본 사업의 예산 총액은 3억원이며, 부가세를 포함한 금액이다."
    }
  ]
}
```

`RFP_RETRIEVER=dense`(또는 `hybrid`)로 띄운 뒤 같은 요청을 보내면 **503**입니다.

```json
{ "detail": "요청한 검색기는 아직 구현되지 않았습니다." }
```

### `POST /ask`

근거를 찾은 경우 — `answer`는 `null`이고 근거만 돌려줍니다.

```bash
curl -s -X POST localhost:8000/ask \
  -H 'content-type: application/json' \
  -d '{"query": "평가 배점"}'
```

```json
{
  "query": "평가 배점",
  "answer": null,
  "answer_status": "evidence_only",
  "evidence": [
    {
      "chunk_id": "evaluation#0",
      "document": "evaluation.md",
      "kind": "text",
      "score": 0.099021,
      "text": "평가 배점은 기술 80점, 가격 20점으로 한다."
    }
  ],
  "notes": ["답변 생성기가 아직 구현되지 않아 근거만 돌려줍니다."]
}
```

근거를 못 찾은 경우 — 빈 결과를 오류로 만들지 않습니다.

```json
{
  "query": "항공권 예약",
  "answer": null,
  "answer_status": "no_evidence",
  "evidence": [],
  "notes": ["질문에 해당하는 근거를 색인에서 찾지 못했습니다."]
}
```

## 테스트

```bash
pip install -r requirements.txt
pytest -q     # 27 passed
```

외부 API·네트워크·모델 다운로드를 쓰지 않습니다. 키가 없어도 전부 돕니다.
CI(GitHub Actions)도 같은 명령을 비밀값 없이 실행합니다.

## 다루지 않는 것

- 인증·rate limit이 없습니다. 기본 바인딩은 로컬입니다.
- 원문 문서와 색인은 저장소에 두지 않습니다(`.gitignore`의 `data/` · `index/`).
