"""Opening things: files, folders, applications, websites, music."""

from __future__ import annotations

import os
import platform
import random
import shutil
import subprocess
import urllib.parse
import webbrowser
from pathlib import Path

from ..permissions import Risk
from ..registry import ToolContext, ToolError, tool
from ._common import resolve

MUSIC_SUFFIXES = {".mp3", ".m4a", ".wav", ".flac", ".ogg", ".aac", ".wma", ".opus"}


def _open_with_desktop(target: str) -> None:
    """Hand a path or URL to whatever the desktop says should handle it."""
    system = platform.system()
    if system == "Windows":
        os.startfile(target)  # type: ignore[attr-defined]
    elif system == "Darwin":
        subprocess.Popen(["open", target])
    else:
        subprocess.Popen(
            ["xdg-open", target], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
        )


@tool(
    risk=Risk.WRITE,
    description=(
        "Open a file or folder in whatever application the system normally uses "
        "for it — a PDF in the PDF reader, a folder in the file manager."
    ),
    params={"path": "File or folder to open."},
    preview=lambda path: f"open {path} in its default application",
)
def open_path(ctx: ToolContext, path: str) -> str:
    target = resolve(ctx, path)
    if not target.exists():
        raise ToolError(f"{target} does not exist.")
    try:
        _open_with_desktop(str(target))
    except OSError as exc:
        raise ToolError(f"Could not open {target}: {exc}") from exc
    return f"Opened {target}."


@tool(
    risk=Risk.WRITE,
    description="Open a website in the default browser.",
    params={"url": "Full URL, or a bare domain like 'youtube.com'."},
    preview=lambda url: f"open {url} in the browser",
)
def open_website(ctx: ToolContext, url: str) -> str:
    address = url.strip()
    if not address.startswith(("http://", "https://")):
        address = f"https://{address}"
    if not webbrowser.open(address):
        raise ToolError(f"No browser available to open {address}.")
    return f"Opened {address}."


@tool(
    risk=Risk.WRITE,
    description=(
        "Run a web search in the default browser. Use this when the user wants "
        "to look at the results themselves; use the web_search tool instead when "
        "you need the answer to reason with."
    ),
    params={
        "query": "What to search for.",
        "engine": "One of: google, duckduckgo, youtube, maps.",
    },
    preview=lambda query, engine="google": f"search {engine} for {query!r} in the browser",
)
def search_in_browser(ctx: ToolContext, query: str, engine: str = "google") -> str:
    templates = {
        "google": "https://www.google.com/search?q={}",
        "duckduckgo": "https://duckduckgo.com/?q={}",
        "youtube": "https://www.youtube.com/results?search_query={}",
        "maps": "https://www.google.com/maps/search/{}",
    }
    template = templates.get(engine.lower())
    if template is None:
        raise ToolError(f"Unknown engine {engine!r}. Use one of: {', '.join(templates)}.")

    url = template.format(urllib.parse.quote_plus(query))
    webbrowser.open(url)
    return f"Searched {engine} for {query!r}."


@tool(
    risk=Risk.WRITE,
    description=(
        "Launch an installed application by name, e.g. 'Spotify', 'Calculator', "
        "'code'. If this fails, fall back to run_command with the exact binary."
    ),
    params={"name": "Name of the application."},
    preview=lambda name: f"launch the {name} application",
)
def launch_app(ctx: ToolContext, name: str) -> str:
    system = platform.system()
    app = name.strip()

    try:
        if system == "Darwin":
            subprocess.run(["open", "-a", app], check=True, capture_output=True)
            return f"Launched {app}."

        binary = shutil.which(app) or shutil.which(app.lower().replace(" ", "-"))
        if binary:
            subprocess.Popen(
                [binary], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
            )
            return f"Launched {app}."

        if system == "Windows":
            os.startfile(app)  # type: ignore[attr-defined]
            return f"Launched {app}."

        if shutil.which("gtk-launch"):
            subprocess.run(
                ["gtk-launch", app.lower().replace(" ", "-")],
                check=True,
                capture_output=True,
            )
            return f"Launched {app}."
    except (OSError, subprocess.CalledProcessError) as exc:
        raise ToolError(f"Could not launch {app}: {exc}") from exc

    raise ToolError(
        f"Could not find an application called {app!r}. "
        f"Try which_program to check the exact name of its executable."
    )


@tool(
    risk=Risk.WRITE,
    description=(
        "Play a song from the user's music folder. With no title, plays a "
        "random track."
    ),
    params={
        "title": "Part of the file name to match. Leave empty for a random track.",
        "folder": "Where to look. Defaults to the system Music folder.",
    },
    preview=lambda title="", folder="": (
        f"play {title!r} from the music folder" if title else "play a random song"
    ),
)
def play_music(ctx: ToolContext, title: str = "", folder: str = "") -> str:
    music_dir = resolve(ctx, folder) if folder else Path.home() / "Music"
    if not music_dir.is_dir():
        raise ToolError(f"No music folder at {music_dir}. Pass one explicitly with 'folder'.")

    tracks = [
        path
        for path in music_dir.rglob("*")
        if path.is_file() and path.suffix.lower() in MUSIC_SUFFIXES
    ]
    if title:
        needle = title.lower()
        tracks = [path for path in tracks if needle in path.stem.lower()]

    if not tracks:
        raise ToolError(
            f"No music matching {title!r} in {music_dir}." if title else f"No audio files in {music_dir}."
        )

    chosen = random.choice(tracks)
    _open_with_desktop(str(chosen))
    return f"Playing {chosen.name}."
