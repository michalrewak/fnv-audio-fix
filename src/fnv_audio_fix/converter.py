"""Audio conversion using FFmpeg."""

import subprocess


def check_ffmpeg():
    """Return True if FFmpeg is available in PATH."""
    try:
        result = subprocess.run(
            ["ffmpeg", "-version"], capture_output=True, text=True, timeout=10
        )
        return result.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


def convert_audio_file(input_path, output_path, sample_rate=44100, logger=None):
    """Convert an audio file on disk to 16-bit PCM WAV.

    Args:
        input_path: Source audio file path (MP3, OGG, etc.).
        output_path: Destination .wav path.
        sample_rate: Output sample rate (default 44100).
        logger: Optional Logger instance.

    Returns:
        True on success, False on failure.
    """
    try:
        cmd = [
            "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
            "-i", str(input_path),
            "-acodec", "pcm_s16le",
            "-ar", str(sample_rate),
            str(output_path),
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        if result.returncode != 0:
            if logger:
                logger.log(
                    f"  FFmpeg error: {result.stderr.strip()[:300]}", "ERROR"
                )
            return False
        return output_path.exists() and output_path.stat().st_size > 0
    except subprocess.TimeoutExpired:
        if logger:
            logger.log(f"  FFmpeg timeout for {input_path.name}", "ERROR")
        return False
    except Exception as e:
        if logger:
            logger.log(f"  Error: {e}", "ERROR")
        return False


def convert_audio_bytes(data, input_format, sample_rate=44100, logger=None,
                        filename=""):
    """Convert raw audio bytes to WAV bytes via FFmpeg pipes.

    Args:
        data: Raw audio bytes (MP3 or OGG).
        input_format: FFmpeg input format name ("mp3" or "ogg").
        sample_rate: Output sample rate (default 44100).
        logger: Optional Logger instance.
        filename: Display name for log messages.

    Returns:
        WAV bytes on success, None on failure.
    """
    try:
        cmd = [
            "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
            "-f", input_format, "-i", "pipe:0",
            "-acodec", "pcm_s16le",
            "-ar", str(sample_rate),
            "-f", "wav", "pipe:1",
        ]
        result = subprocess.run(cmd, input=data, capture_output=True, timeout=60)
        if result.returncode != 0:
            stderr = result.stderr.decode("utf-8", errors="replace").strip()[:300]
            if logger:
                logger.log(f"  FFmpeg error for {filename}: {stderr}", "ERROR")
            return None
        if len(result.stdout) < 44:  # minimum WAV header size
            return None
        return result.stdout
    except Exception as e:
        if logger:
            logger.log(f"  Error converting {filename}: {e}", "ERROR")
        return None
