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

    @property
    def retriever_implemented(self) -> bool:
        return self.retriever in IMPLEMENTED_RETRIEVERS


def load_settings() -> Settings:
    """환경 변수에서 설정을 읽는다.

    답변 생성 관련 값(API 키·모델명)은 **읽지 않는다.** 생성기가 아직 없어서
    읽어도 쓸 곳이 없고, 값이 있다는 이유로 기능이 있는 것처럼 보고하게 되기 때문이다.
    생성기를 실제로 붙일 때 그 코드와 함께 추가한다.
    """
    max_top_k = _int_env("RFP_MAX_TOP_K", 20)
    top_k = min(_int_env("RFP_TOP_K", 5), max_top_k)
    return Settings(
        service_name=os.getenv("RFP_SERVICE_NAME") or "rfp-service",
        retriever=(os.getenv("RFP_RETRIEVER") or "keyword").strip().lower(),
        top_k=top_k,
        max_top_k=max_top_k,
        corpus_dir=os.getenv("RFP_CORPUS_DIR", ""),
    )
