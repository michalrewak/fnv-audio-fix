"""Core fix logic: Phase 1 (loose MP3) and Phase 2 (BSA OGG extraction)."""

import os
import shutil
import json
from pathlib import Path
from datetime import datetime

from .bsa import read_bsa_file_list, extract_file_from_bsa
from .converter import convert_audio_file, convert_audio_bytes

# FNV requires 16-bit PCM WAV at 44100 Hz
WAV_SAMPLE_RATE = 44100

# BSA files to skip (e.g. Polish dubbing mods — already correct format)
SKIP_BSA_PATTERNS = ["Voices_pl", "Voxalter"]

# Only extract audio from dedicated Sound BSAs
SOUND_BSA_NAMES = {
    "Fallout - Sound.bsa",
    "DeadMoney - Sounds.bsa",
    "HonestHearts - Sounds.bsa",
    "LonesomeRoad - Sounds.bsa",
    "OldWorldBlues - Sounds.bsa",
    "GunRunnersArsenal - Sounds.bsa",
}


def should_skip_bsa(bsa_name):
    """Return True if this BSA should be left untouched."""
    for pattern in SKIP_BSA_PATTERNS:
        if pattern.lower() in bsa_name.lower():
            return True
    return False


def _create_backup(source_path, backup_root, game_data_dir, logger):
    """Backup a file preserving directory structure relative to game root."""
    try:
        rel = source_path.relative_to(game_data_dir.parent)
    except ValueError:
        rel = Path(source_path.name)

    backup_path = backup_root / rel
    backup_path.parent.mkdir(parents=True, exist_ok=True)

    if not backup_path.exists():
        shutil.copy2(source_path, backup_path)
        logger.log(f"  Backed up: {rel}")
    return backup_path


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


# ---- Phase 1 ---------------------------------------------------------------

def phase1_loose_mp3(game_data_dir, logger, backup_root, changes,
                     dry_run=False):
    """Convert loose MP3 files (radio songs, music) to 16-bit PCM WAV.

    Returns:
        Dict with keys: converted, failed, skipped.
    """
    logger.log("=" * 60)
    logger.log("PHASE 1: Converting loose MP3 files to WAV")
    logger.log("=" * 60)

    search_dirs = []
    radio_dir = game_data_dir / "Sound" / "songs" / "radionv"
    music_dir = game_data_dir / "Music"

    if radio_dir.exists():
        search_dirs.append(("Radio songs", radio_dir))
    if music_dir.exists():
        search_dirs.append(("Music tracks", music_dir))

    stats = {"converted": 0, "failed": 0, "skipped": 0}

    for label, search_dir in search_dirs:
        mp3_files = sorted(search_dir.rglob("*.mp3"))
        logger.log(
            f"\n  [{label}] Found {len(mp3_files)} MP3 files in "
            f"{search_dir.relative_to(game_data_dir)}"
        )

        for mp3_path in mp3_files:
            rel_path = mp3_path.relative_to(game_data_dir)
            wav_path = mp3_path.with_suffix(".wav")

            if wav_path.exists():
                logger.log(f"    SKIP (WAV exists): {rel_path}")
                stats["skipped"] += 1
                continue

            if dry_run:
                logger.log(f"    [DRY RUN] Would convert: {rel_path}")
                stats["converted"] += 1
                continue

            _create_backup(mp3_path, backup_root, game_data_dir, logger)

            logger.log(f"    Converting: {rel_path}")
            if convert_audio_file(mp3_path, wav_path, WAV_SAMPLE_RATE, logger):
                wav_size = wav_path.stat().st_size
                mp3_size = mp3_path.stat().st_size
                logger.log(
                    f"    OK: {mp3_path.name} -> .wav "
                    f"({mp3_size // 1024}KB -> {wav_size // 1024}KB)"
                )
                mp3_path.unlink()
                stats["converted"] += 1
                changes.append(
                    {
                        "type": "mp3_to_wav",
                        "original": str(mp3_path),
                        "new_file": str(wav_path),
                        "backup": str(
                            backup_root
                            / mp3_path.relative_to(game_data_dir.parent)
                        ),
                    }
                )
            else:
                stats["failed"] += 1
                logger.log(f"    FAILED: {rel_path}", "ERROR")

    logger.log(
        f"\n  Phase 1 done: {stats['converted']} converted, "
        f"{stats['failed']} failed, {stats['skipped']} skipped"
    )
    return stats


# ---- Phase 2 ---------------------------------------------------------------

