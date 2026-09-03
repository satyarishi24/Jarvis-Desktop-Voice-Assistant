"""Command line entry point:  python -m jarvis_ai"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import List, Optional

from . import __version__, console
from .agent import Agent
from .config import Settings
from .permissions import Approver, Policy
from .tools import REGISTRY
from .voice import Voice

EXIT_WORDS = {"exit", "quit", "goodbye", "bye", "stop", "go offline", "shut down jarvis"}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="jarvis",
        description="An AI assistant that can actually operate your device.",
    )
    parser.add_argument(
        "request",
        nargs="*",
        help="Do one thing and exit. Without this, Jarvis starts an interactive session.",
    )
    parser.add_argument("--version", action="version", version=f"jarvis {__version__}")

    approval = parser.add_argument_group("approval")
    approval.add_argument(
        "--policy",
        choices=[policy.value for policy in Policy],
        default=Policy.ASK.value,
        help="How much Jarvis may do without asking (default: ask).",
    )
    approval.add_argument(
        "--yolo",
        action="store_true",
        help="Approve everything automatically. Only sensible in a throwaway VM.",
    )
    approval.add_argument(
        "--read-only",
        action="store_true",
        help="Refuse every action that would change the machine.",
    )
    approval.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what each action would do without doing it.",
    )
    approval.add_argument(
        "--writable-root",
        action="append",
        metavar="PATH",
        help="A directory Jarvis may write to. Repeatable. Defaults to your home directory.",
    )

    voice = parser.add_argument_group("voice")
    voice.add_argument("--voice", action="store_true", help="Listen for spoken requests.")
    voice.add_argument("--no-speech", action="store_true", help="Do not speak replies aloud.")

    model = parser.add_argument_group("model")
    model.add_argument("--model", help="Claude model to use.")
    model.add_argument(
        "--effort",
        choices=["low", "medium", "high", "xhigh", "max"],
        help="How hard Claude thinks before acting (default: high).",
    )

    return parser


def settings_from_args(args: argparse.Namespace) -> Settings:
    settings = Settings.from_env()

    settings.policy = Policy(args.policy)
    if args.read_only:
        settings.policy = Policy.READ_ONLY
    if args.yolo:
        settings.policy = Policy.YOLO

    settings.dry_run = args.dry_run
    settings.voice_input = args.voice or settings.voice_input
    settings.voice_output = not args.no_speech and settings.voice_output

    if args.writable_root:
        settings.writable_roots = [Path(root).expanduser().resolve() for root in args.writable_root]
    if args.model:
        settings.model = args.model
    if args.effort:
        settings.effort = args.effort

    return settings


def make_client():
    """Build the Anthropic client, with a useful message when it can't be built."""
    try:
        import anthropic
    except ImportError:
        console.error(
            "The anthropic package is missing. Install it with:\n"
            "      pip install -r requirements.txt"
        )
        raise SystemExit(1) from None

    try:
        return anthropic.Anthropic()
    except Exception as exc:
        console.error(
            f"Could not authenticate with the Claude API ({exc}).\n"
            "      Set ANTHROPIC_API_KEY, or run 'ant auth login'."
        )
        raise SystemExit(1) from None


def read_request(voice: Voice) -> Optional[str]:
    """Get the next request, from the microphone if enabled, else the keyboard."""
    if voice.listen_enabled:
        console.info("listening…")
        heard = voice.listen()
        if heard:
            print(f"  {console.bold('you')} {heard}")
            return heard
        console.info("didn't catch that — type it instead, or press enter to listen again.")

    try:
        typed = input(f"  {console.bold('you')} ").strip()
    except (EOFError, KeyboardInterrupt):
        return None
    return typed or None


def run_turn(agent: Agent, voice: Voice, request: str) -> None:
    reply = agent.send(request)
    console.assistant(reply)
    voice.speak(reply)


def main(argv: Optional[List[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    settings = settings_from_args(args)

    voice = Voice(
        speak_enabled=settings.voice_output,
        listen_enabled=settings.voice_input,
    )
    for note in voice.notes:
        console.info(note)

    if settings.policy is Policy.YOLO:
        console.error("Running with --yolo: every action runs without asking.")

    agent = Agent(
        client=make_client(),
        settings=settings,
        approver=Approver(
            policy=settings.policy,
            dry_run=settings.dry_run,
            confirm=console.confirm,
        ),
        speak=voice.speak,
    )

    # One-shot mode: do the thing, print the answer, exit.
    if args.request:
        run_turn(agent, voice, " ".join(args.request))
        return 0

    console.banner(
        model=settings.model,
        policy=settings.policy.value,
        tool_count=len(REGISTRY.tools),
        dry_run=settings.dry_run,
    )
    greeting = "Jarvis here. What do you need?"
    console.assistant(greeting)
    voice.speak(greeting)

    while True:
        try:
            request = read_request(voice)
        except KeyboardInterrupt:
            break

        if request is None:
            break
        if request.lower().strip(" .!") in EXIT_WORDS:
            break

        try:
            run_turn(agent, voice, request)
        except KeyboardInterrupt:
            console.error("Interrupted.")
        except Exception as exc:
            console.error(f"{type(exc).__name__}: {exc}")

    farewell = "Going offline. Talk soon."
    console.assistant(farewell)
    voice.speak(farewell)
    return 0


if __name__ == "__main__":
    sys.exit(main())
