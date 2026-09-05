"""환경 변수 하나만 읽는 설정. 값이 없으면 안전한 기본값으로 떨어진다."""

from __future__ import annotations

import os
from dataclasses import dataclass

# 구현된 검색기 이름. 여기 없는 이름은 "슬롯만 있는 상태"로 취급한다.
IMPLEMENTED_RETRIEVERS = frozenset({"keyword"})
KNOWN_RETRIEVERS = frozenset({"keyword", "dense", "hybrid"})


def _int_env(name: str, default: int) -> int:
    raw = os.getenv(name, "")
    try:
        value = int(raw)
    except ValueError:
        return default
    return value if value > 0 else default


@dataclass(frozen=True)
class Settings:
    service_name: str = "rfp-service"
    retriever: str = "keyword"
    top_k: int = 5
    max_top_k: int = 20
    corpus_dir: str = ""
    answer_model: str = ""
    has_answer_key: bool = False

    @property
    def retriever_implemented(self) -> bool:
        return self.retriever in IMPLEMENTED_RETRIEVERS

    @property
    def generation_enabled(self) -> bool:
        """답변 생성은 키와 모델이 둘 다 있을 때만 켠다. 지금은 어느 쪽도 붙어 있지 않다."""
        return bool(self.has_answer_key and self.answer_model)


def load_settings() -> Settings:
    max_top_k = _int_env("RFP_MAX_TOP_K", 20)
    top_k = min(_int_env("RFP_TOP_K", 5), max_top_k)
    return Settings(
        service_name=os.getenv("RFP_SERVICE_NAME") or "rfp-service",
        retriever=(os.getenv("RFP_RETRIEVER") or "keyword").strip().lower(),
        top_k=top_k,
        max_top_k=max_top_k,
        corpus_dir=os.getenv("RFP_CORPUS_DIR", ""),
        answer_model=os.getenv("RFP_ANSWER_MODEL", "").strip(),
        # 키 값 자체는 읽어서 어디에도 넘기지 않는다. 있는지 여부만 본다.
        has_answer_key=bool(os.getenv("OPENAI_API_KEY", "").strip()),
    )
