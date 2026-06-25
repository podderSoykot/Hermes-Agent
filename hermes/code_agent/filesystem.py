"""Safe project-scoped file reads and writes."""

from __future__ import annotations

from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent


def resolve_project_path(relative_path: str) -> Path:
    target = (PROJECT_ROOT / relative_path).resolve()
    if PROJECT_ROOT not in target.parents and target != PROJECT_ROOT:
        raise ValueError("Path must stay inside the Hermes-Agent project.")
    return target


def read_project_file(relative_path: str) -> str:
    path = resolve_project_path(relative_path)
    if not path.is_file():
        raise ValueError(f"File not found: {relative_path}")
    return path.read_text(encoding="utf-8")


def write_code_file(relative_path: str, code: str) -> str:
    target = resolve_project_path(relative_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(code, encoding="utf-8")
    return str(target)
