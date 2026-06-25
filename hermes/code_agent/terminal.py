"""Run shell commands inside the project workspace."""

from __future__ import annotations

import subprocess
from dataclasses import dataclass

from hermes.code_agent.filesystem import PROJECT_ROOT

_BLOCKED_FRAGMENTS = (
    "rm -rf /",
    "rm -rf ~",
    "mkfs",
    ":(){ :|:& };:",
    "dd if=",
    "> /dev/",
)


@dataclass
class CommandResult:
    returncode: int
    stdout: str
    stderr: str

    @property
    def output(self) -> str:
        return "\n".join(part for part in (self.stdout.strip(), self.stderr.strip()) if part)


def run_command(command: str, *, timeout: int = 60) -> CommandResult:
    lowered = command.lower()
    for fragment in _BLOCKED_FRAGMENTS:
        if fragment in lowered:
            raise ValueError(f"Blocked unsafe command fragment: {fragment}")

    try:
        completed = subprocess.run(
            command,
            shell=True,
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired as exc:
        return CommandResult(
            returncode=124,
            stdout=(exc.stdout or "").strip(),
            stderr=f"Command timed out after {timeout}s",
        )

    return CommandResult(
        returncode=completed.returncode,
        stdout=(completed.stdout or "").strip(),
        stderr=(completed.stderr or "").strip(),
    )
