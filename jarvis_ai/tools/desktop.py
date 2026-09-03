"""Eyes and hands: the screen, the clipboard, the keyboard and the volume."""

from __future__ import annotations

import base64
import datetime
import io
import platform
import shutil
import subprocess
from typing import Any, Dict, List

from ..permissions import Risk
from ..registry import ToolContext, ToolError, tool
from ._common import require_writable, resolve, truncate

#: Anthropic's vision models see no extra detail above this width, so shrinking
#: to it costs nothing and saves a lot of tokens.
MAX_IMAGE_WIDTH = 1568


def _pyautogui():
    try:
        import pyautogui  # type: ignore

        pyautogui.FAILSAFE = True
        return pyautogui
    except Exception as exc:  # ImportError, or no display attached
        raise ToolError(
            f"Screen and keyboard control needs pyautogui and a graphical session "
            f"({exc}). Install it with: pip install pyautogui"
        ) from exc


@tool(
    risk=Risk.READ,
    description=(
        "Take a screenshot and look at it. The image comes back to you directly, "
        "so use this whenever you need to see what is on the user's screen — to "
        "read an error dialog, find a button, or check what they are working on."
    ),
    params={
        "save_to": "Optional path to also save the PNG to.",
        "show_to_me": "Attach the image so you can see it. Turn off to only save the file.",
    },
    preview=lambda save_to="", show_to_me=True: "capture the screen",
)
def screenshot(ctx: ToolContext, save_to: str = "", show_to_me: bool = True) -> Any:
    pyautogui = _pyautogui()
    image = pyautogui.screenshot()

    saved_note = ""
    if save_to:
        destination = require_writable(ctx, resolve(ctx, save_to))
        destination.parent.mkdir(parents=True, exist_ok=True)
    else:
        stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
        destination = ctx.settings.ensure_data_dir() / "screenshots" / f"{stamp}.png"
        destination.parent.mkdir(parents=True, exist_ok=True)
    image.save(destination)
    saved_note = f"Screenshot saved to {destination}."

    if not show_to_me:
        return saved_note

    if image.width > MAX_IMAGE_WIDTH:
        height = round(image.height * MAX_IMAGE_WIDTH / image.width)
        image = image.resize((MAX_IMAGE_WIDTH, height))

    buffer = io.BytesIO()
    image.convert("RGB").save(buffer, format="PNG")
    encoded = base64.standard_b64encode(buffer.getvalue()).decode("ascii")

    blocks: List[Dict[str, Any]] = [
        {
            "type": "image",
            "source": {"type": "base64", "media_type": "image/png", "data": encoded},
        },
        {"type": "text", "text": saved_note},
    ]
    return blocks


def _clipboard_commands() -> Dict[str, List[str]]:
    system = platform.system()
    if system == "Darwin":
        return {"read": ["pbpaste"], "write": ["pbcopy"]}
    if system == "Windows":
        return {
            "read": ["powershell", "-NoProfile", "-Command", "Get-Clipboard"],
            "write": ["clip"],
        }
    if shutil.which("wl-paste"):
        return {"read": ["wl-paste"], "write": ["wl-copy"]}
    if shutil.which("xclip"):
        return {
            "read": ["xclip", "-selection", "clipboard", "-o"],
            "write": ["xclip", "-selection", "clipboard"],
        }
    return {}


@tool(
    risk=Risk.READ,
    description="Read whatever text is currently on the clipboard.",
    preview=lambda: "read the clipboard",
)
def read_clipboard(ctx: ToolContext) -> str:
    try:
        import pyperclip  # type: ignore

        content = pyperclip.paste()
    except Exception:
        commands = _clipboard_commands()
        if "read" not in commands:
            raise ToolError(
                "No way to read the clipboard here. Install pyperclip, or xclip/wl-clipboard on Linux."
            ) from None
        result = subprocess.run(commands["read"], capture_output=True, text=True)
        content = result.stdout

    if not content.strip():
        return "The clipboard is empty."
    return truncate(f"Clipboard contents:\n{content}")


@tool(
    risk=Risk.WRITE,
    description="Replace the clipboard contents with the given text.",
    params={"text": "Text to put on the clipboard."},
    preview=lambda text: f"copy {len(text)} characters to the clipboard",
)
def write_clipboard(ctx: ToolContext, text: str) -> str:
    try:
        import pyperclip  # type: ignore

        pyperclip.copy(text)
    except Exception:
        commands = _clipboard_commands()
        if "write" not in commands:
            raise ToolError(
                "No way to write the clipboard here. Install pyperclip, or xclip/wl-clipboard on Linux."
            ) from None
        subprocess.run(commands["write"], input=text, text=True, check=True)
    return f"Copied {len(text)} characters to the clipboard."


