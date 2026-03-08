"""Core fix logic: INI audio settings patch for crackling fix."""

import os
import re
import shutil
import json
import stat
from pathlib import Path
from datetime import datetime


# Viva New Vegas recommended audio settings (prevent crackling / stuttering)
AUDIO_SETTINGS = {
    "iAudioCacheSize": "16384",
    "iMaxSizeForCachedSound": "2048",
    "bMultiThreadAudio": "1",
    "bUseAudioDebugInformation": "0",
}

# Section where audio settings live in FNV INIs
AUDIO_SECTION = "[Audio]"


def _find_fnv_ini_dir():
    """Find the FNV user settings directory (My Games\\FalloutNV)."""
    docs = Path(os.path.expanduser("~")) / "Documents" / "My Games" / "FalloutNV"
    if docs.exists():
        return docs
    return None


def _create_backup(source_path, backup_root, base_dir, logger):
    """Backup a file preserving directory structure relative to base_dir."""
    try:
        rel = source_path.relative_to(base_dir)
    except ValueError:
        rel = Path(source_path.name)

    backup_path = backup_root / rel
    backup_path.parent.mkdir(parents=True, exist_ok=True)

    if not backup_path.exists():
        shutil.copy2(source_path, backup_path)
        logger.log(f"  Backed up: {rel}")
    return backup_path


def _patch_ini_content(content, settings):
    """Patch audio settings in INI content string.

    Returns (new_content, dict_of_changes) where dict maps
    setting name -> (old_value, new_value) for settings that changed.
    """
    patched = {}
    for key, value in settings.items():
        pattern = re.compile(
            rf"^(\s*{re.escape(key)}\s*=\s*)(.*)$",
            re.MULTILINE | re.IGNORECASE,
        )
        match = pattern.search(content)
        if match:
            old_val = match.group(2).strip()
            if old_val != value:
                content = pattern.sub(rf"\g<1>{value}", content)
                patched[key] = (old_val, value)
    return content, patched


def _patch_ini(ini_path, settings, logger, backup_root, base_dir, changes,
               dry_run):
    """Patch audio settings in a single INI file.

    Returns dict mapping setting names to (old_value, new_value) tuples
    for settings that were actually changed.
    """
    if not ini_path.exists():
        logger.log(f"    SKIP (not found): {ini_path}")
        return {}

    content = ini_path.read_text(encoding="utf-8", errors="replace")
    new_content, patched = _patch_ini_content(content, settings)

    for key, (old_val, new_val) in patched.items():
        logger.log(f"    {key}: {old_val} -> {new_val}")

    # Report settings already at target value
    for key, value in settings.items():
        if key not in patched:
            pattern = re.compile(
                rf"^\s*{re.escape(key)}\s*=",
                re.MULTILINE | re.IGNORECASE,
            )
            if pattern.search(content):
                logger.log(f"    {key}: already {value}")
            else:
                logger.log(f"    {key}: NOT FOUND in file")

    if not patched:
        logger.log(f"    No changes needed: {ini_path.name}")
        return patched

    if dry_run:
        logger.log(f"    [DRY RUN] Would patch: {ini_path.name}")
        return patched

    # Backup before modifying
    _create_backup(ini_path, backup_root, base_dir, logger)

    # Handle read-only files
    was_readonly = not os.access(ini_path, os.W_OK)
    if was_readonly:
        ini_path.chmod(ini_path.stat().st_mode | stat.S_IWRITE)

    ini_path.write_text(new_content, encoding="utf-8")

    if was_readonly:
        ini_path.chmod(ini_path.stat().st_mode & ~stat.S_IWRITE)

    changes.append({
        "type": "ini_patch",
        "file": str(ini_path),
        "backup": str(backup_root / ini_path.relative_to(base_dir)),
    })
    logger.log(f"    Patched: {ini_path.name}")
    return patched


