"""Risk levels and the approval gate that stands between Claude and your device."""

from __future__ import annotations

import enum
from dataclasses import dataclass
from typing import Callable, Optional


class Risk(str, enum.Enum):
    """How much damage a tool could do if Claude gets it wrong."""

    READ = "read"
    """Observes the machine without changing it: listing files, system stats."""

    WRITE = "write"
    """Changes something recoverable: writing a file, launching an app, typing."""

    SYSTEM = "system"
    """Arbitrary or irreversible: shell commands, deleting, killing, powering off."""


class Policy(str, enum.Enum):
    """How much the assistant is allowed to do without stopping to ask."""

    ASK = "ask"
    """Confirm anything that changes the machine. The default."""

    AUTO_EDIT = "auto-edit"
    """Confirm only SYSTEM actions; file writes and app launches run freely."""

    YOLO = "yolo"
    """Never ask. Only sensible in a throwaway VM."""

    READ_ONLY = "read-only"
    """Refuse every action that changes anything, without asking."""


_AUTO_APPROVED = {
    Policy.ASK: {Risk.READ},
    Policy.AUTO_EDIT: {Risk.READ, Risk.WRITE},
    Policy.YOLO: {Risk.READ, Risk.WRITE, Risk.SYSTEM},
    Policy.READ_ONLY: {Risk.READ},
}


class Denied(Exception):
    """Raised when an action is refused — by policy or by the user at the prompt."""


@dataclass
class Approver:
    """Decides whether a single tool call is allowed to run.

    ``confirm`` is injected so the console, a test, or a future GUI can each
    supply their own way of asking. It receives a human-readable description of
    the action and returns True to allow it.
    """

    policy: Policy = Policy.ASK
    dry_run: bool = False
    confirm: Optional[Callable[[str, str, Risk], bool]] = None

    def will_prompt(self, risk: Risk) -> bool:
        """True if an action at this risk level would stop and ask the user."""
        return (
            risk not in _AUTO_APPROVED[self.policy]
            and self.policy is not Policy.READ_ONLY
            and self.confirm is not None
        )

    def check(self, tool_name: str, description: str, risk: Risk) -> None:
        """Allow the call, or raise :class:`Denied` explaining why not."""
        if risk in _AUTO_APPROVED[self.policy]:
            return

        if self.policy is Policy.READ_ONLY:
            raise Denied(
                f"'{tool_name}' would change the system, and Jarvis is running "
                f"read-only. Restart without --read-only to allow it."
            )

        if self.confirm is None:
            raise Denied(
                f"'{tool_name}' needs confirmation but no way to ask the user "
                f"is available. Re-run with a policy that permits it."
            )

        if not self.confirm(tool_name, description, risk):
            raise Denied(f"You declined the '{tool_name}' action.")
