"""Runtime settings and the filesystem guard rails."""

from __future__ import annotations

import fnmatch
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import List

from .permissions import Policy

MODEL = "claude-opus-5"

#: Paths that hold credentials often enough that reading one deserves a prompt,
#: even though reads are otherwise unrestricted.
SENSITIVE_PATTERNS: List[str] = [
    "*/.ssh/*",
    "*/.aws/credentials",
    "*/.aws/config",
    "*/.config/gcloud/*",
    "*/.gnupg/*",
    "*/.docker/config.json",
    "*/.kube/config",
    "*.pem",
    "*.key",
    "*.env",
    "*/.env.*",
    "*/id_rsa*",
    "*/id_ed25519*",
    "*_history",
    "*/Login Data",
    "*/cookies.sqlite",
]


def _env_flag(name: str, default: bool = False) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


@dataclass
class Settings:
    """Everything that changes how a Jarvis session behaves."""

    model: str = MODEL
    effort: str = "high"
    max_tokens: int = 16000

    policy: Policy = Policy.ASK
    dry_run: bool = False

    voice_input: bool = False
    voice_output: bool = True

    #: Directories the assistant may write to. Anything outside is refused
    #: before the tool runs, no prompt offered.
    writable_roots: List[Path] = field(default_factory=lambda: [Path.home()])

    #: Where notes, screenshots and the assistant's own state live.
    data_dir: Path = field(default_factory=lambda: Path.home() / ".jarvis")

    #: Ceiling on tool-call rounds in a single turn, so a confused model
    #: cannot loop forever on your machine.
    max_iterations: int = 40

    #: Seconds before a shell command is killed.
    command_timeout: int = 120

    @classmethod
    def from_env(cls) -> "Settings":
        """Build settings from JARVIS_* environment variables."""
        settings = cls()
        settings.model = os.environ.get("JARVIS_MODEL", settings.model)
        settings.effort = os.environ.get("JARVIS_EFFORT", settings.effort)
        settings.voice_input = _env_flag("JARVIS_VOICE_INPUT", settings.voice_input)
        settings.voice_output = _env_flag("JARVIS_VOICE_OUTPUT", settings.voice_output)

        roots = os.environ.get("JARVIS_WRITABLE_ROOTS")
        if roots:
            settings.writable_roots = [
                Path(part).expanduser() for part in roots.split(os.pathsep) if part
            ]

        data_dir = os.environ.get("JARVIS_DATA_DIR")
        if data_dir:
            settings.data_dir = Path(data_dir).expanduser()

        timeout = os.environ.get("JARVIS_COMMAND_TIMEOUT")
        if timeout and timeout.isdigit():
            settings.command_timeout = int(timeout)

        return settings

    # -- path helpers ----------------------------------------------------

    def resolve(self, raw: str) -> Path:
        """Expand ``~`` and environment variables, then make the path absolute."""
        expanded = os.path.expandvars(str(raw))
        path = Path(expanded).expanduser()
        if not path.is_absolute():
            path = Path.cwd() / path
        # resolve() without strict=True so we can validate paths that don't
        # exist yet (the target of a write, for instance).
        return Path(os.path.normpath(str(path)))

    def is_writable(self, path: Path) -> bool:
        """True if ``path`` sits inside one of the configured writable roots."""
        for root in self.writable_roots:
            root = Path(os.path.normpath(str(root.expanduser())))
            try:
                path.relative_to(root)
                return True
            except ValueError:
                continue
        return False

    def is_sensitive(self, path: Path) -> bool:
        """True if the path looks like it holds credentials or private history."""
        text = str(path)
        return any(fnmatch.fnmatch(text, pattern) for pattern in SENSITIVE_PATTERNS)

    def ensure_data_dir(self) -> Path:
        self.data_dir.mkdir(parents=True, exist_ok=True)
        return self.data_dir
