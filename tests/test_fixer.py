"""Tests for the fixer module (INI patching, rollback, manifest)."""

import json
import os
import stat
from pathlib import Path

import pytest

from fnv_audio_fix.fixer import (
    AUDIO_SETTINGS,
    _patch_ini_content,
    fix_audio_ini,
    save_manifest,
    rollback,
)
from fnv_audio_fix.logger import Logger


class TestPatchIniContent:
    def test_patches_existing_settings(self):
        content = "[Audio]\niAudioCacheSize=2048\nbMultiThreadAudio=0\n"
        new_content, changed = _patch_ini_content(content, AUDIO_SETTINGS)
        assert "iAudioCacheSize=16384" in new_content
        assert "bMultiThreadAudio=1" in new_content
        assert "iAudioCacheSize" in changed
        assert changed["iAudioCacheSize"] == ("2048", "16384")

    def test_no_change_if_already_correct(self):
        content = (
            "[Audio]\n"
            "iAudioCacheSize=16384\n"
            "iMaxSizeForCachedSound=2048\n"
            "bMultiThreadAudio=1\n"
            "bUseAudioDebugInformation=0\n"
        )
        new_content, changed = _patch_ini_content(content, AUDIO_SETTINGS)
        assert changed == {}
        assert new_content == content

    def test_case_insensitive_key(self):
        content = "[Audio]\nIAUDIOCACHESIZE=1024\n"
        new_content, changed = _patch_ini_content(
            content, {"iAudioCacheSize": "16384"}
        )
        assert "IAUDIOCACHESIZE=16384" in new_content
        assert "iAudioCacheSize" in changed

    def test_preserves_other_settings(self):
        content = (
            "[Audio]\n"
            "iAudioCacheSize=2048\n"
            "fSomethingElse=1.5\n"
        )
        new_content, changed = _patch_ini_content(
            content, {"iAudioCacheSize": "16384"}
        )
        assert "fSomethingElse=1.5" in new_content


class TestSaveManifest:
    def test_writes_json(self, tmp_path):
        backup_root = tmp_path / "backup"
        backup_root.mkdir()
        logger = Logger()
        changes = [{"type": "ini_patch", "file": "test.ini"}]

        save_manifest(backup_root, changes, tmp_path, logger)

        manifest_path = backup_root / "manifest.json"
        assert manifest_path.exists()
        data = json.loads(manifest_path.read_text(encoding="utf-8"))
        assert data["changes"] == changes
        assert "timestamp" in data


class TestFixAudioIni:
    def test_patches_default_ini(self, tmp_path):
        """Should patch Fallout_default.ini in game root."""
        data_dir = tmp_path / "Data"
        data_dir.mkdir()

        default_ini = tmp_path / "Fallout_default.ini"
        default_ini.write_text(
            "[Audio]\niAudioCacheSize=2048\nbMultiThreadAudio=0\n"
            "bUseAudioDebugInformation=1\niMaxSizeForCachedSound=256\n",
            encoding="utf-8",
        )

        backup = tmp_path / "backup"
        backup.mkdir()
        logger = Logger()
        changes = []

        stats = fix_audio_ini(data_dir, logger, backup, changes)

        content = default_ini.read_text(encoding="utf-8")
        assert "iAudioCacheSize=16384" in content
        assert "bMultiThreadAudio=1" in content
        assert stats["patched"] >= 1

    def test_dry_run_no_changes(self, tmp_path):
        """Dry run should not modify files."""
        data_dir = tmp_path / "Data"
        data_dir.mkdir()

        default_ini = tmp_path / "Fallout_default.ini"
        original = "[Audio]\niAudioCacheSize=2048\n"
        default_ini.write_text(original, encoding="utf-8")

        backup = tmp_path / "backup"
        logger = Logger()
        changes = []

        fix_audio_ini(data_dir, logger, backup, changes, dry_run=True)

        assert default_ini.read_text(encoding="utf-8") == original
        assert len(changes) == 0

    def test_handles_readonly_ini(self, tmp_path):
        """Should handle read-only INI files."""
        data_dir = tmp_path / "Data"
        data_dir.mkdir()

        default_ini = tmp_path / "Fallout_default.ini"
        default_ini.write_text(
            "[Audio]\niAudioCacheSize=2048\n", encoding="utf-8"
        )
        # Make read-only
        default_ini.chmod(default_ini.stat().st_mode & ~stat.S_IWRITE)

        backup = tmp_path / "backup"
        backup.mkdir()
        logger = Logger()
        changes = []

        stats = fix_audio_ini(data_dir, logger, backup, changes)

        content = default_ini.read_text(encoding="utf-8")
        assert "iAudioCacheSize=16384" in content
        assert stats["patched"] >= 1

    def test_skips_missing_ini(self, tmp_path):
        """Should skip non-existent INI files without error."""
        data_dir = tmp_path / "Data"
        data_dir.mkdir()
        # No Fallout_default.ini exists

        backup = tmp_path / "backup"
        logger = Logger()
        changes = []

        stats = fix_audio_ini(data_dir, logger, backup, changes)
        assert stats["skipped"] >= 1


class TestRollback:
    def test_rollback_restores_ini(self, tmp_path):
        """Rollback should restore original INI from backup."""
        data_dir = tmp_path / "game" / "Data"
        data_dir.mkdir(parents=True)
        backup_dir = tmp_path / "backup"
        ts_dir = backup_dir / "20260101_120000"
        ts_dir.mkdir(parents=True)

        ini_file = tmp_path / "game" / "Fallout_default.ini"
        ini_file.write_text("patched content", encoding="utf-8")

        ini_backup = ts_dir / "Fallout_default.ini"
        ini_backup.write_text("original content", encoding="utf-8")

        manifest = {
            "timestamp": "2026-01-01T12:00:00",
            "game_data_dir": str(data_dir),
            "changes": [
                {
                    "type": "ini_patch",
                    "file": str(ini_file),
                    "backup": str(ini_backup),
                }
            ],
        }
        (ts_dir / "manifest.json").write_text(
            json.dumps(manifest), encoding="utf-8"
        )

        logger = Logger()
        ok = rollback(backup_dir, data_dir, logger)

        assert ok is True
        assert ini_file.read_text(encoding="utf-8") == "original content"

    def test_rollback_no_backup(self, tmp_path):
        logger = Logger()
        ok = rollback(tmp_path / "nonexistent", tmp_path, logger)
        assert ok is False

    def test_rollback_no_manifest(self, tmp_path):
        backup_dir = tmp_path / "backup"
        ts_dir = backup_dir / "20260101_120000"
        ts_dir.mkdir(parents=True)

        logger = Logger()
        ok = rollback(backup_dir, tmp_path, logger)
        assert ok is False
