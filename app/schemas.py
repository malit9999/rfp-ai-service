"""API 입출력 스키마. 요청·응답의 계약을 여기서만 정한다."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

ChunkKind = Literal["text", "table", "unknown"]


class HealthComponent(BaseModel):
    """구성 요소 하나의 상태. 아직 구현되지 않은 것도 숨기지 않고 그대로 보고한다."""

    name: str
    status: Literal["ready", "not_implemented", "disabled"]
    detail: str = ""


class HealthResponse(BaseModel):
    status: Literal["ok", "degraded"]
    service: str
    components: list[HealthComponent]


class RetrieveRequest(BaseModel):
    query: str = Field(min_length=1, max_length=2000)
    top_k: int | None = Field(default=None, ge=1, le=100)


class RetrievedChunk(BaseModel):
    chunk_id: str
    document: str
    kind: ChunkKind = "unknown"
    score: float
    text: str


class RetrieveResponse(BaseModel):
    query: str
    retriever: str
    top_k: int
    chunks: list[RetrievedChunk]


class AskRequest(BaseModel):
    query: str = Field(min_length=1, max_length=2000)
    top_k: int | None = Field(default=None, ge=1, le=100)


class AskResponse(BaseModel):
    """답변 생성이 붙기 전 단계의 응답.

    `answer`가 None이면 생성기가 연결되지 않은 것이고, 근거만 돌려준다.
    근거 없이 답변만 돌려주는 경로는 두지 않는다.
    """

    query: str
    answer: str | None
    answer_status: Literal["generated", "evidence_only", "no_evidence"]
    evidence: list[RetrievedChunk]
    notes: list[str] = Field(default_factory=list)


class ErrorResponse(BaseModel):
    """오류는 고정 문구만 돌려준다 — 예외 원문·내부 경로·설정값을 싣지 않는다."""

    detail: str
