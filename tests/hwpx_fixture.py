"""테스트용 합성 HWPX 생성기.

**실제 원본 문서는 저장소에 넣지 않는다.** 여기서 만드는 파일은 민감 정보가 없는
최소 구조이고, 테스트 실행 중에만 임시로 만들어진다.
"""

from __future__ import annotations

import zipfile
from pathlib import Path

HP = "http://www.hancom.co.kr/hwpml/2011/paragraph"
HS = "http://www.hancom.co.kr/hwpml/2011/section"

MIMETYPE = "application/hwp+zip"

# 정규화가 실제로 걸리는지 보려고 일부러 섞은 문자들
NBSP = " "
FULLWIDTH_SPACE = "　"
ZERO_WIDTH = "​"
NFD_TEXT = "가"  # 자모 분리형 "가" — NFC로 합쳐져야 한다

_SECTION = f"""<?xml version="1.0" encoding="UTF-8"?>
<hs:sec xmlns:hs="{HS}" xmlns:hp="{HP}">
  <hp:p><hp:run><hp:t>가상 문서{NBSP}본문입니다.{ZERO_WIDTH}</hp:t></hp:run></hp:p>
  <hp:p><hp:run><hp:t>○ 첫 번째 항목</hp:t></hp:run></hp:p>
  <hp:p><hp:run><hp:t>- 두 번째 항목</hp:t></hp:run></hp:p>
  <hp:p><hp:run><hp:t>제출 마감{FULLWIDTH_SPACE}2026/09/23 10:00</hp:t></hp:run></hp:p>
  <hp:p><hp:run><hp:t>자모 시험 {NFD_TEXT}</hp:t></hp:run></hp:p>
  <hp:p>
    <hp:run>
      <hp:ctrl><hp:header><hp:p><hp:run><hp:t>머리말 텍스트</hp:t></hp:run></hp:p></hp:header></hp:ctrl>
      <hp:ctrl><hp:footer><hp:p><hp:run><hp:t>꼬리말 텍스트</hp:t></hp:run></hp:p></hp:footer></hp:ctrl>
      <hp:ctrl><hp:pageNum/></hp:ctrl>
      <hp:t>머리말 다음 문단</hp:t>
      <hp:ctrl><hp:footNote><hp:subList><hp:p><hp:run><hp:t>각주 본문</hp:t></hp:run></hp:p></hp:subList></hp:footNote></hp:ctrl>
    </hp:run>
  </hp:p>
  <hp:p>
    <hp:run>
      <hp:tbl>
        <hp:tr>
          <hp:tc><hp:cellSpan colSpan="1" rowSpan="1"/><hp:subList><hp:p><hp:run><hp:t>구분</hp:t></hp:run></hp:p></hp:subList></hp:tc>
          <hp:tc><hp:cellSpan colSpan="1" rowSpan="1"/><hp:subList><hp:p><hp:run><hp:t>금액</hp:t></hp:run></hp:p></hp:subList></hp:tc>
          <hp:tc><hp:cellSpan colSpan="1" rowSpan="1"/><hp:subList><hp:p><hp:run><hp:t>비고</hp:t></hp:run></hp:p></hp:subList></hp:tc>
        </hp:tr>
        <hp:tr>
          <hp:tc><hp:cellSpan colSpan="1" rowSpan="1"/><hp:subList><hp:p><hp:run><hp:t>총액</hp:t></hp:run></hp:p></hp:subList></hp:tc>
          <hp:tc><hp:cellSpan colSpan="1" rowSpan="1"/><hp:subList><hp:p><hp:run><hp:t>1,234,567원</hp:t></hp:run></hp:p></hp:subList></hp:tc>
          <hp:tc><hp:cellSpan colSpan="1" rowSpan="1"/><hp:subList><hp:p><hp:run><hp:t>부가세 포함</hp:t></hp:run></hp:p></hp:subList></hp:tc>
        </hp:tr>
        <hp:tr>
          <hp:tc><hp:cellSpan colSpan="2" rowSpan="1"/><hp:subList><hp:p><hp:run><hp:t>합계</hp:t></hp:run></hp:p></hp:subList></hp:tc>
          <hp:tc><hp:cellSpan colSpan="1" rowSpan="1"/><hp:subList><hp:p><hp:run><hp:t>확인</hp:t></hp:run></hp:p></hp:subList></hp:tc>
        </hp:tr>
      </hp:tbl>
    </hp:run>
  </hp:p>
</hs:sec>
"""

_SECTION1 = f"""<?xml version="1.0" encoding="UTF-8"?>
<hs:sec xmlns:hs="{HS}" xmlns:hp="{HP}">
  <hp:p><hp:run><hp:t>두 번째 섹션 문단</hp:t></hp:run></hp:p>
</hs:sec>
"""


def write_fixture(path: Path, *, sections: int = 2) -> Path:
    """정상 HWPX 하나를 만든다. 항목 순서는 실제 HWPX와 같게 둔다."""
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zf:
        # mimetype은 무압축으로 먼저 넣는 것이 관례다
        zf.writestr(zipfile.ZipInfo("mimetype"), MIMETYPE, zipfile.ZIP_STORED)
        zf.writestr("META-INF/container.xml", '<?xml version="1.0"?><container/>')
        zf.writestr("Contents/header.xml", '<?xml version="1.0"?><head/>')
        # 일부러 10 → 2 → 0 순으로 넣어 사전순 정렬로는 틀리게 만든다
        if sections > 2:
            zf.writestr("Contents/section10.xml", _SECTION1.replace("두 번째", "열한 번째"))
        zf.writestr("Contents/section1.xml", _SECTION1)
        zf.writestr("Contents/section0.xml", _SECTION)
        # 읽으면 안 되는 것들
        zf.writestr("BinData/image1.png", b"\x89PNG\r\n\x1a\n" + b"\x00" * 32)
        zf.writestr("Preview/PrvText.txt", "미리보기 텍스트 — 본문에 들어가면 안 된다")
    return path


def write_traversal_fixture(path: Path) -> Path:
    with zipfile.ZipFile(path, "w") as zf:
        zf.writestr("mimetype", MIMETYPE)
        zf.writestr("Contents/section0.xml", _SECTION)
        zf.writestr("../../etc/passwd", "x")
    return path


def write_bomb_fixture(path: Path) -> Path:
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("mimetype", MIMETYPE)
        zf.writestr("Contents/section0.xml", _SECTION)
        zf.writestr("Contents/blob.bin", "A" * (5 * 1024 * 1024))  # 압축률이 매우 높다
    return path


def write_dtd_fixture(path: Path) -> Path:
    evil = (
        '<?xml version="1.0"?>\n'
        '<!DOCTYPE sec [<!ENTITY lol "lol">]>\n'
        f'<hs:sec xmlns:hs="{HS}" xmlns:hp="{HP}">'
        "<hp:p><hp:run><hp:t>&lol;</hp:t></hp:run></hp:p></hs:sec>"
    )
    with zipfile.ZipFile(path, "w") as zf:
        zf.writestr("mimetype", MIMETYPE)
        zf.writestr("Contents/section0.xml", evil)
    return path


def write_wrong_mimetype_fixture(path: Path) -> Path:
    with zipfile.ZipFile(path, "w") as zf:
        zf.writestr("mimetype", "application/zip")
        zf.writestr("Contents/section0.xml", _SECTION)
    return path
