# FNV Audio Fix

**Fix audio crackling in Fallout: New Vegas** by converting MP3/OGG files to 16-bit PCM WAV.

Works with modded games — safely skips Polish dubbing and other voice mods.

## The Problem

Fallout: New Vegas's audio engine (DirectSound) has well-known issues:

- **MP3 files** cause crackling/popping, especially on radio stations and the main menu
- **OGG Vorbis** sound effects inside BSA archives can cause stuttering
- This affects both vanilla and modded installations

Based on the same approach as [FNV BSA Decompressor](https://www.nexusmods.com/newvegas/mods/65854),
but works reliably with heavily modded games where that tool may fail.

## What It Does

| Phase | Action | Files |
|-------|--------|-------|
| **1** | Converts loose MP3 files (radio songs, music) to WAV | `Data/Sound/songs/`, `Data/Music/` |
| **2** | Extracts OGG from Sound BSAs as loose WAV files | `Fallout - Sound.bsa`, DLC Sound BSAs |

- Creates timestamped **backups** of all original files
- **Rollback** support to undo everything in one command
- **Dry-run** mode to preview changes
- Skips voice/mod BSAs (Voxalter, Voices_pl, etc.)

## Requirements

- **Python 3.8+** — [python.org/downloads](https://www.python.org/downloads/)
- **FFmpeg** — install with `winget install Gyan.FFmpeg` or download from [gyan.dev](https://www.gyan.dev/ffmpeg/builds/)

## Installation

```bash
pip install fnv-audio-fix
```

Or install from source:

```bash
git clone https://github.com/mikemadest/fnv-audio-fix.git
cd fnv-audio-fix
pip install .
```

## Usage

### Fix audio (auto-detects game location)

```bash
fnv-audio-fix
```

### Specify game directory manually

```bash
fnv-audio-fix --game-dir "D:\Steam\steamapps\common\Fallout New Vegas"
```

### Preview changes without modifying anything

```bash
fnv-audio-fix --dry-run
```

### Undo all changes

```bash
fnv-audio-fix --rollback
```

### Skip confirmation prompt

```bash
fnv-audio-fix -y
```

## Options

| Option | Description |
|--------|-------------|
| `--game-dir PATH` | Path to FNV install directory (auto-detected if omitted) |
| `--dry-run` | Preview changes without modifying files |
| `--rollback` | Undo all changes using the latest backup |
| `-y, --yes` | Skip the confirmation prompt |
| `--version` | Show version |

## How It Works

1. **Phase 1** scans `Data/Sound/` and `Data/Music/` for loose `.mp3` files, backs them up, converts each to `.wav` using FFmpeg, then removes the original MP3 (the game picks up the WAV automatically).

2. **Phase 2** reads the file list from each Sound BSA archive (Bethesda's v104 format), finds `.ogg` and `.mp3` entries, extracts them, converts to WAV, and writes them as loose files. FNV loads loose files over BSA contents, so the BSA stays untouched.

3. **Backups** are stored in `<game root>/AudioFixBackup/<timestamp>/` with a `manifest.json` that tracks every change for rollback.

## Game Path Detection

The tool auto-detects FNV in these locations:

- `C:\Program Files (x86)\Steam\steamapps\common\Fallout New Vegas`
- `C:\Program Files\Steam\steamapps\common\Fallout New Vegas`
- `D:\Steam\steamapps\common\Fallout New Vegas`
- `D:\SteamLibrary\steamapps\common\Fallout New Vegas`
- Windows Registry (Steam install path)

Use `--game-dir` if your installation is elsewhere.

## Development

```bash
git clone https://github.com/mikemadest/fnv-audio-fix.git
cd fnv-audio-fix
pip install -e ".[dev]"
pytest
```

## License

[MIT](LICENSE)
