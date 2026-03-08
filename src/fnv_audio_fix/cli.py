"""CLI entry point for fnv-audio-fix."""

import argparse
import sys
from datetime import datetime
from pathlib import Path

from . import __version__
from .converter import check_ffmpeg
from .fixer import (
    SOUND_BSA_NAMES,
    phase1_loose_mp3,
    phase2_bsa_ogg,
    rollback,
    save_manifest,
    should_skip_bsa,
)
from .bsa import read_bsa_file_list
from .game_path import find_game_data_dir
from .logger import Logger

BANNER = r"""
  _____ _   ___     __   _             _ _         _____ _
 |  ___| \ | \ \   / /  / \  _   _  __| (_) ___   |  ___(_)_  __
 | |_  |  \| |\ \ / /  / _ \| | | |/ _` | |/ _ \  | |_  | \ \/ /
 |  _| | |\  | \ V /  / ___ \ |_| | (_| | | (_) | |  _| | |>  <
 |_|   |_| \_|  \_/  /_/   \_\__,_|\__,_|_|\___/  |_|   |_/_/\_\

  Fallout: New Vegas Audio Crackling Fix  v{}
  Converts MP3/OGG -> 16-bit PCM WAV
""".format(__version__)


def _build_parser():
    parser = argparse.ArgumentParser(
        prog="fnv-audio-fix",
        description=(
            "Fix audio crackling in Fallout: New Vegas by converting "
            "MP3 and OGG audio files to 16-bit PCM WAV."
        ),
    )
    parser.add_argument(
        "--version", action="version", version=f"%(prog)s {__version__}"
    )
    parser.add_argument(
        "--game-dir",
        type=str,
        default=None,
        help=(
            "Path to the FNV installation (or its Data directory). "
            "Auto-detected from common Steam locations if omitted."
        ),
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview what would be changed without modifying any files.",
    )
    parser.add_argument(
        "--rollback",
        action="store_true",
        help="Undo all changes using the most recent backup.",
    )
    parser.add_argument(
        "-y", "--yes",
        action="store_true",
        help="Skip the confirmation prompt.",
    )
    return parser


def main(argv=None):
    """CLI entry point."""
    print(BANNER)
    parser = _build_parser()
    args = parser.parse_args(argv)

    # Locate game
    game_data_dir = find_game_data_dir(args.game_dir)
    if game_data_dir is None:
        print("ERROR: Could not find Fallout: New Vegas Data directory.")
        print("Use --game-dir to specify the path manually.")
        sys.exit(1)

    game_root = game_data_dir.parent
    backup_dir = game_root / "AudioFixBackup"
    log_file = game_root / "audio_fix_log.txt"

    # Handle rollback
    if args.rollback:
        logger = Logger(log_file)
        ok = rollback(backup_dir, game_data_dir, logger)
        logger.close()
        sys.exit(0 if ok else 1)

    # Verify FFmpeg
    if not check_ffmpeg():
        print("ERROR: FFmpeg not found in PATH!")
        print("Install it:  winget install Gyan.FFmpeg")
        print("Or download: https://www.gyan.dev/ffmpeg/builds/")
        sys.exit(1)

    # Prepare backup directory
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_root = backup_dir / timestamp
    if not args.dry_run:
        backup_root.mkdir(parents=True, exist_ok=True)

    logger = Logger(log_file)
    changes = []

    logger.log(f"Game Data: {game_data_dir}")
    logger.log(f"Backup:    {backup_root}")
    if args.dry_run:
        logger.log("*** DRY RUN MODE — no files will be modified ***")

    # Scan
    mp3_radio = (
        sorted((game_data_dir / "Sound").rglob("*.mp3"))
        if (game_data_dir / "Sound").exists()
        else []
    )
    mp3_music = (
        sorted((game_data_dir / "Music").rglob("*.mp3"))
        if (game_data_dir / "Music").exists()
        else []
    )
    bsa_files = sorted(game_data_dir.glob("*.bsa"))

    logger.log(f"\nFound:")
    logger.log(f"  {len(mp3_radio)} loose MP3 radio songs")
    logger.log(f"  {len(mp3_music)} loose MP3 music tracks")
    logger.log(f"  {len(bsa_files)} BSA archives")

    total_ogg_in_bsa = 0
    for bsa_path in bsa_files:
        skip = should_skip_bsa(bsa_path.name)
        is_sound = bsa_path.name in SOUND_BSA_NAMES
        file_list = (
            read_bsa_file_list(bsa_path) if (not skip and is_sound) else None
        )
        ogg = sum(
            1 for f in (file_list or []) if f["name"].lower().endswith(".ogg")
        )
        mp3 = sum(
            1 for f in (file_list or []) if f["name"].lower().endswith(".mp3")
        )
        audio_note = f" ({ogg} OGG, {mp3} MP3)" if ogg + mp3 > 0 else ""
        skip_note = (
            " [SKIP - mod audio]"
            if skip
            else (" [SKIP - not Sound BSA]" if not is_sound else "")
        )
        size_mb = bsa_path.stat().st_size / 1024 / 1024
        logger.log(
            f"    {bsa_path.name:45s} {size_mb:7.1f} MB{audio_note}{skip_note}"
        )
        if not skip and is_sound:
            total_ogg_in_bsa += ogg

    total_mp3 = len(mp3_radio) + len(mp3_music)

    print(f"\nPlan:")
    print(f"  Phase 1: Convert {total_mp3} loose MP3 files -> WAV")
    print(f"  Phase 2: Extract {total_ogg_in_bsa} OGG files from BSAs -> WAV")
    print(f"  Backups: {backup_root}")
    if args.dry_run:
        print("  *** DRY RUN — no changes will be made ***")
    print()

    if not args.yes:
        response = input("Proceed? [y/N] ").strip().lower()
        if response != "y":
            print("Aborted.")
            logger.close()
            sys.exit(0)

    # Run
    p1 = phase1_loose_mp3(game_data_dir, logger, backup_root, changes,
                           args.dry_run)
    p2 = phase2_bsa_ogg(game_data_dir, logger, backup_root, changes,
                          args.dry_run)

    if not args.dry_run and changes:
        save_manifest(backup_root, changes, game_data_dir, logger)

    # Summary
    logger.log("\n" + "=" * 60)
    logger.log("SUMMARY")
    logger.log("=" * 60)
    logger.log(f"Phase 1 (MP3 -> WAV): {p1['converted']} converted, "
               f"{p1['failed']} failed, {p1['skipped']} skipped")
    logger.log(f"Phase 2 (BSA OGG -> WAV): {p2['converted']} extracted, "
               f"{p2['failed']} failed, {p2['skipped']} skipped")
    logger.log(f"Total changes: {len(changes)}")

    total_failures = p1["failed"] + p2["failed"]
    if total_failures > 0:
        logger.log(
            f"\nWARNING: {total_failures} operations failed! Check log.",
            "WARN",
        )

    logger.log(f"\nBackup: {backup_root}")
    logger.log(f"Log:    {log_file}")
    logger.log("To undo: fnv-audio-fix --rollback")
    logger.log("Done! Launch the game and test the radio.")
    logger.close()


if __name__ == "__main__":
    main()
