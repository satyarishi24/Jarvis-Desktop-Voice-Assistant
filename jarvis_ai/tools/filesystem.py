"""Reading, writing and reorganising files."""

from __future__ import annotations

import fnmatch
import os
import shutil
from pathlib import Path
from typing import List

from ..permissions import Risk
from ..registry import ToolContext, ToolError, tool
from ._common import guard_sensitive_read, human_size, require_writable, resolve, truncate

SKIP_DIRS = {".git", "node_modules", "__pycache__", ".venv", "venv", ".mypy_cache", ".cache"}


@tool(
    risk=Risk.READ,
    description=(
        "List the contents of a directory. Use this to explore the filesystem "
        "before acting on it."
    ),
    params={
        "path": "Directory to list. Supports ~ and environment variables. Defaults to the home directory.",
        "show_hidden": "Include dotfiles.",
    },
    preview=lambda path="~", show_hidden=False: f"list the contents of {path}",
)
def list_directory(ctx: ToolContext, path: str = "~", show_hidden: bool = False) -> str:
    target = resolve(ctx, path)
    if not target.is_dir():
        raise ToolError(f"{target} is not a directory.")

    rows: List[str] = []
    try:
        entries = sorted(target.iterdir(), key=lambda p: (p.is_file(), p.name.lower()))
    except PermissionError as exc:
        raise ToolError(f"Permission denied reading {target}: {exc}") from exc

    for entry in entries:
        if not show_hidden and entry.name.startswith("."):
            continue
        try:
            if entry.is_dir():
                rows.append(f"{entry.name}/")
            else:
                rows.append(f"{entry.name}  ({human_size(entry.stat().st_size)})")
        except OSError:
            rows.append(f"{entry.name}  (unreadable)")

    if not rows:
        return f"{target} is empty."
    return truncate(f"{target} — {len(rows)} entries:\n" + "\n".join(rows))


@tool(
    risk=Risk.READ,
    description="Read a text file. Binary files are reported rather than dumped.",
    params={
        "path": "File to read.",
        "max_bytes": "Stop after this many bytes. Keep it small for large files.",
    },
    preview=lambda path, max_bytes=40000: f"read the file {path}",
)
def read_file(ctx: ToolContext, path: str, max_bytes: int = 40000) -> str:
    target = resolve(ctx, path)
    if not target.is_file():
        raise ToolError(f"{target} does not exist or is not a file.")

    guard_sensitive_read(ctx, target)

    raw = target.read_bytes()[: max(1, max_bytes)]
    if b"\0" in raw[:4096]:
        return f"{target} looks like a binary file ({human_size(target.stat().st_size)}); not shown."

    text = raw.decode("utf-8", errors="replace")
    return truncate(f"{target}:\n{text}")


@tool(
    risk=Risk.WRITE,
    description=(
        "Write text to a file, creating parent directories as needed. "
        "Overwrites by default — set append to add to the end instead."
    ),
    params={
        "path": "File to write.",
        "content": "Text to write.",
        "append": "Append instead of overwriting.",
    },
    preview=lambda path, content, append=False: (
        f"{'append to' if append else 'write'} {path} "
        f"({len(content)} characters)"
    ),
)
def write_file(ctx: ToolContext, path: str, content: str, append: bool = False) -> str:
    target = require_writable(ctx, resolve(ctx, path))
    target.parent.mkdir(parents=True, exist_ok=True)
    with open(target, "a" if append else "w", encoding="utf-8") as handle:
        handle.write(content)
    verb = "Appended to" if append else "Wrote"
    return f"{verb} {target} ({len(content)} characters)."


@tool(
    risk=Risk.WRITE,
    description="Create a directory, including any missing parents.",
    params={"path": "Directory to create."},
    preview=lambda path: f"create the directory {path}",
)
def create_directory(ctx: ToolContext, path: str) -> str:
    target = require_writable(ctx, resolve(ctx, path))
    target.mkdir(parents=True, exist_ok=True)
    return f"Created {target}."


@tool(
    risk=Risk.WRITE,
    description="Move or rename a file or directory.",
    params={"source": "Path to move.", "destination": "Where to move it to."},
    preview=lambda source, destination: f"move {source} to {destination}",
)
def move_path(ctx: ToolContext, source: str, destination: str) -> str:
    src = require_writable(ctx, resolve(ctx, source))
    dst = require_writable(ctx, resolve(ctx, destination))
    if not src.exists():
        raise ToolError(f"{src} does not exist.")
    if dst.is_dir():
        dst = dst / src.name
    if dst.exists():
        raise ToolError(f"{dst} already exists; move or rename it first.")
    shutil.move(str(src), str(dst))
    return f"Moved {src} to {dst}."


