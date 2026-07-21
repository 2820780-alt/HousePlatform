from __future__ import annotations

import argparse
import gzip
import json
from pathlib import Path
import tarfile
from typing import BinaryIO, Iterable


SENSITIVE_VARIABLES = frozenset(
    {
        "ADMIN_PASSWORD",
        "DATABASE_URL",
        "DATABASE_URL_SYNC",
        "JWT_SECRET_KEY",
    }
)
SECRET_FILE_MARKERS = (b".env.docker",)


def parse_env_file(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        name, value = line.split("=", 1)
        values[name.strip()] = value.strip()
    return values


def known_secret_values(path: Path) -> tuple[bytes, ...]:
    env = parse_env_file(path)
    values = {
        value.encode("utf-8")
        for name, value in env.items()
        if name in SENSITIVE_VARIABLES and value
    }
    redis_url = env.get("REDIS_URL", "")
    if "@" in redis_url:
        values.add(redis_url.encode("utf-8"))
    return tuple(sorted(values))


def _scan_stream(stream: BinaryIO, needles: Iterable[bytes]) -> set[bytes]:
    patterns = tuple(item for item in needles if item)
    if not patterns:
        return set()
    overlap = max(len(item) for item in patterns) - 1
    found: set[bytes] = set()
    tail = b""
    while True:
        chunk = stream.read(1024 * 1024)
        if not chunk:
            break
        block = tail + chunk
        found.update(item for item in patterns if item in block)
        tail = block[-overlap:] if overlap else b""
    return found


def scan_image_archive(image_tar: Path, env_file: Path) -> dict[str, int | bool]:
    secret_values = known_secret_values(env_file)
    name_hits: set[bytes] = set()
    secret_hits: set[bytes] = set()
    with tarfile.open(image_tar, mode="r:*") as archive:
        for member in archive.getmembers():
            name_bytes = member.name.encode("utf-8", errors="ignore")
            name_hits.update(marker for marker in SECRET_FILE_MARKERS if marker in name_bytes)
            if not member.isfile():
                continue
            source = archive.extractfile(member)
            if source is None:
                continue
            prefix = source.read(2)
            source.seek(0)
            hits = _scan_stream(source, (*SECRET_FILE_MARKERS, *secret_values))
            name_hits.update(marker for marker in SECRET_FILE_MARKERS if marker in hits)
            secret_hits.update(value for value in secret_values if value in hits)
            if prefix == b"\x1f\x8b":
                source.seek(0)
                with gzip.GzipFile(fileobj=source) as decompressed:
                    hits = _scan_stream(decompressed, (*SECRET_FILE_MARKERS, *secret_values))
                name_hits.update(marker for marker in SECRET_FILE_MARKERS if marker in hits)
                secret_hits.update(value for value in secret_values if value in hits)
    return {
        "known_secret_count": len(secret_values),
        "secret_file_marker_hits": len(name_hits),
        "known_secret_value_hits": len(secret_hits),
        "passed": not name_hits and not secret_hits,
    }


def scan_text_file(path: Path, env_file: Path) -> dict[str, int | bool]:
    values = known_secret_values(env_file)
    with path.open("rb") as stream:
        hits = _scan_stream(stream, values)
    return {"known_secret_value_hits": len(hits), "passed": not hits}


def main() -> int:
    parser = argparse.ArgumentParser(description="Scan a saved Docker image without printing secrets.")
    parser.add_argument("--image-tar", type=Path, required=True)
    parser.add_argument("--env-file", type=Path, required=True)
    parser.add_argument("--history-file", type=Path)
    parser.add_argument("--build-log", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    report: dict[str, object] = {
        "image": scan_image_archive(args.image_tar, args.env_file),
    }
    if args.history_file:
        report["history"] = scan_text_file(args.history_file, args.env_file)
    if args.build_log:
        report["build_log"] = scan_text_file(args.build_log, args.env_file)
    report["passed"] = all(
        isinstance(value, dict) and bool(value.get("passed"))
        for key, value in report.items()
        if key != "passed"
    )
    rendered = json.dumps(report, ensure_ascii=True, indent=2, sort_keys=True)
    if args.output:
        args.output.write_text(rendered + "\n", encoding="utf-8")
    print(rendered)
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
