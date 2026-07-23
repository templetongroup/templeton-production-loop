#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import shutil
import zipfile
from pathlib import Path
from typing import TypedDict

ROOT = Path(__file__).resolve().parent.parent
DIST = ROOT / "dist"
STAGE = DIST / "stage"
VERSION = "0.2.0"


class RuntimeConfig(TypedDict):
    skills_source: Path
    skills_destination: str
    readme: Path
    agents: Path


RUNTIMES: dict[str, RuntimeConfig] = {
    "hermes": {
        "skills_source": ROOT / "skills",
        "skills_destination": "skills",
        "readme": ROOT / "exports/hermes/README.md",
        "agents": ROOT / "exports/hermes/AGENTS.example.md",
    },
    "openclaw": {
        "skills_source": ROOT / "skills-openclaw",
        "skills_destination": "skills-openclaw",
        "readme": ROOT / "exports/openclaw/README.md",
        "agents": ROOT / "exports/openclaw/AGENTS.example.md",
    },
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def copy_runtime(runtime: str, config: RuntimeConfig) -> Path:
    bundle_name = f"templeton-coding-loop-{runtime}-v{VERSION}"
    bundle = STAGE / bundle_name
    bundle.mkdir(parents=True, exist_ok=True)

    shutil.copy2(ROOT / "LICENSE", bundle / "LICENSE")
    shutil.copy2(ROOT / "pyproject.toml", bundle / "pyproject.toml")
    shutil.copy2(config["readme"], bundle / "README.md")
    shutil.copy2(config["agents"], bundle / "AGENTS.example.md")
    shutil.copytree(ROOT / "templeton_loop", bundle / "templeton_loop", ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    shutil.copytree(config["skills_source"], bundle / str(config["skills_destination"]))
    (bundle / "scripts").mkdir()
    shutil.copy2(ROOT / "exports/validate_bundle.py", bundle / "scripts/validate_bundle.py")
    (bundle / "VERSION").write_text(VERSION + "\n", encoding="utf-8")
    (bundle / "SOURCE.md").write_text(
        "# Source and attribution\n\n"
        "Templeton Coding Loop is an MIT-licensed adaptation of Alex Finn's Finn-loop: "
        "https://github.com/finna/Finn-loop\n\n"
        "Linear-specific state was replaced with GitHub Issues. This edition targets "
        f"{runtime.title()}. No credentials are included.\n",
        encoding="utf-8",
    )

    records = []
    for path in sorted(p for p in bundle.rglob("*") if p.is_file()):
        relative = path.relative_to(bundle).as_posix()
        records.append({"path": relative, "sha256": sha256(path), "bytes": path.stat().st_size})
    (bundle / "MANIFEST.json").write_text(
        json.dumps({"name": bundle_name, "version": VERSION, "runtime": runtime, "files": records}, indent=2) + "\n",
        encoding="utf-8",
    )
    (bundle / "MANIFEST.sha256").write_text(
        "".join(f"{record['sha256']}  {record['path']}\n" for record in records),
        encoding="utf-8",
    )
    return bundle


def zip_bundle(bundle: Path) -> Path:
    output = DIST / f"{bundle.name}.zip"
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for path in sorted(p for p in bundle.rglob("*") if p.is_file()):
            arcname = (Path(bundle.name) / path.relative_to(bundle)).as_posix()
            info = zipfile.ZipInfo(arcname, date_time=(2026, 7, 22, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = (0o644 & 0xFFFF) << 16
            archive.writestr(info, path.read_bytes(), compress_type=zipfile.ZIP_DEFLATED, compresslevel=9)
    return output


def main() -> int:
    if STAGE.exists():
        shutil.rmtree(STAGE)
    STAGE.mkdir(parents=True)
    outputs = []
    for runtime, config in RUNTIMES.items():
        bundle = copy_runtime(runtime, config)
        archive = zip_bundle(bundle)
        outputs.append(
            {
                "runtime": runtime,
                "directory": str(bundle),
                "archive": str(archive),
                "sha256": sha256(archive),
                "bytes": archive.stat().st_size,
            }
        )
    (DIST / "exports.json").write_text(json.dumps(outputs, indent=2) + "\n", encoding="utf-8")
    (DIST / "SHA256SUMS").write_text(
        "".join(f"{item['sha256']}  {Path(item['archive']).name}\n" for item in outputs),
        encoding="utf-8",
    )
    print(json.dumps(outputs, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
