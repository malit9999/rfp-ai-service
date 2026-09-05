"""rfp-service — RFP 질의응답 서비스의 최소 골격.

지금 있는 것: 상태 보고 · 검색 · 근거 반환.
아직 없는 것: Dense/Hybrid 검색, Reranker, 답변 생성, HWP/PDF 표 추출.
없는 것은 숨기지 않고 /health 와 응답의 answer_status 로 드러낸다.
"""

from __future__ import annotations

from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse

from app.config import Settings, load_settings
from app.retrieval import Chunk, build_retriever
from app.retrieval.registry import NOT_IMPLEMENTED_DETAIL
from app.schemas import (
    AskRequest,
    AskResponse,
    HealthComponent,
    HealthResponse,
    RetrievedChunk,
    RetrieveRequest,
    RetrieveResponse,
)

GENERATION_NOT_WIRED = "답변 생성기가 아직 구현되지 않아 근거만 돌려줍니다."
NO_EVIDENCE = "질문에 해당하는 근거를 색인에서 찾지 못했습니다."


def create_app(settings: Settings | None = None, chunks: list[Chunk] | None = None) -> FastAPI:
    settings = settings or load_settings()
    retriever = build_retriever(settings, chunks)

    app = FastAPI(title="rfp-service", version="0.1.0")
    app.state.settings = settings
    app.state.retriever = retriever

    def resolve_top_k(requested: int | None) -> int:
        return min(requested or settings.top_k, settings.max_top_k)

    def search(query: str, top_k: int) -> list[RetrievedChunk]:
        try:
            hits = retriever.search(query, top_k)
        except NotImplementedError:
            raise HTTPException(status_code=503, detail=NOT_IMPLEMENTED_DETAIL) from None
        return [
            RetrievedChunk(
                chunk_id=hit.chunk.chunk_id,
                document=hit.chunk.document,
                kind=hit.chunk.kind if hit.chunk.kind in {"text", "table"} else "unknown",
                score=hit.score,
                text=hit.chunk.text,
            )
            for hit in hits
        ]

    @app.get("/health", response_model=HealthResponse)
    def health() -> HealthResponse:
        components = [
            HealthComponent(
                name=f"retriever:{settings.retriever}",
                status="ready" if settings.retriever_implemented else "not_implemented",
                detail=f"indexed_chunks={retriever.size()}",
            ),
            HealthComponent(
                name="reranker",
                status="not_implemented",
                detail="검색 후보 재정렬 단계가 아직 없습니다.",
            ),
            HealthComponent(
                # 생성기는 코드가 없다. 환경 변수가 채워져 있어도 ready가 되지 않는다 —
                # /ask가 항상 answer: null 인 현재 동작과 상태 보고가 어긋나면 안 된다.
                name="generation",
                status="not_implemented",
                detail=GENERATION_NOT_WIRED,
            ),
        ]
        degraded = any(c.status != "ready" for c in components)
        return HealthResponse(
            status="degraded" if degraded else "ok",
            service=settings.service_name,
            components=components,
        )

    @app.post("/retrieve", response_model=RetrieveResponse)
    def retrieve(req: RetrieveRequest) -> RetrieveResponse:
        top_k = resolve_top_k(req.top_k)
        return RetrieveResponse(
            query=req.query,
            retriever=retriever.name,
            top_k=top_k,
            chunks=search(req.query, top_k),
        )

    @app.post("/ask", response_model=AskResponse)
    def ask(req: AskRequest) -> AskResponse:
        top_k = resolve_top_k(req.top_k)
        evidence = search(req.query, top_k)

        if not evidence:
            return AskResponse(
                query=req.query,
                answer=None,
                answer_status="no_evidence",
                evidence=[],
                notes=[NO_EVIDENCE],
            )

        # 생성기가 붙기 전까지 answer는 항상 None이다. 근거 없이 문장을 만들지 않는다.
        return AskResponse(
            query=req.query,
            answer=None,
            answer_status="evidence_only",
            evidence=evidence,
            notes=[GENERATION_NOT_WIRED],
        )

    @app.exception_handler(HTTPException)
    def fixed_error(_request, exc: HTTPException) -> JSONResponse:
        # 예외 원문·스택·경로를 응답에 싣지 않는다.
        return JSONResponse(status_code=exc.status_code, content={"detail": str(exc.detail)})

    return app


app = create_app()
