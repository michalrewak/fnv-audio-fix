"""Tests for game path detection."""

import sys
from pathlib import Path
from unittest.mock import patch

import pytest

from fnv_audio_fix.game_path import find_game_data_dir


class TestFindGameDataDir:
    def test_custom_path_data_dir(self, tmp_path):
        data = tmp_path / "Data"
        data.mkdir()
        result = find_game_data_dir(str(data))
        assert result == data

    def test_custom_path_game_root(self, tmp_path):
        data = tmp_path / "Data"
        data.mkdir()
        result = find_game_data_dir(str(tmp_path))
        assert result == data

    def test_custom_path_invalid(self, tmp_path):
        result = find_game_data_dir(str(tmp_path / "nonexistent"))
        assert result is None

    def test_auto_detect_steam(self, tmp_path):
        steam = tmp_path / "Steam" / "steamapps" / "common"
        data = steam / "Fallout New Vegas" / "Data"
        data.mkdir(parents=True)

        with patch(
            "fnv_audio_fix.game_path._STEAM_COMMON",
            [str(steam)],
        ):
            result = find_game_data_dir()
            assert result == data

    def test_no_game_found(self):
        with patch("fnv_audio_fix.game_path._STEAM_COMMON", []):
            with patch("fnv_audio_fix.game_path._find_via_registry", return_value=None):
                result = find_game_data_dir()
                assert result is None
