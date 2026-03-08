"""Tests for CLI argument parsing and entry point."""

import sys
from unittest.mock import patch, MagicMock
from pathlib import Path

import pytest

from fnv_audio_fix.cli import _build_parser, main


class TestParser:
    def test_defaults(self):
        parser = _build_parser()
        args = parser.parse_args([])
        assert args.game_dir is None
        assert args.dry_run is False
        assert args.rollback is False
        assert args.yes is False

    def test_dry_run(self):
        parser = _build_parser()
        args = parser.parse_args(["--dry-run"])
        assert args.dry_run is True

    def test_rollback(self):
        parser = _build_parser()
        args = parser.parse_args(["--rollback"])
        assert args.rollback is True

    def test_game_dir(self):
        parser = _build_parser()
        args = parser.parse_args(["--game-dir", "C:\\Games\\FNV"])
        assert args.game_dir == "C:\\Games\\FNV"

    def test_yes_flag(self):
        parser = _build_parser()
        args = parser.parse_args(["-y"])
        assert args.yes is True


class TestMainErrors:
    @patch("fnv_audio_fix.cli.find_game_data_dir", return_value=None)
    def test_exit_if_no_game(self, mock_find):
        with pytest.raises(SystemExit) as exc_info:
            main(["--game-dir", "/nonexistent"])
        assert exc_info.value.code == 1

    @patch("fnv_audio_fix.cli.find_game_data_dir")
    @patch("fnv_audio_fix.cli.check_ffmpeg", return_value=False)
    def test_exit_if_no_ffmpeg(self, mock_ffmpeg, mock_find, tmp_path):
        data = tmp_path / "Data"
        data.mkdir()
        mock_find.return_value = data

        with pytest.raises(SystemExit) as exc_info:
            main(["--game-dir", str(tmp_path)])
        assert exc_info.value.code == 1
