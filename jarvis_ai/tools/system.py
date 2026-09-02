"""Machine state: hardware, processes, power."""

from __future__ import annotations

import datetime
import platform
import shutil
import socket
import subprocess

from ..permissions import Risk
from ..registry import ToolContext, ToolError, tool
from ._common import human_size, truncate


def _psutil():
    try:
        import psutil  # type: ignore

        return psutil
    except ImportError:
        return None


@tool(
    risk=Risk.READ,
    description=(
        "Report what this machine is and how it is doing right now: operating "
        "system, CPU, memory, disk and battery."
    ),
    preview=lambda: "read this machine's hardware and resource usage",
)
def system_info(ctx: ToolContext) -> str:
    lines = [
        f"system: {platform.system()} {platform.release()} ({platform.machine()})",
        f"hostname: {socket.gethostname()}",
        f"python: {platform.python_version()}",
        f"local time: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
    ]

    psutil = _psutil()
    if psutil is None:
        usage = shutil.disk_usage("/")
        lines.append(
            f"disk (/): {human_size(usage.used)} used of {human_size(usage.total)}, "
            f"{human_size(usage.free)} free"
        )
        lines.append("(install psutil for CPU, memory and battery details)")
        return "\n".join(lines)

    memory = psutil.virtual_memory()
    lines += [
        f"cpu: {psutil.cpu_count(logical=True)} threads, {psutil.cpu_percent(interval=0.3):.0f}% in use",
        f"memory: {human_size(memory.used)} used of {human_size(memory.total)} ({memory.percent:.0f}%)",
    ]
    for part in psutil.disk_partitions(all=False):
        try:
            usage = psutil.disk_usage(part.mountpoint)
        except (PermissionError, OSError):
            continue
        lines.append(
            f"disk {part.mountpoint}: {human_size(usage.used)} of {human_size(usage.total)} "
            f"used ({usage.percent:.0f}%)"
        )

    battery = getattr(psutil, "sensors_battery", lambda: None)()
    if battery is not None:
        state = "charging" if battery.power_plugged else "on battery"
        lines.append(f"battery: {battery.percent:.0f}% ({state})")

    return "\n".join(lines)


@tool(
    risk=Risk.READ,
    description=(
        "List running processes, heaviest first, optionally filtered by name. "
        "Use this to find what is slowing the machine down or to get a pid."
    ),
    params={
        "name_filter": "Only show processes whose name contains this text.",
        "limit": "How many processes to show.",
    },
    preview=lambda name_filter="", limit=15: (
        f"list running processes" + (f" matching {name_filter!r}" if name_filter else "")
    ),
)
def list_processes(ctx: ToolContext, name_filter: str = "", limit: int = 15) -> str:
    psutil = _psutil()
    if psutil is None:
        raise ToolError("Listing processes needs the psutil package: pip install psutil")

    needle = name_filter.lower()
    rows = []
    for proc in psutil.process_iter(["pid", "name", "memory_percent", "cpu_percent"]):
        info = proc.info
        if needle and needle not in (info.get("name") or "").lower():
            continue
        rows.append(info)

    rows.sort(key=lambda info: info.get("memory_percent") or 0, reverse=True)
    if not rows:
        return f"No running process matches {name_filter!r}." if needle else "No processes found."

    lines = [f"{'PID':>7}  {'MEM%':>5}  NAME"]
    for info in rows[: max(1, limit)]:
        lines.append(f"{info['pid']:>7}  {(info.get('memory_percent') or 0):>5.1f}  {info.get('name')}")
    return truncate("\n".join(lines))


@tool(
    risk=Risk.SYSTEM,
    description=(
        "Stop a running process by pid. Confirm the pid with list_processes "
        "first — killing the wrong one can lose the user's unsaved work."
    ),
    params={
        "pid": "Process id to stop.",
        "force": "Kill immediately instead of asking the process to exit cleanly.",
    },
    preview=lambda pid, force=False: f"{'force kill' if force else 'stop'} process {pid}",
)
def kill_process(ctx: ToolContext, pid: int, force: bool = False) -> str:
    psutil = _psutil()
    if psutil is None:
        raise ToolError("Stopping processes needs the psutil package: pip install psutil")

    try:
        proc = psutil.Process(pid)
        name = proc.name()
        proc.kill() if force else proc.terminate()
        proc.wait(timeout=5)
    except psutil.NoSuchProcess:
        raise ToolError(f"No process with pid {pid}.") from None
    except psutil.AccessDenied:
        raise ToolError(f"Not allowed to stop pid {pid} — it belongs to another user.") from None
    except psutil.TimeoutExpired:
        return f"Asked pid {pid} to stop, but it is still running. Try again with force=True."
    return f"Stopped {name} (pid {pid})."


