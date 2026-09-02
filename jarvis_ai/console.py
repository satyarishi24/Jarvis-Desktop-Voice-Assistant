"""Terminal output and the confirmation prompt."""

from __future__ import annotations

import os
import sys

from .permissions import Risk

_COLOR = sys.stdout.isatty() and os.environ.get("NO_COLOR") is None


def _paint(text: str, code: str) -> str:
    return f"\033[{code}m{text}\033[0m" if _COLOR else text


def dim(text: str) -> str:
    return _paint(text, "2")


def bold(text: str) -> str:
    return _paint(text, "1")


def cyan(text: str) -> str:
    return _paint(text, "36")


def yellow(text: str) -> str:
    return _paint(text, "33")


def red(text: str) -> str:
    return _paint(text, "31")


def green(text: str) -> str:
    return _paint(text, "32")


RISK_LABEL = {
    Risk.READ: green("read"),
    Risk.WRITE: yellow("modifies your machine"),
    Risk.SYSTEM: red("system-level"),
}


def banner(model: str, policy: str, tool_count: int, dry_run: bool) -> None:
    print(bold("\n  J A R V I S"), dim(f"· {tool_count} device tools · {model}"))
    mode = f"approval: {policy}"
    if dry_run:
        mode += " · dry run (nothing will actually happen)"
    print(dim(f"  {mode}"))
    print(dim("  Type what you want done, or 'exit' to quit.\n"))


def assistant(text: str) -> None:
    print(f"\n{cyan('jarvis')} {text}\n")


def tool_start(name: str, description: str) -> None:
    print(dim(f"  → {name}: {description}"))


def tool_result(summary: str) -> None:
    print(dim(f"    {summary}"))


def error(text: str) -> None:
    print(red(f"  ! {text}"))


def info(text: str) -> None:
    print(dim(f"  {text}"))


def confirm(tool_name: str, description: str, risk: Risk) -> bool:
    """Ask the user to approve one action. Anything but y/yes is a no."""
    print()
    print(f"  {yellow('Jarvis wants to')} {bold(description)}")
    print(dim(f"  tool: {tool_name} · {RISK_LABEL[risk]}"))
    try:
        answer = input(f"  {bold('Allow? [y/N] ')}").strip().lower()
    except (EOFError, KeyboardInterrupt):
        print()
        return False
    return answer in {"y", "yes"}