def fix_audio_ini(game_data_dir, logger, backup_root, changes, dry_run=False):
    """Patch audio INI settings to prevent crackling.

    Applies the Viva New Vegas recommended audio settings to:
    - Fallout_default.ini (game root - source of defaults on launch)
    - Fallout.ini (user settings)
    - FalloutPrefs.ini (user prefs)

    Returns:
        Dict with keys: patched (count of files changed), skipped.
    """
    logger.log("=" * 60)
    logger.log("Patching audio INI settings")
    logger.log("=" * 60)
    logger.log("  Settings (Viva New Vegas recommended):")
    for k, v in AUDIO_SETTINGS.items():
        logger.log(f"    {k} = {v}")

    stats = {"patched": 0, "skipped": 0}
    game_root = game_data_dir.parent

    # 1) Fallout_default.ini in game root (overwrites Fallout.ini on launch)
    default_ini = game_root / "Fallout_default.ini"
    logger.log(f"\n  [Fallout_default.ini] {default_ini}")
    result = _patch_ini(default_ini, AUDIO_SETTINGS, logger, backup_root,
                        game_root, changes, dry_run)
    if result:
        stats["patched"] += 1
    else:
        stats["skipped"] += 1

    # 2) & 3) User INI files in Documents\My Games\FalloutNV
    ini_dir = _find_fnv_ini_dir()
    if ini_dir is None:
        logger.log("\n  Could not find FNV settings directory "
                   "(Documents\\My Games\\FalloutNV).", "WARN")
        stats["skipped"] += 2
    else:
        for ini_name in ("Fallout.ini", "FalloutPrefs.ini"):
            ini_path = ini_dir / ini_name
            logger.log(f"\n  [{ini_name}] {ini_path}")
            result = _patch_ini(ini_path, AUDIO_SETTINGS, logger,
                                backup_root, ini_dir, changes, dry_run)
            if result:
                stats["patched"] += 1
            else:
                stats["skipped"] += 1

    logger.log(f"\n  Done: {stats['patched']} patched, "
               f"{stats['skipped']} unchanged")
    return stats


def save_manifest(backup_root, changes, game_data_dir, logger):
    """Write a JSON manifest of all changes for rollback."""
    manifest = {
        "timestamp": datetime.now().isoformat(),
        "game_data_dir": str(game_data_dir),
        "changes": changes,
    }
    manifest_path = backup_root / "manifest.json"
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)
    logger.log(f"Manifest saved: {manifest_path}")


# ---- Rollback ---------------------------------------------------------------

def rollback(backup_dir, game_data_dir, logger):
    """Undo all changes using the most recent backup manifest.

    Returns:
        True on success, False if no backup found.
    """
    if not backup_dir.exists():
        logger.log("No backup directory found!", "ERROR")
        return False

    backups = sorted(
        [d for d in backup_dir.iterdir() if d.is_dir()], reverse=True
    )
    if not backups:
        logger.log("No backups found!", "ERROR")
        return False

    latest = backups[0]
    manifest_path = latest / "manifest.json"
    if not manifest_path.exists():
        logger.log(f"No manifest in {latest}", "ERROR")
        return False

    with open(manifest_path, "r", encoding="utf-8") as f:
        manifest = json.load(f)

    logger.log(f"Rolling back changes from {manifest['timestamp']}")
    restored = 0

    for change in manifest["changes"]:
        ctype = change["type"]

        if ctype == "ini_patch":
            ini_path = Path(change["file"])
            backup_path = Path(change["backup"])
            if backup_path.exists() and ini_path.exists():
                was_readonly = not os.access(ini_path, os.W_OK)
                if was_readonly:
                    ini_path.chmod(ini_path.stat().st_mode | stat.S_IWRITE)
                shutil.copy2(backup_path, ini_path)
                if was_readonly:
                    ini_path.chmod(ini_path.stat().st_mode & ~stat.S_IWRITE)
                restored += 1
                logger.log(f"  Restored: {ini_path.name}")

    logger.log(f"\nRollback complete: {restored} files restored")
    return True
