"""HWPX(OWPML) 안전 읽기와 텍스트 추출.

**신뢰할 수 없는 파일을 다룬다는 전제로 쓴다.**

- 전체 압축을 임시 디렉터리에 풀지 않는다. 필요한 항목만 스트림으로 읽는다
- 첨부 바이너리·OLE·미리보기·스크립트는 열지 않는다 (`BinData/`, `Preview/` 등)
- XML은 DTD·엔티티 선언이 있으면 파싱 자체를 거부한다 (XXE·엔티티 확장 차단)
- 경로 순회(`..`), 절대 경로, 암호화, 압축 폭탄을 미리 검사한다

구조가 예상과 다르면 조용히 빈 결과를 내지 않고 예외를 던진다.
"""

from __future__ import annotations

import re
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from xml.etree import ElementTree as ET

from extraction.version import EXTRACTOR_VERSION

# ── 안전 한계 ────────────────────────────────────────────────
MAX_ENTRIES = 5_000
MAX_ENTRY_UNCOMPRESSED = 50 * 1024 * 1024      # 항목 하나
MAX_TOTAL_UNCOMPRESSED = 200 * 1024 * 1024     # 전체 합
MAX_COMPRESSION_RATIO = 200                    # 1KB 초과 항목에만 적용
_RATIO_MIN_SIZE = 1024

# 읽어도 되는 항목만 화이트리스트로 둔다
_ALLOWED_EXACT = {"mimetype", "version.xml", "META-INF/container.xml"}
_SECTION_RE = re.compile(r"^Contents/section(\d+)\.xml$")

_EXPECTED_MIMETYPE = "application/hwp+zip"
_XML_DECL_GUARD = re.compile(rb"<!DOCTYPE|<!ENTITY", re.IGNORECASE)


class HwpxSafetyError(Exception):
    """보안 검사에 걸렸다. 파싱을 진행하지 않는다."""


class HwpxStructureError(Exception):
    """HWPX 구조가 예상과 다르다. 조용히 넘어가지 않는다."""


@dataclass
class ArchiveReport:
    """구조·보안 검사 결과. 문서 내용은 담지 않는다."""

    entry_count: int
    total_compressed: int
    total_uncompressed: int
    max_ratio: float
    mimetype: str | None
    section_names: list[str]
    encrypted_entries: list[str] = field(default_factory=list)
    suspicious_paths: list[str] = field(default_factory=list)

    @property
    def is_hwpx(self) -> bool:
        return self.mimetype == _EXPECTED_MIMETYPE and bool(self.section_names)


def _is_suspicious(name: str) -> bool:
    """경로 순회·절대 경로·드라이브 경로를 걸러낸다."""
    if not name or name.startswith(("/", "\\")):
        return True
    if "\\" in name:                      # 윈도 구분자는 정상 HWPX에 없다
        return True
    if re.match(r"^[A-Za-z]:", name):     # C:\ 형태
        return True
    return any(part == ".." for part in name.split("/"))


def inspect_archive(path: str | Path) -> ArchiveReport:
    """압축을 풀지 않고 항목 정보만 읽어 검사한다."""
    path = Path(path)
    if not zipfile.is_zipfile(path):
        raise HwpxStructureError("ZIP 컨테이너가 아니다")

    with zipfile.ZipFile(path) as zf:
        infos = zf.infolist()
        if len(infos) > MAX_ENTRIES:
            raise HwpxSafetyError(f"항목 수 초과: {len(infos)} > {MAX_ENTRIES}")

        total_c = total_u = 0
        max_ratio = 0.0
        encrypted: list[str] = []
        suspicious: list[str] = []

        for zi in infos:
            if _is_suspicious(zi.filename):
                suspicious.append(zi.filename)
            if zi.flag_bits & 0x1:
                encrypted.append(zi.filename)
            if zi.file_size > MAX_ENTRY_UNCOMPRESSED:
                raise HwpxSafetyError(f"항목 크기 초과: {zi.filename}")
            total_c += zi.compress_size
            total_u += zi.file_size
            if zi.file_size > _RATIO_MIN_SIZE and zi.compress_size > 0:
                max_ratio = max(max_ratio, zi.file_size / zi.compress_size)

        if total_u > MAX_TOTAL_UNCOMPRESSED:
            raise HwpxSafetyError(f"전체 해제 크기 초과: {total_u}")
        if max_ratio > MAX_COMPRESSION_RATIO:
            raise HwpxSafetyError(f"압축률 초과(폭탄 의심): {max_ratio:.1f}")
        if suspicious:
            raise HwpxSafetyError(f"의심스러운 경로: {suspicious[:3]}")
        if encrypted:
            raise HwpxSafetyError(f"암호화된 항목: {encrypted[:3]}")

        mimetype = None
        if "mimetype" in zf.namelist():
            mimetype = zf.read("mimetype").decode("ascii", "replace").strip()

        sections = sorted(
            (n for n in zf.namelist() if _SECTION_RE.match(n)),
            key=lambda n: int(_SECTION_RE.match(n).group(1)),  # 사전순이 아니라 번호순
        )

    return ArchiveReport(
        entry_count=len(infos),
        total_compressed=total_c,
        total_uncompressed=total_u,
        max_ratio=round(max_ratio, 2),
        mimetype=mimetype,
        section_names=sections,
    )


def _parse_xml(raw: bytes, name: str) -> ET.Element:
    """DTD·엔티티 선언이 있으면 파싱하지 않는다."""
    if _XML_DECL_GUARD.search(raw):
        raise HwpxSafetyError(f"DTD/엔티티 선언이 있는 XML은 처리하지 않는다: {name}")
    try:
        return ET.fromstring(raw)  # ElementTree는 외부 엔티티를 해석하지 않는다
    except ET.ParseError as exc:
        raise HwpxStructureError(f"XML 파싱 실패: {name}: {exc}") from None


