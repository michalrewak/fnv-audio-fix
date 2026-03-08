"""Tests for audio converter functions."""

import subprocess
from unittest.mock import patch, MagicMock
from pathlib import Path

import pytest

from fnv_audio_fix.converter import (
    check_ffmpeg,
    convert_audio_file,
    convert_audio_bytes,
)


class TestCheckFfmpeg:
    @patch("fnv_audio_fix.converter.subprocess.run")
    def test_ffmpeg_available(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0)
        assert check_ffmpeg() is True

    @patch("fnv_audio_fix.converter.subprocess.run", side_effect=FileNotFoundError)
    def test_ffmpeg_not_found(self, mock_run):
        assert check_ffmpeg() is False

    @patch(
        "fnv_audio_fix.converter.subprocess.run",
        side_effect=subprocess.TimeoutExpired(cmd="ffmpeg", timeout=10),
    )
    def test_ffmpeg_timeout(self, mock_run):
        assert check_ffmpeg() is False


class TestConvertAudioFile:
    @patch("fnv_audio_fix.converter.subprocess.run")
    def test_success(self, mock_run, tmp_path):
        src = tmp_path / "test.mp3"
        dst = tmp_path / "test.wav"
        src.write_bytes(b"fake mp3")
        dst.write_bytes(b"RIFF" + b"\x00" * 40)  # fake WAV

        mock_run.return_value = MagicMock(returncode=0)
        result = convert_audio_file(src, dst)
        assert result is True

    @patch("fnv_audio_fix.converter.subprocess.run")
    def test_ffmpeg_error(self, mock_run, tmp_path):
        src = tmp_path / "test.mp3"
        dst = tmp_path / "test.wav"
        src.write_bytes(b"fake mp3")

        mock_run.return_value = MagicMock(returncode=1, stderr="Error")
        result = convert_audio_file(src, dst)
        assert result is False

    @patch(
        "fnv_audio_fix.converter.subprocess.run",
        side_effect=subprocess.TimeoutExpired(cmd="ffmpeg", timeout=120),
    )
    def test_timeout(self, mock_run, tmp_path):
        src = tmp_path / "test.mp3"
        dst = tmp_path / "test.wav"
        src.write_bytes(b"fake mp3")

        result = convert_audio_file(src, dst)
        assert result is False


class TestConvertAudioBytes:
    @patch("fnv_audio_fix.converter.subprocess.run")
    def test_success(self, mock_run):
        wav_header = b"RIFF" + b"\x00" * 40
        mock_run.return_value = MagicMock(returncode=0, stdout=wav_header)
        result = convert_audio_bytes(b"ogg data", "ogg")
        assert result == wav_header

    @patch("fnv_audio_fix.converter.subprocess.run")
    def test_failure(self, mock_run):
        mock_run.return_value = MagicMock(
            returncode=1, stderr=b"Error decoding"
        )
        result = convert_audio_bytes(b"bad data", "ogg")
        assert result is None

    @patch("fnv_audio_fix.converter.subprocess.run")
    def test_too_small_output(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0, stdout=b"tiny")
        result = convert_audio_bytes(b"ogg data", "ogg")
        assert result is None
