"""Détection et actions système explicites pour l'assistant de collage.

Ce module ne modifie jamais l'hôte pendant une détection. Les mutations sont
transmises à un helper installé par le paquet et invoqué avec ``pkexec`` avec
des arguments fermés.
"""

from __future__ import annotations

import hashlib
import os
import shlex
import shutil
import subprocess
from pathlib import Path


HELPER_CANDIDATES = (
    Path("/usr/lib/koplyx/koplyx-system-setup"),
    Path("/usr/libexec/koplyx-system-setup"),
)


def session_type() -> str:
    return os.environ.get("XDG_SESSION_TYPE", "").strip().lower()


def xorg_sessions() -> list[Path]:
    directory = Path("/usr/share/xsessions")
    if not directory.is_dir():
        return []
    return sorted(path for path in directory.glob("*.desktop") if path.is_file())


def xorg_session_labels() -> list[str]:
    labels: list[str] = []
    for path in xorg_sessions():
        label = path.stem
        try:
            for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
                if line.startswith("Name="):
                    label = line.partition("=")[2].strip() or label
                    break
        except OSError:
            pass
        labels.append(f"{path.name}: {label}")
    return labels


def command_available(command: str) -> bool:
    return shutil.which(command) is not None


def ydotool_socket() -> Path | None:
    configured = os.environ.get("YDOTOOL_SOCKET")
    if configured:
        return Path(configured)
    runtime_dir = os.environ.get("XDG_RUNTIME_DIR", f"/run/user/{os.getuid()}")
    return Path(runtime_dir) / ".ydotool_socket"


def ydotool_diagnostic() -> dict[str, object]:
    socket = ydotool_socket()
    return {
        "installed": command_available("ydotool"),
        "daemon": bool(socket and socket.exists()),
        "socket": str(socket) if socket else "",
        "writable": bool(socket and socket.exists() and os.access(socket, os.W_OK)),
    }


def helper_path() -> Path | None:
    for path in HELPER_CANDIDATES:
        if path.is_file() and os.access(path, os.X_OK):
            return path
    return None


def run_privileged(action: str, value: str = "") -> tuple[bool, str]:
    """Exécute uniquement une action connue du helper système.

    Aucun shell n'est utilisé et les valeurs sont limitées aux identifiants
    attendus par le helper. L'appel reste toujours déclenché par un bouton.
    """

    if os.environ.get("SNAP") or os.environ.get("FLATPAK_ID"):
        return False, "Cette opération n'est pas disponible dans une sandbox Snap ou Flatpak."
    allowed = {"ydotool-enable", "ydotool-disable", "gdm-xorg-enable", "gdm-restore"}
    if action not in allowed:
        return False, "Action système inconnue."
    if action in {"ydotool-enable", "ydotool-disable"}:
        # Le helper vérifie l'utilisateur réel avec PKEXEC_UID. Aucun nom
        # d'utilisateur fourni par l'interface n'est transmis à la commande.
        value = ""
    elif action == "gdm-xorg-enable":
        candidate = Path(value)
        if candidate.parent != Path("/usr/share/xsessions") or candidate.suffix != ".desktop":
            return False, "Session Xorg invalide."
        value = candidate.name
    else:
        value = ""
    helper = helper_path()
    if helper is None:
        return False, "Le helper système n'est pas installé avec cette version."
    command = ["pkexec", str(helper), action]
    if value:
        command.append(value)
    try:
        result = subprocess.run(command, check=False, capture_output=True, text=True)
    except OSError as exc:
        return False, f"Impossible de lancer l'autorisation système : {exc}"
    detail = (result.stdout or result.stderr).strip()
    if result.returncode != 0:
        return False, detail or "L'opération privilégiée a été refusée."
    return True, detail or "Configuration appliquée."


def gdm_checksum(path: Path = Path("/etc/gdm3/custom.conf")) -> str | None:
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError:
        return None


def display_diagnostic() -> dict[str, object]:
    wayland = session_type() == "wayland"
    x11 = session_type() == "x11"
    return {
        "session": session_type() or "inconnue",
        "display": os.environ.get("DISPLAY", ""),
        "wayland_display": os.environ.get("WAYLAND_DISPLAY", ""),
        "wtype": command_available("wtype"),
        "xdotool": command_available("xdotool"),
        "ydotool": ydotool_diagnostic(),
        "xorg_sessions": xorg_sessions(),
        "wayland": wayland,
        "x11": x11,
        "xwayland_candidate": bool(wayland and os.environ.get("DISPLAY")),
    }


def restore_display_session_command() -> list[str] | None:
    helper = helper_path()
    if helper is None:
        return None
    return ["pkexec", str(helper), "gdm-restore"]


def format_command(command: list[str] | None) -> str:
    return " ".join(shlex.quote(part) for part in command or [])
