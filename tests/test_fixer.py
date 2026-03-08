"""Tests for the fixer module (phases, rollback, manifest)."""

import json
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from fnv_audio_fix.fixer import (
    should_skip_bsa,
    save_manifest,
    phase1_loose_mp3,
    phase3_patch_ini,
    _patch_ini_file,
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

    def test_skips_existing_wav(self, tmp_path):
        data_dir = tmp_path / "Data"
        music = data_dir / "Music"
        music.mkdir(parents=True)

        (music / "song.mp3").write_bytes(b"fake mp3")
        (music / "song.wav").write_bytes(b"fake wav")

        logger = Logger()
        stats = phase1_loose_mp3(data_dir, logger, tmp_path, [],
                                  dry_run=True)
        assert stats["skipped"] == 1
        assert stats["converted"] == 0


class TestRollback:
    def test_rollback_mp3(self, tmp_path):
        """Rollback should restore MP3 and remove WAV."""
        data_dir = tmp_path / "game" / "Data"
        data_dir.mkdir(parents=True)
        backup_dir = tmp_path / "backup"
        ts_dir = backup_dir / "20260101_120000"
        ts_dir.mkdir(parents=True)

        # Simulate: original MP3 was backed up, WAV was created
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


class TestPatchIniFile:
    SAMPLE_INI = (
        "[General]\r\n"
        "sEssentialFileCacheList=Data\\Fallout.esm, Data\\Music\\Special\\"
        "MainTitle.mp3, Data\\Fallout - Sound.bsa\r\n"
        "sUnessentialFileCacheList=Data\\Music\\Base\\*.mp3, "
        "Data\\Music\\Battle\\*.mp3, Data\\Music\\Explore\\*.mp3\r\n"
        "[Display]\r\n"
        "iSize W=1920\r\n"
        "SMainMenuMusicTrack=special\\maintitle.mp3\r\n"
        "[Audio]\r\n"
        "SFileTypeSource=wav\r\n"
    )

    def test_patches_mp3_to_wav(self, tmp_path):
        ini_path = tmp_path / "Fallout.ini"
        ini_path.write_text(self.SAMPLE_INI, encoding="utf-8")

        logger = Logger()
        backup_root = tmp_path / "backup"
        backup_root.mkdir()
        changes = []

        result = _patch_ini_file(ini_path, logger, backup_root, changes,
                                  dry_run=False)

        assert result is True
        content = ini_path.read_text(encoding="utf-8")
        assert "MainTitle.wav" in content
        assert "maintitle.wav" in content
        assert "*.wav" in content
        # Ensure non-music .mp3 references remain unchanged
        assert "SFileTypeSource=wav" in content
        # Should not contain .mp3 in music lines
        assert "MainTitle.mp3" not in content
        assert "maintitle.mp3" not in content
        assert len(changes) == 1
        assert changes[0]["type"] == "ini_patch"

    def test_dry_run_no_writes(self, tmp_path):
        ini_path = tmp_path / "Fallout.ini"
        ini_path.write_text(self.SAMPLE_INI, encoding="utf-8")
        original_bytes = ini_path.read_bytes()

        logger = Logger()
        changes = []

        result = _patch_ini_file(ini_path, logger, tmp_path, changes,
                                  dry_run=True)

        assert result is True
        # File should be unchanged (compare raw bytes)
        assert ini_path.read_bytes() == original_bytes
        assert len(changes) == 0

    def test_no_changes_needed(self, tmp_path):
        ini_path = tmp_path / "clean.ini"
        ini_path.write_text(
            "[Audio]\r\nSMainMenuMusicTrack=special\\maintitle.wav\r\n",
            encoding="utf-8",
        )

        logger = Logger()
        result = _patch_ini_file(ini_path, logger, tmp_path, [], dry_run=False)
        assert result is False

    def test_handles_readonly(self, tmp_path):
        import stat
        ini_path = tmp_path / "Fallout.ini"
        ini_path.write_text(self.SAMPLE_INI, encoding="utf-8")
        ini_path.chmod(ini_path.stat().st_mode & ~stat.S_IWRITE)

        logger = Logger()
        backup_root = tmp_path / "backup"
        backup_root.mkdir()
        changes = []

        result = _patch_ini_file(ini_path, logger, backup_root, changes,
                                  dry_run=False)
        assert result is True
        assert "maintitle.wav" in ini_path.read_text(encoding="utf-8")


class TestPhase3PatchIni:
    def test_phase3_finds_and_patches(self, tmp_path):
        ini_dir = tmp_path / "Documents" / "My Games" / "FalloutNV"
        ini_dir.mkdir(parents=True)
        ini_content = (
            "SMainMenuMusicTrack=special\\maintitle.mp3\r\n"
            "sEssentialFileCacheList=Data\\Music\\Special\\MainTitle.mp3\r\n"
        )
        (ini_dir / "Fallout.ini").write_text(ini_content, encoding="utf-8")
        (ini_dir / "FalloutPrefs.ini").write_text(ini_content, encoding="utf-8")

        logger = Logger()
        backup_root = tmp_path / "backup"
        backup_root.mkdir()
        changes = []

        with patch("fnv_audio_fix.fixer._find_fnv_ini_dir",
                    return_value=ini_dir):
            stats = phase3_patch_ini(logger, backup_root, changes,
                                      dry_run=False)

        assert stats["patched"] == 2
        assert stats["skipped"] == 0
        assert len(changes) == 2

    def test_phase3_no_ini_dir(self):
        logger = Logger()
        with patch("fnv_audio_fix.fixer._find_fnv_ini_dir",
                    return_value=None):
            stats = phase3_patch_ini(logger, Path("/fake"), [], dry_run=False)

        assert stats["skipped"] == 1
