"""norm-v1 — docs/EXTRACTION_CONTRACT.md §2 의 8단계를 그대로 구현한다.

단계 순서가 계약의 일부다. 순서를 바꾸면 결과 문자열이 달라지고 좌표가 밀린다.
"""

from __future__ import annotations

import re
import unicodedata

# 4단계에서 일반 공백으로 바꾸는 문자
_SPACE_LIKE = {
    " ",  # NBSP
    "　",  # 전각 공백
    " ", " ", " ", " ", " ", " ", " ",
}
# 4단계에서 삭제하는 폭 없는 문자
_ZERO_WIDTH = {"​", "‌", "‍", "﻿"}

# 3단계: \t \n 을 제외한 C0 제어문자
_CONTROL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
# 5단계: 줄바꿈을 제외한 연속 공백
_INLINE_WS = re.compile(r"[ \t]+")
# 7단계: 3줄 이상의 연속 개행
_BLANK_RUN = re.compile(r"\n{3,}")


def normalize(text: str) -> str:
    """추출 직후 텍스트에 norm-v1을 적용한다."""
    # 1. 유니코드 정규화 — 자모 분리형(NFD)으로 저장된 파일을 먼저 통일한다
    text = unicodedata.normalize("NFC", text)

    # 2. 줄바꿈 통일
    text = text.replace("\r\n", "\n").replace("\r", "\n")

    # 3. 제어문자 제거 (\t, \n 은 남긴다)
    text = _CONTROL.sub("", text)

    # 4. 공백 문자 통일 — 폭 없는 문자는 삭제, 나머지 공백류는 일반 공백으로
    text = "".join(
        "" if ch in _ZERO_WIDTH else (" " if ch in _SPACE_LIKE else ch) for ch in text
    )

    # 5. 행 내부 공백 축약 (줄바꿈은 건드리지 않는다)
    text = _INLINE_WS.sub(" ", text)

    # 6. 행 끝 공백 제거
    text = "\n".join(line.rstrip() for line in text.split("\n"))

    # 7. 빈 줄 축약 — 연속된 빈 줄을 최대 1개로
    text = _BLANK_RUN.sub("\n\n", text)

    # 8. 문서 끝 개행 정리
    return text.strip("\n") + "\n"
