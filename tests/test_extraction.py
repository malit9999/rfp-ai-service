import hashlib
import zipfile

import pytest

from extraction import (
    EXTRACTOR_VERSION,
    NORMALIZATION_VERSION,
    HwpxSafetyError,
    HwpxStructureError,
    extract_text,
    inspect_archive,
    normalize,
)
from tests.hwpx_fixture import (
    write_bomb_fixture,
    write_dtd_fixture,
    write_fixture,
    write_traversal_fixture,
    write_wrong_mimetype_fixture,
)


@pytest.fixture
def hwpx(tmp_path):
    return write_fixture(tmp_path / "sample.hwpx")


# ── 구조·보안 검사 ────────────────────────────────────────────
def test_inspect_reports_structure(hwpx):
    r = inspect_archive(hwpx)
    assert r.mimetype == "application/hwp+zip"
    assert r.is_hwpx
    assert r.entry_count > 0
    assert r.total_uncompressed > 0


def test_sections_are_ordered_numerically(tmp_path):
    """section10 이 section1·section2 보다 뒤에 와야 한다 — 사전순이면 틀린다."""
    r = inspect_archive(write_fixture(tmp_path / "many.hwpx", sections=3))
    assert r.section_names == [
        "Contents/section0.xml",
        "Contents/section1.xml",
        "Contents/section10.xml",
    ]


def test_path_traversal_is_rejected(tmp_path):
    with pytest.raises(HwpxSafetyError, match="경로"):
        inspect_archive(write_traversal_fixture(tmp_path / "evil.hwpx"))


def test_zip_bomb_ratio_is_rejected(tmp_path):
    with pytest.raises(HwpxSafetyError, match="압축률"):
        inspect_archive(write_bomb_fixture(tmp_path / "bomb.hwpx"))


def test_dtd_and_entity_are_rejected(tmp_path):
    with pytest.raises(HwpxSafetyError, match="DTD"):
        extract_text(write_dtd_fixture(tmp_path / "xxe.hwpx"))


def test_wrong_mimetype_is_rejected(tmp_path):
    with pytest.raises(HwpxStructureError, match="mimetype"):
        extract_text(write_wrong_mimetype_fixture(tmp_path / "bad.hwpx"))


def test_non_zip_is_rejected(tmp_path):
    p = tmp_path / "plain.hwpx"
    p.write_text("이건 ZIP이 아니다", encoding="utf-8")
    with pytest.raises(HwpxStructureError, match="ZIP"):
        inspect_archive(p)


def test_missing_section_is_not_silent(tmp_path):
    p = tmp_path / "nosec.hwpx"
    with zipfile.ZipFile(p, "w") as zf:
        zf.writestr("mimetype", "application/hwp+zip")
        zf.writestr("Contents/header.xml", "<head/>")
    with pytest.raises(HwpxStructureError, match="section"):
        extract_text(p)


# ── 본문 추출 ────────────────────────────────────────────────
def test_paragraphs_and_list_markers_survive(hwpx):
    text, _ = extract_text(hwpx)
    assert "가상 문서 본문입니다." in normalize(text)
    assert "○ 첫 번째 항목" in text
    assert "- 두 번째 항목" in text


def test_header_footer_pagenum_are_dropped(hwpx):
    text, _ = extract_text(hwpx)
    assert "머리말 텍스트" not in text
    assert "꼬리말 텍스트" not in text
    assert "머리말 다음 문단" in text


def test_footnote_follows_its_paragraph(hwpx):
    text, _ = extract_text(hwpx)
    assert text.index("머리말 다음 문단") < text.index("각주 본문")


def test_preview_and_bindata_are_not_read(hwpx):
    text, _ = extract_text(hwpx)
    assert "미리보기" not in text


def test_second_section_comes_after_first(hwpx):
    text, _ = extract_text(hwpx)
    assert text.index("가상 문서") < text.index("두 번째 섹션 문단")


# ── 표 규칙 ──────────────────────────────────────────────────
def test_table_rows_use_pipe_separator(hwpx):
    text, _ = extract_text(hwpx)
    assert "구분 | 금액 | 비고" in text
    assert "총액 | 1,234,567원 | 부가세 포함" in text


def test_merged_cell_is_not_repeated(hwpx):
    """colSpan=2 인 셀의 값을 두 번 쓰지 않는다. 빈 칸으로 자리만 채운다."""
    text, _ = extract_text(hwpx)
    assert "합계 |  | 확인" in text
    assert "합계 | 합계" not in text


def test_amount_keeps_commas_and_unit(hwpx):
    text, _ = extract_text(hwpx)
    assert "1,234,567원" in text


def test_no_markdown_table_markup(hwpx):
    text, _ = extract_text(hwpx)
    assert "|---" not in text and "---|" not in text


def test_no_placeholder_for_images(hwpx):
    text, _ = extract_text(hwpx)
    assert "[이미지]" not in text


# ── 정규화 norm-v1 ────────────────────────────────────────────
def test_normalize_applies_nfc(hwpx):
    text, _ = extract_text(hwpx)
    out = normalize(text)
    assert "자모 시험 가" in out          # NFD "가" 가 합쳐졌다
    assert "ᄀ" not in out            # 분리형 ㄱ 이 남지 않았다


def test_normalize_collapses_inline_whitespace_only():
    out = normalize("가  나\t\t다\n\n\n\n라")
    assert "가 나 다" in out
    assert "\n\n\n" not in out            # 빈 줄은 최대 1개


def test_normalize_removes_zero_width_and_nbsp(hwpx):
    out = normalize(extract_text(hwpx)[0])
    assert "​" not in out and " " not in out and "　" not in out


def test_normalize_ends_with_single_newline():
    assert normalize("본문\n\n\n").endswith("본문\n")


def test_normalize_strips_trailing_spaces():
    assert normalize("본문   \n다음") == "본문\n다음\n"


# ── 결정성 ────────────────────────────────────────────────────
def test_same_file_extracts_byte_identically(hwpx):
    a = normalize(extract_text(hwpx)[0]).encode("utf-8")
    b = normalize(extract_text(hwpx)[0]).encode("utf-8")
    assert hashlib.sha256(a).hexdigest() == hashlib.sha256(b).hexdigest()


def test_versions_are_declared():
    assert EXTRACTOR_VERSION and NORMALIZATION_VERSION