def _local(tag: str) -> str:
    """`{ns}local` → `local`. 네임스페이스 URI 판본 차이에 흔들리지 않게 한다."""
    return tag.rsplit("}", 1)[-1] if "}" in tag else tag


# ── 본문 조립 ────────────────────────────────────────────────
# 통째로 건너뛰는 서브트리 — 머리말·꼬리말·쪽번호·각주 표식·이미지·바이너리
_SKIP = {
    "header", "footer", "pageNum", "autoNum", "newNum",
    "picture", "pic", "container", "ole", "equation", "chart",
    "footNote", "endNote",  # 각주 본문은 _footnote_text로 따로 모은다
}


def _runs_text(node: ET.Element) -> str:
    """문단 안의 텍스트 조각을 이어 붙인다. 표는 여기서 다루지 않는다."""
    out: list[str] = []
    for child in node:
        name = _local(child.tag)
        if name in _SKIP or name == "tbl":
            continue
        if name == "t":
            out.append("".join(child.itertext()))
        elif name in ("lineBreak", "tab"):
            out.append(" ")
        else:
            out.append(_runs_text(child))
        if child.tail:
            out.append(child.tail)
    return "".join(out)


def _footnote_text(para: ET.Element) -> list[str]:
    """문단에 달린 각주 본문. 계약 §2.4에 따라 문단 뒤에 붙인다."""
    notes: list[str] = []
    for node in para.iter():
        if _local(node.tag) in ("footNote", "endNote"):
            txt = " ".join(
                "".join(t.itertext()) for t in node.iter() if _local(t.tag) == "t"
            ).strip()
            if txt:
                notes.append(txt)
    return notes


def _cell_text(cell: ET.Element) -> str:
    """셀 안의 문단들을 한 줄로 만든다 (행이 쪼개지지 않게)."""
    parts = [
        _runs_text(p).strip()
        for p in cell.iter()
        if _local(p.tag) == "p"
    ]
    return " ".join(x for x in parts if x)


def _table_lines(tbl: ET.Element) -> list[str]:
    """표를 행 단위로 펼친다. 계약 §2.2.

    - 셀 구분자는 ` | `
    - 병합 셀은 값을 반복하지 않고 첫 위치에만 두고 나머지는 빈 문자열
    - 마크다운 표로 바꾸지 않는다
    """
    lines: list[str] = []
    for tr in (n for n in tbl.iter() if _local(n.tag) == "tr"):
        cells: list[str] = []
        for tc in (n for n in tr if _local(n.tag) == "tc"):
            span_cols = 1
            for sp in tc.iter():
                if _local(sp.tag) == "cellSpan":
                    span_cols = max(1, int(sp.attrib.get("colSpan", "1") or 1))
                    break
            cells.append(_cell_text(tc))
            # 병합으로 덮인 자리는 빈 칸으로 둔다 — 값을 반복하지 않는다
            cells.extend("" for _ in range(span_cols - 1))
        if cells:
            lines.append(" | ".join(cells))
    return lines


def _section_blocks(root: ET.Element) -> list[str]:
    """섹션 하나를 블록(문단/표) 목록으로 만든다.

    ElementTree에는 부모 포인터가 없어 부모 맵을 **섹션마다 한 번만** 만든다.
    문단마다 다시 훑으면 문서 크기에 제곱으로 느려진다.
    """
    parents: dict[ET.Element, ET.Element] = {}
    for parent in root.iter():
        for child in parent:
            parents[child] = parent

    def skip_paragraph(node: ET.Element) -> bool:
        """표 셀 안이거나, 건너뛰는 컨테이너(머리말·꼬리말·각주 등) 안이면 제외한다.

        - 표 안의 문단은 표 처리에서 다룬다
        - 머리말·꼬리말·쪽번호는 본문이 아니다
        - 각주 본문은 _footnote_text 가 해당 문단 뒤에 붙인다
        """
        cur = parents.get(node)
        while cur is not None:
            name = _local(cur.tag)
            if name == "tc" or name in _SKIP:
                return True
            cur = parents.get(cur)
        return False

    blocks: list[str] = []
    for para in (n for n in root.iter() if _local(n.tag) == "p"):
        if skip_paragraph(para):
            continue

        text = _runs_text(para).strip()
        if text:
            blocks.append(text)
        blocks.extend(_footnote_text(para))
        for tbl in (t for t in para.iter() if _local(t.tag) == "tbl"):
            rows = _table_lines(tbl)
            if rows:
                # 표 앞뒤 빈 줄은 블록 사이 "\n\n" 결합에서 생긴다
                blocks.append("\n".join(rows))
    return blocks


def extract_text(path: str | Path) -> tuple[str, ArchiveReport]:
    """HWPX에서 본문 텍스트를 뽑는다. 정규화는 하지 않는다(호출자가 norm-v1을 적용한다)."""
    report = inspect_archive(path)
    if report.mimetype is not None and report.mimetype != _EXPECTED_MIMETYPE:
        raise HwpxStructureError(f"mimetype이 다르다: {report.mimetype!r}")
    if not report.section_names:
        raise HwpxStructureError("Contents/section*.xml 을 찾지 못했다")

    blocks: list[str] = []
    with zipfile.ZipFile(path) as zf:
        for name in report.section_names:  # 번호순으로 결정적으로 처리
            root = _parse_xml(zf.read(name), name)
            blocks.extend(_section_blocks(root))

    if not blocks:
        raise HwpxStructureError("본문 블록이 하나도 나오지 않았다")

    return "\n\n".join(blocks), report


def extractor_id() -> str:
    return EXTRACTOR_VERSION