@tool(
    risk=Risk.WRITE,
    description="Copy a file, or a directory and everything inside it.",
    params={"source": "Path to copy.", "destination": "Where to copy it to."},
    preview=lambda source, destination: f"copy {source} to {destination}",
)
def copy_path(ctx: ToolContext, source: str, destination: str) -> str:
    src = resolve(ctx, source)
    dst = require_writable(ctx, resolve(ctx, destination))
    if not src.exists():
        raise ToolError(f"{src} does not exist.")
    if dst.is_dir() and src.is_file():
        dst = dst / src.name
    if src.is_dir():
        shutil.copytree(src, dst, dirs_exist_ok=False)
    else:
        shutil.copy2(src, dst)
    return f"Copied {src} to {dst}."


@tool(
    risk=Risk.SYSTEM,
    description=(
        "Delete a file or directory. Moves it to the trash when the send2trash "
        "package is installed, otherwise deletes permanently."
    ),
    params={
        "path": "Path to delete.",
        "recursive": "Required to delete a directory that is not empty.",
    },
    preview=lambda path, recursive=False: (
        f"DELETE {path}" + (" and everything inside it" if recursive else "")
    ),
)
def delete_path(ctx: ToolContext, path: str, recursive: bool = False) -> str:
    target = require_writable(ctx, resolve(ctx, path))
    if not target.exists():
        raise ToolError(f"{target} does not exist.")

    try:
        from send2trash import send2trash  # type: ignore

        send2trash(str(target))
        return f"Moved {target} to the trash."
    except ImportError:
        pass

    if target.is_dir():
        if not recursive and any(target.iterdir()):
            raise ToolError(
                f"{target} is not empty. Call again with recursive=True to delete its contents."
            )
        shutil.rmtree(target)
    else:
        target.unlink()
    return f"Permanently deleted {target} (install send2trash to delete to the trash instead)."


@tool(
    risk=Risk.READ,
    description=(
        "Find files by name pattern, e.g. '*.pdf' or 'invoice*'. "
        "Searches recursively and skips build and VCS directories."
    ),
    params={
        "pattern": "Glob pattern matched against the file name.",
        "path": "Directory to search under.",
        "max_results": "Stop after this many matches.",
    },
    preview=lambda pattern, path="~", max_results=50: f"search for files matching {pattern!r} under {path}",
)
def find_files(ctx: ToolContext, pattern: str, path: str = "~", max_results: int = 50) -> str:
    root = resolve(ctx, path)
    if not root.is_dir():
        raise ToolError(f"{root} is not a directory.")

    matches: List[str] = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS and not d.startswith(".")]
        for name in filenames:
            if fnmatch.fnmatch(name, pattern):
                matches.append(str(Path(dirpath) / name))
                if len(matches) >= max_results:
                    return truncate(
                        f"First {len(matches)} matches for {pattern!r}:\n" + "\n".join(matches)
                    )

    if not matches:
        return f"No files matching {pattern!r} under {root}."
    return truncate(f"{len(matches)} matches for {pattern!r}:\n" + "\n".join(matches))


@tool(
    risk=Risk.READ,
    description="Search inside text files for a string. The filesystem equivalent of grep.",
    params={
        "query": "Text to look for (case-insensitive).",
        "path": "Directory or file to search.",
        "file_pattern": "Only search files whose name matches this glob.",
        "max_results": "Stop after this many matching lines.",
    },
    preview=lambda query, path="~", file_pattern="*", max_results=50: (
        f"search for {query!r} inside {file_pattern} files under {path}"
    ),
)
def search_in_files(
    ctx: ToolContext,
    query: str,
    path: str = "~",
    file_pattern: str = "*",
    max_results: int = 50,
) -> str:
    root = resolve(ctx, path)
    needle = query.lower()
    hits: List[str] = []

    def scan(file_path: Path) -> bool:
        """Returns False when we've collected enough results."""
        try:
            with open(file_path, "r", encoding="utf-8", errors="ignore") as handle:
                for number, line in enumerate(handle, 1):
                    if needle in line.lower():
                        hits.append(f"{file_path}:{number}: {line.strip()[:200]}")
                        if len(hits) >= max_results:
                            return False
        except OSError:
            pass
        return True

    if root.is_file():
        scan(root)
    else:
        for dirpath, dirnames, filenames in os.walk(root):
            dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS and not d.startswith(".")]
            for name in filenames:
                if fnmatch.fnmatch(name, file_pattern) and not scan(Path(dirpath) / name):
                    break
            else:
                continue
            break

    if not hits:
        return f"No matches for {query!r} under {root}."
    return truncate(f"{len(hits)} matching lines for {query!r}:\n" + "\n".join(hits))


@tool(
    risk=Risk.READ,
    description="Show size, timestamps and permissions for a file or directory.",
    params={"path": "Path to inspect."},
    preview=lambda path: f"inspect {path}",
)
def file_info(ctx: ToolContext, path: str) -> str:
    import datetime as _dt

    target = resolve(ctx, path)
    if not target.exists():
        raise ToolError(f"{target} does not exist.")

    stat = target.stat()
    kind = "directory" if target.is_dir() else "file"
    modified = _dt.datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M:%S")
    return (
        f"{target}\n"
        f"  type: {kind}\n"
        f"  size: {human_size(stat.st_size)}\n"
        f"  modified: {modified}\n"
        f"  permissions: {oct(stat.st_mode)[-3:]}"
    )
