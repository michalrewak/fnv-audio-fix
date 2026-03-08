"""Game path detection for Fallout: New Vegas."""

import os
import sys
from pathlib import Path

# Common Steam library locations
_STEAM_COMMON = [
    r"C:\Program Files (x86)\Steam\steamapps\common",
    r"C:\Program Files\Steam\steamapps\common",
    r"D:\Steam\steamapps\common",
    r"D:\SteamLibrary\steamapps\common",
    r"E:\SteamLibrary\steamapps\common",
]

_FNV_FOLDER = "Fallout New Vegas"


def find_game_data_dir(custom_path=None):
    """Locate the FNV Data directory.

    Args:
        custom_path: Explicit path to the game Data directory (or game root).

    Returns:
        Path to the Data directory, or None if not found.
    """
    if custom_path:
        p = Path(custom_path)
        if p.name == "Data" and p.is_dir():
            return p
        data = p / "Data"
        if data.is_dir():
            return data
        return None

    # Try common Steam locations
    for steam_dir in _STEAM_COMMON:
        data = Path(steam_dir) / _FNV_FOLDER / "Data"
        if data.is_dir():
            return data

    # Try Steam registry (Windows only)
    if sys.platform == "win32":
        path = _find_via_registry()
        if path:
            return path

    return None


def _find_via_registry():
    """Try to find FNV install path from Windows registry."""
    try:
        import winreg

        key_paths = [
            r"SOFTWARE\WOW6432Node\Bethesda Softworks\FalloutNV",
            r"SOFTWARE\Bethesda Softworks\FalloutNV",
        ]
        for key_path in key_paths:
            try:
                with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, key_path) as key:
                    install_path, _ = winreg.QueryValueEx(
                        key, "Installed Path"
                    )
                    data = Path(install_path) / "Data"
                    if data.is_dir():
                        return data
            except OSError:
                continue
    except ImportError:
        pass
    return None
