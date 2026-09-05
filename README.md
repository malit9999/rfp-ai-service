# rfp-service

RFP 질의응답을 **서비스로 만들기 위한 최소 골격**입니다.
부트캠프 팀 프로젝트(RFP-AI)에서 확인한 구조를 개인 작업으로 다시 세우는 첫 단계입니다.
**팀 저장소 코드를 옮겨 오지 않았습니다** — 이 저장소의 코드는 2026-09-05에 새로 작성했습니다.

## 지금 되는 것

| 엔드포인트 | 하는 일 | 과금 |
|---|---|---|
| `GET /health` | 구성 요소별 상태를 그대로 보고 (`ready` / `not_implemented` / `disabled`) | 없음 |
| `POST /retrieve` | 질문 → 근거 chunk 목록 (문서명·chunk id·점수 포함) | 없음 |
| `POST /ask` | 질문 → 근거 + 답변 상태 | 없음 |

## 아직 없는 것

의도적으로 비워 둔 자리입니다. 숨기지 않고 `/health`와 응답에 드러납니다.

- **Dense · Hybrid 검색** — 이름만 있고 구현이 없습니다. `RFP_RETRIEVER=dense`로 두면
  조용히 keyword로 떨어지지 않고 요청이 **503**으로 끊깁니다.
- **Reranker** — 재정렬 단계가 없습니다. `/health`에 `not_implemented`로 나옵니다.
- **답변 생성** — 생성기가 붙기 전까지 `/ask`의 `answer`는 항상 `null`이고
  `answer_status`가 `evidence_only`입니다. 근거 없이 문장을 만드는 경로는 두지 않았습니다.
- **HWP · PDF 표 추출** — 지금 로더는 `.txt` / `.md`를 한 파일 = 한 chunk로 읽습니다.

기준 검색기(`keyword`)는 BM25가 아니라 토큰 겹침 + 문서 빈도 역가중입니다.
파이프라인이 통하는지 확인하려는 것이지 검색 성능을 주장하려는 것이 아닙니다.

## 실행

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env          # 키 없이도 그대로 뜬다
uvicorn app.main:app --reload --port 8000
```

문서를 넣으려면 `.env`의 `RFP_CORPUS_DIR`에 `.txt`/`.md`가 든 디렉터리를 지정합니다.
비워 두면 빈 색인으로 뜨고, `/ask`는 `answer_status: "no_evidence"`를 돌려줍니다.

```bash
curl -s localhost:8000/health
curl -s -X POST localhost:8000/retrieve \
  -H 'content-type: application/json' -d '{"query":"예산 총액","top_k":3}'
```

## 테스트

```bash
pip install -r requirements.txt
pytest -q
```

외부 API·네트워크·모델 다운로드를 쓰지 않습니다. 키가 없어도 전부 돕니다.

## 다루지 않는 것

- 인증·rate limit이 없습니다. 기본 바인딩은 로컬입니다.
- 원문 문서와 색인은 저장소에 두지 않습니다(`.gitignore`의 `data/`·`index/`).
- 오류 응답은 고정 문구만 돌려줍니다 — 예외 원문·내부 경로·설정값을 싣지 않습니다.
