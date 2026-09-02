"""The agent loop: user request in, device actions out."""

from __future__ import annotations

import platform
import socket
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List

from . import console
from .config import Settings
from .permissions import Approver, Denied
from .registry import Registry, ToolContext, ToolError
from .tools import REGISTRY
from .tools.memory import load_memory

#: Anthropic's hosted search tool. Claude runs it server-side, so unlike every
#: other tool here it never touches the user's machine and needs no approval.
WEB_SEARCH_TOOL = {
    "type": "web_search_20260209",
    "name": "web_search",
    "max_uses": 5,
}

SYSTEM_PROMPT = """You are Jarvis, a voice-driven assistant that operates the \
user's computer for them. You are not a chatbot that describes what the user \
could do — you have tools that actually do it, and you use them.

<machine>
{machine}
</machine>

How you work:
- When a request needs something done on the machine, do it. Chain as many tool \
calls as the job takes, and check your work: after writing a file, read it back \
if the result matters; after launching something, confirm it started.
- Look before you leap on anything ambiguous. If the user says "delete the old \
report", find the candidates first and confirm which one they mean rather than \
guessing.
- You cannot see the screen unless you take a screenshot. When a request depends \
on what is on screen, take one.
- Prefer the specific tool over run_command when both would work: the user sees \
the tool name and description at the approval prompt, and "open_website \
youtube.com" is a much clearer thing to approve than a shell one-liner.
- The user must approve anything that changes their machine. A denial is a \
normal answer, not an error: acknowledge it and offer another route. Never try \
to route around a denial by doing the same thing through a different tool.
- Never run destructive commands the user did not ask for, never use sudo unless \
they explicitly asked, and never send the contents of their files anywhere.

How you speak:
- Your replies are read aloud, so keep them short and plain. One or two \
sentences for ordinary requests.
- Say what you did, not what you are about to do. No preamble, no bullet lists, \
no markdown — this is speech.
- If something failed, say so plainly and say what you would try next.
{memories}"""


def _machine_description() -> str:
    import getpass

    return (
        f"operating system: {platform.system()} {platform.release()}\n"
        f"hostname: {socket.gethostname()}\n"
        f"user: {getpass.getuser()}\n"
        f"home directory: {Path.home()}"
    )


def build_system_prompt(settings: Settings) -> str:
    facts = load_memory(settings)
    if facts:
        remembered = "\n".join(f"- {entry['fact']}" for entry in facts)
        memories = f"\n\nWhat you already know about this user:\n{remembered}"
    else:
        memories = ""
    return SYSTEM_PROMPT.format(machine=_machine_description(), memories=memories)


@dataclass
class Agent:
    """Holds the conversation and drives one turn at a time."""

    client: Any
    settings: Settings
    approver: Approver
    registry: Registry = field(default_factory=lambda: REGISTRY)
    speak: Callable[[str], None] = lambda text: None
    messages: List[Dict[str, Any]] = field(default_factory=list)

    def __post_init__(self) -> None:
        self._system = build_system_prompt(self.settings)
        self._ctx = ToolContext(
            settings=self.settings,
            approver=self.approver,
            speak=self.speak,
            notify=console.info,
        )

    # -- one turn --------------------------------------------------------

    def send(self, user_message: str) -> str:
        """Run a full turn: think, use tools, and return what to say back."""
        self.messages.append({"role": "user", "content": user_message})

        for _ in range(self.settings.max_iterations):
            response = self._create()

            if response.stop_reason == "refusal":
                self.messages.append({"role": "assistant", "content": response.content})
                details = getattr(response, "stop_details", None)
                reason = getattr(details, "explanation", None) or "no reason given"
                return f"I can't help with that one. ({reason})"

            # Keep the assistant turn verbatim — thinking blocks have to be
            # replayed unchanged for the next request to accept them.
            self.messages.append({"role": "assistant", "content": response.content})

            if response.stop_reason == "pause_turn":
                # A server-side tool hit its limit mid-turn; re-send to resume.
                continue

            tool_uses = [block for block in response.content if block.type == "tool_use"]
            if not tool_uses:
                return self._text_of(response)

            self.messages.append({"role": "user", "content": self._run_tools(tool_uses)})

        return (
            "I stopped after too many steps without finishing. "
            "Could you break that into smaller requests?"
        )

    def _create(self) -> Any:
        return self.client.messages.create(
            model=self.settings.model,
            max_tokens=self.settings.max_tokens,
            system=[
                {
                    "type": "text",
                    "text": self._system,
                    # The system prompt and tool list are identical on every
                    # request, so caching them makes each turn cheaper.
                    "cache_control": {"type": "ephemeral"},
                }
            ],
            thinking={"type": "adaptive"},
            output_config={"effort": self.settings.effort},
            tools=self.registry.specs() + [WEB_SEARCH_TOOL],
            messages=self.messages,
        )

    # -- tool execution --------------------------------------------------

    def _run_tools(self, tool_uses: List[Any]) -> List[Dict[str, Any]]:
        """Execute every requested tool and collect the results for one message."""
        results: List[Dict[str, Any]] = []

        for block in tool_uses:
            tool = self.registry.tools.get(block.name)
            # An action that is about to prompt announces itself in the prompt,
            # so only narrate the ones that run without asking.
            if tool is not None and not self.approver.will_prompt(tool.risk):
                console.tool_start(block.name, tool.describe(block.input))

            content, is_error = self._run_one(block)
            results.append(
                {
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": content,
                    "is_error": is_error,
                }
            )

        return results

    def _run_one(self, block: Any) -> tuple[Any, bool]:
        try:
            output = self.registry.call(block.name, dict(block.input), self._ctx)
        except Denied as exc:
            console.error(str(exc))
            return str(exc), True
        except ToolError as exc:
            console.error(str(exc))
            return str(exc), True
        except Exception as exc:  # a tool bug should reach Claude, not the user
            message = f"{type(exc).__name__}: {exc}"
            console.error(message)
            return message, True

        console.tool_result(self._summarize(output))
        return output, False

    @staticmethod
    def _summarize(output: Any) -> str:
        if isinstance(output, list):
            return "(screenshot attached)"
        first_line = str(output).strip().splitlines()[0] if str(output).strip() else "done"
        return first_line[:110]

    @staticmethod
    def _text_of(response: Any) -> str:
        parts = [block.text for block in response.content if block.type == "text"]
        return "\n".join(part for part in parts if part.strip()).strip() or "Done."
