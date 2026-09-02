"""Notes and long-term memory — the things Jarvis should still know tomorrow."""

from __future__ import annotations

import datetime
import json
from pathlib import Path
from typing import Any, Dict, List

from ..permissions import Risk
from ..registry import ToolContext, ToolError, tool
from ._common import truncate


def memory_path(settings: Any) -> Path:
    return settings.ensure_data_dir() / "memory.json"


def notes_path(settings: Any) -> Path:
    return settings.ensure_data_dir() / "notes.md"


def load_memory(settings: Any) -> List[Dict[str, str]]:
    """Read the remembered facts. Returns an empty list if there are none yet."""
    path = memory_path(settings)
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return []
    return data if isinstance(data, list) else []


def _save_memory(settings: Any, facts: List[Dict[str, str]]) -> None:
    memory_path(settings).write_text(json.dumps(facts, indent=2), encoding="utf-8")


@tool(
    risk=Risk.WRITE,
    description=(
        "Remember a fact about the user or their machine for future sessions — "
        "preferences, project locations, how they like things done. Remembered "
        "facts are loaded into your context at the start of every session."
    ),
    params={"fact": "The thing to remember, written as a short standalone sentence."},
    preview=lambda fact: f"remember: {fact}",
)
def remember(ctx: ToolContext, fact: str) -> str:
    text = fact.strip()
    if not text:
        raise ToolError("Nothing to remember.")

    facts = load_memory(ctx.settings)
    if any(entry["fact"].lower() == text.lower() for entry in facts):
        return "Already remembered that."

    facts.append({"fact": text, "added": datetime.date.today().isoformat()})
    _save_memory(ctx.settings, facts)
    return f"Remembered: {text}"


@tool(
    risk=Risk.READ,
    description="List everything currently remembered about the user.",
    preview=lambda: "review remembered facts",
)
def recall(ctx: ToolContext) -> str:
    facts = load_memory(ctx.settings)
    if not facts:
        return "Nothing has been remembered yet."
    lines = [f"{index}. {entry['fact']}  (since {entry['added']})" for index, entry in enumerate(facts, 1)]
    return "Remembered facts:\n" + "\n".join(lines)


@tool(
    risk=Risk.WRITE,
    description="Forget a remembered fact, identified by its number from recall.",
    params={"number": "The number shown next to the fact by recall."},
    preview=lambda number: f"forget remembered fact #{number}",
)
def forget(ctx: ToolContext, number: int) -> str:
    facts = load_memory(ctx.settings)
    if not 1 <= number <= len(facts):
        raise ToolError(f"There is no fact #{number}. Call recall to see the list.")
    removed = facts.pop(number - 1)
    _save_memory(ctx.settings, facts)
    return f"Forgot: {removed['fact']}"


@tool(
    risk=Risk.WRITE,
    description="Append a timestamped note to the user's notes file.",
    params={"text": "The note to write down."},
    preview=lambda text: f"note down: {text[:80]}",
)
def take_note(ctx: ToolContext, text: str) -> str:
    path = notes_path(ctx.settings)
    stamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    with open(path, "a", encoding="utf-8") as handle:
        handle.write(f"- [{stamp}] {text.strip()}\n")
    return f"Noted. ({path})"


@tool(
    risk=Risk.READ,
    description="Read back the notes the user has taken, newest last.",
    params={"limit": "How many of the most recent notes to show."},
    preview=lambda limit=20: "read back saved notes",
)
def read_notes(ctx: ToolContext, limit: int = 20) -> str:
    path = notes_path(ctx.settings)
    if not path.exists():
        return "No notes yet."
    lines = [line for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    if not lines:
        return "No notes yet."
    return truncate("\n".join(lines[-max(1, limit) :]))