@tool(
    risk=Risk.WRITE,
    description=(
        "Type text into whatever window currently has focus, as if the user had "
        "typed it. Make sure the right window is focused first."
    ),
    params={
        "text": "Text to type.",
        "interval": "Seconds between keystrokes. Some apps drop input when typed too fast.",
    },
    preview=lambda text, interval=0.02: f"type {text[:60]!r} into the focused window",
)
def type_text(ctx: ToolContext, text: str, interval: float = 0.02) -> str:
    pyautogui = _pyautogui()
    pyautogui.write(text, interval=max(0.0, interval))
    return f"Typed {len(text)} characters."


@tool(
    risk=Risk.WRITE,
    description=(
        "Press a keyboard shortcut, e.g. ['ctrl', 's'] to save or ['alt', 'tab'] "
        "to switch windows. Keys are pressed together and released in reverse."
    ),
    params={"keys": "The keys to press together, e.g. ['ctrl', 'shift', 't']."},
    preview=lambda keys: f"press {' + '.join(keys)}",
)
def press_keys(ctx: ToolContext, keys: List[str]) -> str:
    if not keys:
        raise ToolError("No keys given.")
    pyautogui = _pyautogui()
    pyautogui.hotkey(*[key.strip().lower() for key in keys])
    return f"Pressed {' + '.join(keys)}."


MEDIA_KEYS = {
    "play": "playpause",
    "pause": "playpause",
    "playpause": "playpause",
    "next": "nexttrack",
    "previous": "prevtrack",
    "stop": "stop",
    "volume_up": "volumeup",
    "volume_down": "volumedown",
    "mute": "volumemute",
}


@tool(
    risk=Risk.WRITE,
    description="Control media playback and volume with the media keys.",
    params={
        "action": "One of: play, pause, next, previous, stop, volume_up, volume_down, mute.",
        "repeat": "How many times to press the key — useful for volume steps.",
    },
    preview=lambda action, repeat=1: f"press the {action.replace('_', ' ')} media key {repeat}x",
)
def media_control(ctx: ToolContext, action: str, repeat: int = 1) -> str:
    key = MEDIA_KEYS.get(action.strip().lower().replace("-", "_"))
    if key is None:
        raise ToolError(f"Unknown action {action!r}. Use one of: {', '.join(MEDIA_KEYS)}.")

    pyautogui = _pyautogui()
    for _ in range(max(1, min(repeat, 25))):
        pyautogui.press(key)
    return f"Pressed {action} {max(1, repeat)} time(s)."


@tool(
    risk=Risk.WRITE,
    description="Set the system output volume to a percentage.",
    params={"level": "Volume from 0 to 100."},
    preview=lambda level: f"set the system volume to {level}%",
)
def set_volume(ctx: ToolContext, level: int) -> str:
    level = max(0, min(100, int(level)))
    system = platform.system()

    if system == "Darwin":
        command = ["osascript", "-e", f"set volume output volume {level}"]
    elif system == "Linux" and shutil.which("pactl"):
        command = ["pactl", "set-sink-volume", "@DEFAULT_SINK@", f"{level}%"]
    elif system == "Linux" and shutil.which("amixer"):
        command = ["amixer", "-q", "sset", "Master", f"{level}%"]
    else:
        raise ToolError(
            f"Setting an exact volume is not supported on {system} here. "
            f"Use media_control with volume_up or volume_down instead."
        )

    try:
        subprocess.run(command, check=True, capture_output=True)
    except (OSError, subprocess.CalledProcessError) as exc:
        raise ToolError(f"Could not set the volume: {exc}") from exc
    return f"Volume set to {level}%."


@tool(
    risk=Risk.READ,
    description="List the titles of the windows that are currently open.",
    preview=lambda: "list open windows",
)
def list_windows(ctx: ToolContext) -> str:
    system = platform.system()
    try:
        if system == "Linux" and shutil.which("wmctrl"):
            result = subprocess.run(["wmctrl", "-l"], capture_output=True, text=True, check=True)
            titles = [line.split(None, 3)[-1] for line in result.stdout.splitlines() if line.strip()]
        elif system == "Darwin":
            script = (
                'tell application "System Events" to get the name of every process '
                "whose background only is false"
            )
            result = subprocess.run(["osascript", "-e", script], capture_output=True, text=True, check=True)
            titles = [part.strip() for part in result.stdout.split(",") if part.strip()]
        else:
            import pygetwindow  # type: ignore

            titles = [title for title in pygetwindow.getAllTitles() if title.strip()]
    except Exception as exc:
        raise ToolError(
            f"Could not list windows on {system} ({exc}). "
            f"Install pygetwindow, or wmctrl on Linux."
        ) from exc

    if not titles:
        return "No open windows found."
    return truncate("Open windows:\n" + "\n".join(f"- {title}" for title in titles))
