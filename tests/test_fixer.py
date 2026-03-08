"""Tests for the fixer module (phases, rollback, manifest)."""

import json
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from fnv_audio_fix.fixer import (
    should_skip_bsa,
    save_manifest,
    phase1_loose_mp3,
    rollback,
    SOUND_BSA_NAMES,
)
from fnv_audio_fix.logger import Logger


class TestShouldSkipBsa:
    def test_skip_polish_voices(self):
        assert should_skip_bsa("Voices_pl.bsa") is True

    def test_skip_voxalter(self):
        assert should_skip_bsa("Voxalter_dub.bsa") is True

    def test_no_skip_sound(self):
        assert should_skip_bsa("Fallout - Sound.bsa") is False

    def test_case_insensitive(self):
        assert should_skip_bsa("VOICES_PL.BSA") is True


class TestSaveManifest:
    def test_writes_json(self, tmp_path):
        backup_root = tmp_path / "backup"
        backup_root.mkdir()
        logger = Logger()
        changes = [{"type": "mp3_to_wav", "original": "test.mp3"}]

        save_manifest(backup_root, changes, tmp_path, logger)

        manifest_path = backup_root / "manifest.json"
        assert manifest_path.exists()
        data = json.loads(manifest_path.read_text(encoding="utf-8"))
        assert data["changes"] == changes
        assert "timestamp" in data


class TestPhase1DryRun:
    def test_dry_run_counts_mp3(self, tmp_path):
        """Dry run should count MP3 files without converting them."""
        data_dir = tmp_path / "Data"
        music = data_dir / "Music"
        music.mkdir(parents=True)

        # Create fake MP3 files
        (music / "song1.mp3").write_bytes(b"fake mp3 1")
        (music / "song2.mp3").write_bytes(b"fake mp3 2")

        logger = Logger()
        changes = []
        backup = tmp_path / "backup"

        stats = phase1_loose_mp3(data_dir, logger, backup, changes,
                                  dry_run=True)

        assert stats["converted"] == 2
        assert stats["failed"] == 0
        # Original files should still exist
        assert (music / "song1.mp3").exists()
        assert (music / "song2.mp3").exists()

    def test_skips_already_converted(self, tmp_path):
        data_dir = tmp_path / "Data"
        music = data_dir / "Music"
        music.mkdir(parents=True)

        # File with RIFF header = already converted to WAV content
        (music / "song.mp3").write_bytes(b"RIFF" + b"\x00" * 40)

        logger = Logger()
        stats = phase1_loose_mp3(data_dir, logger, tmp_path, [],
                                  dry_run=True)
        assert stats["skipped"] == 1
        assert stats["converted"] == 0


class TestRollback:
    def test_rollback_mp3_rewrite(self, tmp_path):
        """Rollback should restore original MP3 content from backup."""
        data_dir = tmp_path / "game" / "Data"
        data_dir.mkdir(parents=True)
        backup_dir = tmp_path / "backup"
        ts_dir = backup_dir / "20260101_120000"
        ts_dir.mkdir(parents=True)

        # Simulate: original MP3 was backed up, file now has WAV content
        mp3_file = data_dir / "Music" / "song.mp3"
        mp3_file.parent.mkdir(parents=True)
        mp3_file.write_bytes(b"RIFF wav content")

        mp3_backup = ts_dir / "song.mp3"
        mp3_backup.write_bytes(b"original mp3")

        manifest = {
            "timestamp": "2026-01-01T12:00:00",
            "game_data_dir": str(data_dir),
            "changes": [
                {
                    "type": "mp3_rewrite",
                    "file": str(mp3_file),
                    "backup": str(mp3_backup),
                }
            ],
        }
        (ts_dir / "manifest.json").write_text(
            json.dumps(manifest), encoding="utf-8"
        )

        logger = Logger()
        ok = rollback(backup_dir, data_dir, logger)

        assert ok is True
        assert mp3_file.exists()
        assert mp3_file.read_bytes() == b"original mp3"

    def test_rollback_legacy_mp3_to_wav(self, tmp_path):
        """Rollback should handle legacy v1 manifest format."""
        data_dir = tmp_path / "game" / "Data"
        data_dir.mkdir(parents=True)
        backup_dir = tmp_path / "backup"
        ts_dir = backup_dir / "20260101_120000"
        ts_dir.mkdir(parents=True)

        wav_file = data_dir / "Music" / "song.wav"
        wav_file.parent.mkdir(parents=True)
        wav_file.write_bytes(b"wav data")

        mp3_backup = ts_dir / "song.mp3"
        mp3_backup.write_bytes(b"original mp3")
        mp3_original = data_dir / "Music" / "song.mp3"

        manifest = {
            "timestamp": "2026-01-01T12:00:00",
            "game_data_dir": str(data_dir),
            "changes": [
                {
                    "type": "mp3_to_wav",
                    "original": str(mp3_original),
                    "new_file": str(wav_file),
                    "backup": str(mp3_backup),
                }
            ],
        }
        (ts_dir / "manifest.json").write_text(
            json.dumps(manifest), encoding="utf-8"
        )

        logger = Logger()
        ok = rollback(backup_dir, data_dir, logger)

        assert ok is True
        assert not wav_file.exists()
        assert mp3_original.exists()
        assert mp3_original.read_bytes() == b"original mp3"

    def test_rollback_no_backup(self, tmp_path):
        logger = Logger()
        ok = rollback(tmp_path / "nonexistent", tmp_path, logger)
        assert ok is False
