"""CLI entry point for fnv-audio-fix."""

import argparse
import sys
from datetime import datetime
from pathlib import Path

from . import __version__
from .fixer import (
    AUDIO_SETTINGS,
    fix_audio_ini,
    rollback,
    save_manifest,
)
from .game_path import find_game_data_dir
from .logger import Logger

BANNER = r"""
  _____ _   ___     __   _             _ _         _____ _
 |  ___| \ | \ \   / /  / \  _   _  __| (_) ___   |  ___(_)_  __
 | |_  |  \| |\ \ / /  / _ \| | | |/ _` | |/ _ \  | |_  | \ \/ /
 |  _| | |\  | \ V /  / ___ \ |_| | (_| | | (_) | |  _| | |>  <
 |_|   |_| \_|  \_/  /_/   \_\__,_|\__,_|_|\___/  |_|   |_/_/\_\

  Fallout: New Vegas Audio Crackling Fix  v{}
  Patches INI audio settings (Viva New Vegas recommended)
""".format(__version__)


def _build_parser():
    parser = argparse.ArgumentParser(
        prog="fnv-audio-fix",
        description=(
            "Fix audio crackling in Fallout: New Vegas by patching "
            "INI audio buffer settings (Viva New Vegas recommended fix)."
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
        logger.log("*** DRY RUN MODE - no files will be modified ***")

    # Show plan
    print(f"\nPlan:")
    print(f"  Patch audio INI settings to fix crackling:")
    for k, v in AUDIO_SETTINGS.items():
        print(f"    {k} = {v}")
    print(f"  Files: Fallout_default.ini, Fallout.ini, FalloutPrefs.ini")
    print(f"  Backups: {backup_root}")
    if args.dry_run:
        print("  *** DRY RUN - no changes will be made ***")
    print()

    if not args.yes and not args.dry_run:
        response = input("Proceed? [y/N] ").strip().lower()
        if response != "y":
            print("Aborted.")
            logger.close()
            sys.exit(0)

    # Run INI patching
    stats = fix_audio_ini(game_data_dir, logger, backup_root, changes,
                          args.dry_run)

    if not args.dry_run and changes:
        save_manifest(backup_root, changes, game_data_dir, logger)

    # Summary
    logger.log("\n" + "=" * 60)
    logger.log("SUMMARY")
    logger.log("=" * 60)
    logger.log(f"INI files patched: {stats['patched']}")
    logger.log(f"INI files unchanged: {stats['skipped']}")

    if changes:
        logger.log(f"\nBackup: {backup_root}")
    logger.log(f"Log:    {log_file}")
    logger.log("To undo: fnv-audio-fix --rollback")
    logger.log("\nDone! Launch the game and test the audio.")
    logger.close()


if __name__ == "__main__":
    main()
