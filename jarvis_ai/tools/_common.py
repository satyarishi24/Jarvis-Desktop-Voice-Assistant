"""Small helpers shared by the tool modules."""

from __future__ import annotations

from pathlib import Path

from ..permissions import Risk
from ..registry import ToolContext, ToolError

MAX_OUTPUT = 20_000


def truncate(text: str, limit: int = MAX_OUTPUT) -> str:
    """Keep tool output from swallowing the context window."""
    if len(text) <= limit:
        return text
    dropped = len(text) - limit
    return f"{text[:limit]}\n... [truncated {dropped:,} more characters]"


def human_size(num_bytes: float) -> str:
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if abs(num_bytes) < 1024 or unit == "TB":
            return f"{num_bytes:.0f} {unit}" if unit == "B" else f"{num_bytes:.1f} {unit}"
        num_bytes /= 1024
    return f"{num_bytes:.1f} TB"


def resolve(ctx: ToolContext, raw: str) -> Path:
    return ctx.settings.resolve(raw)


def require_writable(ctx: ToolContext, path: Path) -> Path:
    """Refuse, without prompting, any write outside the configured roots."""
    if not ctx.settings.is_writable(path):
        roots = ", ".join(str(r) for r in ctx.settings.writable_roots)
        raise ToolError(
            f"Refusing to modify {path}: it is outside the writable roots ({roots}). "
            f"Ask the user to restart Jarvis with --writable-root if this is intended."
        )
    return path


def guard_sensitive_read(ctx: ToolContext, path: Path) -> None:
    """Escalate to a confirmation prompt when a read touches likely secrets."""
    if ctx.settings.is_sensitive(path):
        ctx.approver.check(
            "read_file",
            f"read {path}, which looks like it contains credentials or private history",
            Risk.SYSTEM,
        )
