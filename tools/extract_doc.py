#!/usr/bin/env python3
"""HWPX 한 건을 검사·추출·정규화하고 해시를 찍는다.

    python tools/extract_doc.py data/raw/doc-001.hwpx

**문서 내용은 출력하지 않는다.** 해시와 구조·검사 결과만 찍는다.
결과 텍스트는 data/extracted/<stem>.txt 에 저장하고, 그 디렉터리는 .gitignore 대상이다.
"""

from __future__ import annotations

import argparse
import hashlib
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from extraction import (  # noqa: E402
    EXTRACTOR_VERSION,
    NORMALIZATION_VERSION,
    HwpxSafetyError,
    HwpxStructureError,
    extract_text,
    normalize,
)

OUT_DIR = Path("data/extracted")


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def main() -> int:
    ap = argparse.ArgumentParser(description="HWPX 검사·추출 (내용은 출력하지 않는다)")
    ap.add_argument("path", type=Path)
    ap.add_argument("--out-dir", type=Path, default=OUT_DIR)
    args = ap.parse_args()

    src: Path = args.path
    if not src.is_file():
        print(f"파일이 없다: {src}", file=sys.stderr)
        return 2

    print(f"파일          : {src.name}")
    print(f"크기          : {src.stat().st_size:,} bytes")
    print(f"확인일        : {date.today().isoformat()}")
    print(f"document_sha256: {sha256_file(src)}")

    try:
        raw_text, report = extract_text(src)
    except HwpxSafetyError as exc:
        print(f"\n[보안 검사 실패] {exc}", file=sys.stderr)
        return 3
    except HwpxStructureError as exc:
        print(f"\n[구조 오류] {exc}", file=sys.stderr)
        return 4

    print(f"\nZIP 항목 수    : {report.entry_count}")
    print(f"압축 합계      : {report.total_compressed:,} bytes")
    print(f"해제 합계      : {report.total_uncompressed:,} bytes")
    print(f"최대 압축률    : {report.max_ratio}")
    print(f"mimetype       : {report.mimetype}")
    print(f"섹션           : {len(report.section_names)}개 {report.section_names}")

    text = normalize(raw_text)
    data = text.encode("utf-8")
    args.out_dir.mkdir(parents=True, exist_ok=True)
    out = args.out_dir / f"{src.stem}.txt"
    out.write_bytes(data)

    print(f"\nextractor_version    : {EXTRACTOR_VERSION}")
    print(f"normalization_version: {NORMALIZATION_VERSION}")
    print(f"extracted_text_sha256: {hashlib.sha256(data).hexdigest()}")
    print(f"문자 수              : {len(text):,}")
    print(f"줄 수                : {text.count(chr(10)):,}")
    print(f"저장                 : {out}  (.gitignore 대상)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
