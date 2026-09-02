"""Arbitrary command execution — the tool that makes 'do anything' literal."""

from __future__ import annotations

import subprocess
import sys

from ..permissions import Risk
from ..registry import ToolContext, ToolError, tool
from ._common import resolve, truncate


@tool(
    risk=Risk.SYSTEM,
    description=(
        "Run a shell command on this machine and return its output. This is the "
        "fallback for anything the other tools do not cover — package managers, "
        "git, ffmpeg, system utilities. Prefer a dedicated tool when one exists, "
        "because dedicated tools are clearer to the user at the approval prompt. "
        "The command runs with the user's own privileges; never use sudo unless "
        "the user explicitly asked for it."
    ),
    params={
        "command": "The command line to run, exactly as it would be typed in a terminal.",
        "working_directory": "Directory to run it in. Defaults to the home directory.",
        "timeout": "Seconds to wait before killing the command.",
    },
    preview=lambda command, working_directory="~", timeout=0: (
        f"run the shell command: {command}"
        + (f"  (in {working_directory})" if working_directory not in ("~", "") else "")
    ),
)
def run_command(
    ctx: ToolContext,
    command: str,
    working_directory: str = "~",
    timeout: int = 0,
) -> str:
    cwd = resolve(ctx, working_directory)
    if not cwd.is_dir():
        raise ToolError(f"{cwd} is not a directory.")

    limit = timeout if timeout > 0 else ctx.settings.command_timeout

    try:
        completed = subprocess.run(
            command,
            shell=True,
            cwd=str(cwd),
            capture_output=True,
            text=True,
            timeout=limit,
            errors="replace",
        )
    except subprocess.TimeoutExpired:
        raise ToolError(f"Command timed out after {limit}s: {command}") from None
    except OSError as exc:
        raise ToolError(f"Could not run the command: {exc}") from exc

    parts = [f"exit code: {completed.returncode}"]
    if completed.stdout.strip():
        parts.append(f"stdout:\n{completed.stdout.rstrip()}")
    if completed.stderr.strip():
        parts.append(f"stderr:\n{completed.stderr.rstrip()}")
    if len(parts) == 1:
        parts.append("(no output)")
    return truncate("\n".join(parts))


@tool(
    risk=Risk.READ,
    description=(
        "Check whether a program is installed and where it lives. Use this "
        "before running a command that might not exist on this machine."
    ),
    params={"program": "Name of the executable, e.g. 'ffmpeg' or 'git'."},
    preview=lambda program: f"check whether {program} is installed",
)
def which_program(ctx: ToolContext, program: str) -> str:
    import shutil as _shutil

    location = _shutil.which(program)
    if location is None:
        return f"{program} is not installed or not on PATH."
    return f"{program} is at {location}."


@tool(
    risk=Risk.WRITE,
    description=(
        "Start a long-running program in the background and return immediately, "
        "without waiting for it to finish. Use this for servers, editors and "
        "anything with a GUI; use run_command when you need the output."
    ),
    params={
        "command": "The command line to start.",
        "working_directory": "Directory to start it in.",
    },
    preview=lambda command, working_directory="~": f"start {command} in the background",
)
def start_background(ctx: ToolContext, command: str, working_directory: str = "~") -> str:
    cwd = resolve(ctx, working_directory)
    kwargs = {
        "shell": True,
        "cwd": str(cwd),
        "stdout": subprocess.DEVNULL,
        "stderr": subprocess.DEVNULL,
        "stdin": subprocess.DEVNULL,
    }
    if sys.platform == "win32":
        kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP  # type: ignore[attr-defined]
    else:
        kwargs["start_new_session"] = True

    try:
        process = subprocess.Popen(command, **kwargs)  # type: ignore[arg-type]
    except OSError as exc:
        raise ToolError(f"Could not start the command: {exc}") from exc
    return f"Started '{command}' in the background (pid {process.pid})."