_POWER_COMMANDS = {
    "shutdown": {
        "Windows": ["shutdown", "/s", "/t", "5"],
        "Darwin": ["osascript", "-e", 'tell app "System Events" to shut down'],
        "Linux": ["systemctl", "poweroff"],
    },
    "restart": {
        "Windows": ["shutdown", "/r", "/t", "5"],
        "Darwin": ["osascript", "-e", 'tell app "System Events" to restart'],
        "Linux": ["systemctl", "reboot"],
    },
    "sleep": {
        "Windows": ["rundll32.exe", "powrprof.dll,SetSuspendState", "0,1,0"],
        "Darwin": ["pmset", "sleepnow"],
        "Linux": ["systemctl", "suspend"],
    },
    "lock": {
        "Windows": ["rundll32.exe", "user32.dll,LockWorkStation"],
        "Darwin": ["pmset", "displaysleepnow"],
        "Linux": ["loginctl", "lock-session"],
    },
    "log_out": {
        "Windows": ["shutdown", "/l"],
        "Darwin": ["osascript", "-e", 'tell app "System Events" to log out'],
        "Linux": ["loginctl", "terminate-user", ""],
    },
}


@tool(
    risk=Risk.SYSTEM,
    description=(
        "Shut down, restart, sleep, lock or log out of the machine. Always "
        "confirm with the user first — anything unsaved will be lost."
    ),
    params={"action": "One of: shutdown, restart, sleep, lock, log_out."},
    preview=lambda action: f"{action.replace('_', ' ').upper()} this machine",
)
def power_action(ctx: ToolContext, action: str) -> str:
    key = action.strip().lower().replace(" ", "_").replace("-", "_")
    if key not in _POWER_COMMANDS:
        raise ToolError(f"Unknown power action {action!r}. Use one of: {', '.join(_POWER_COMMANDS)}.")

    command = _POWER_COMMANDS[key].get(platform.system())
    if command is None:
        raise ToolError(f"Don't know how to {key} on {platform.system()}.")

    if key == "log_out" and platform.system() == "Linux":
        import getpass

        command = ["loginctl", "terminate-user", getpass.getuser()]

    ctx.speak(f"{key.replace('_', ' ').capitalize()}ing now.")
    try:
        subprocess.Popen(command)
    except OSError as exc:
        raise ToolError(f"Could not {key}: {exc}") from exc
    return f"Issued the {key} command."


@tool(
    risk=Risk.READ,
    description="Report network status: hostname, local addresses and whether the machine is online.",
    preview=lambda: "check network status",
)
def network_info(ctx: ToolContext) -> str:
    lines = [f"hostname: {socket.gethostname()}"]

    psutil = _psutil()
    if psutil is not None:
        for name, addrs in psutil.net_if_addrs().items():
            for addr in addrs:
                if addr.family == socket.AF_INET and not addr.address.startswith("127."):
                    lines.append(f"{name}: {addr.address}")
    else:
        try:
            lines.append(f"local address: {socket.gethostbyname(socket.gethostname())}")
        except OSError:
            pass

    probe = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    probe.settimeout(3)
    try:
        probe.connect(("1.1.1.1", 53))
        lines.append("internet: reachable")
    except OSError:
        lines.append("internet: unreachable")
    finally:
        probe.close()

    return "\n".join(lines)


@tool(
    risk=Risk.READ,
    description="Get the current date and time, including the day of the week.",
    preview=lambda: "check the current date and time",
)
def current_datetime(ctx: ToolContext) -> str:
    now = datetime.datetime.now().astimezone()
    return now.strftime("%A, %d %B %Y, %I:%M:%S %p %Z").replace(" 0", " ")