def phase2_bsa_ogg(game_data_dir, logger, backup_root, changes,
                   dry_run=False):
    """Extract OGG/MP3 from Sound BSAs as loose WAV files.

    Loose files override BSA contents so the original BSA stays intact.

    Returns:
        Dict with keys: converted, failed, skipped, bsa_processed.
    """
    logger.log("\n" + "=" * 60)
    logger.log("PHASE 2: Extracting OGG from BSAs as loose WAV files")
    logger.log("=" * 60)

    bsa_files = sorted(game_data_dir.glob("*.bsa"))
    stats = {"converted": 0, "failed": 0, "skipped": 0, "bsa_processed": 0}

    for bsa_path in bsa_files:
        bsa_name = bsa_path.name

        if should_skip_bsa(bsa_name):
            logger.log(f"\n  SKIP (mod audio): {bsa_name}")
            continue

        if bsa_name not in SOUND_BSA_NAMES:
            logger.log(f"\n  SKIP (not a Sound BSA): {bsa_name}")
            continue

        file_list = read_bsa_file_list(bsa_path)
        if file_list is None:
            logger.log(f"\n  SKIP (invalid BSA): {bsa_name}", "WARN")
            continue

        audio_files = [
            f
            for f in file_list
            if f["name"].lower().endswith((".ogg", ".mp3"))
        ]
        if not audio_files:
            continue

        ogg_count = sum(
            1 for f in audio_files if f["name"].lower().endswith(".ogg")
        )
        mp3_count = sum(
            1 for f in audio_files if f["name"].lower().endswith(".mp3")
        )

        logger.log(
            f"\n  {bsa_name}: {ogg_count} OGG + {mp3_count} MP3 to extract"
        )
        stats["bsa_processed"] += 1

        for file_rec in audio_files:
            ext = os.path.splitext(file_rec["name"])[1].lower()
            wav_name = os.path.splitext(file_rec["name"])[0] + ".wav"
            folder_path = file_rec["folder"].replace("\\", os.sep)
            loose_dir = game_data_dir / folder_path
            wav_path = loose_dir / wav_name
            rel_display = file_rec["folder"] + "\\" + file_rec["name"]

            if wav_path.exists():
                stats["skipped"] += 1
                continue

            if dry_run:
                logger.log(
                    f"    [DRY RUN] Would extract: {rel_display} -> {wav_name}"
                )
                stats["converted"] += 1
                continue

            try:
                raw_data = extract_file_from_bsa(bsa_path, file_rec)
            except Exception as e:
                logger.log(
                    f"    FAILED to extract {rel_display}: {e}", "ERROR"
                )
                stats["failed"] += 1
                continue

            input_format = "ogg" if ext == ".ogg" else "mp3"
            wav_data = convert_audio_bytes(
                raw_data, input_format, WAV_SAMPLE_RATE, logger, rel_display
            )
            if wav_data is None:
                stats["failed"] += 1
                continue

            loose_dir.mkdir(parents=True, exist_ok=True)
            with open(wav_path, "wb") as f:
                f.write(wav_data)

            stats["converted"] += 1
            logger.log(
                f"    OK: {rel_display} -> loose WAV ({len(wav_data) // 1024}KB)"
            )
            changes.append(
                {
                    "type": "bsa_extract_wav",
                    "bsa": bsa_name,
                    "bsa_path": rel_display,
                    "extracted_to": str(wav_path),
                }
            )

    logger.log(
        f"\n  Phase 2 done: {stats['bsa_processed']} BSAs, "
        f"{stats['converted']} extracted, {stats['failed']} failed, "
        f"{stats['skipped']} skipped"
    )
    return stats


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
    removed = 0

    for change in manifest["changes"]:
        if change["type"] == "mp3_to_wav":
            wav_path = Path(change["new_file"])
            if wav_path.exists():
                wav_path.unlink()
                removed += 1

            backup_path = Path(change["backup"])
            original_path = Path(change["original"])
            if backup_path.exists():
                original_path.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(backup_path, original_path)
                restored += 1
                logger.log(f"  Restored: {original_path.name}")

        elif change["type"] == "bsa_extract_wav":
            extracted = Path(change["extracted_to"])
            if extracted.exists():
                extracted.unlink()
                removed += 1
                logger.log(f"  Removed: {extracted.name}")

            # Clean up empty directories
            try:
                parent = extracted.parent
                while parent != game_data_dir and not any(parent.iterdir()):
                    parent.rmdir()
                    parent = parent.parent
            except (OSError, StopIteration):
                pass

    logger.log(
        f"\nRollback complete: {restored} files restored, {removed} files removed"
    )
    return True
