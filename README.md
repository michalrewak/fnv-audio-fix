# FNV Audio Fix

**Fix audio crackling in Fallout: New Vegas** by patching INI audio buffer settings.

Uses the [Viva New Vegas](https://vivanewvegas.moddinglinked.com/) recommended audio configuration.

## The Problem

Fallout: New Vegas has well-known audio issues:

- **Crackling/popping** on radio stations, the main menu, and during gameplay
- **Audio stuttering** with many sounds playing simultaneously

These are caused by the game's default audio buffer settings being too small and single-threaded audio processing.

## The Fix

This tool applies the community-recommended audio settings from the Viva New Vegas modding guide:

| Setting | Default | Fixed | Purpose |
|---------|---------|-------|---------|
| `iAudioCacheSize` | 2048 | **16384** | Larger audio buffer prevents crackling |
| `iMaxSizeForCachedSound` | 256 | **2048** | Cache larger sound files |
| `bMultiThreadAudio` | 0 | **1** | Enable multi-threaded audio processing |
| `bUseAudioDebugInformation` | 1 | **0** | Disable debug overhead |

Settings are applied to all three INI files:
- `Fallout_default.ini` (game root - overwrites Fallout.ini on launch)
- `Fallout.ini` (user settings in Documents)
- `FalloutPrefs.ini` (user preferences in Documents)

## Requirements

- **Python 3.8+** - [python.org/downloads](https://www.python.org/downloads/)

No external dependencies (no FFmpeg needed).

## Installation

```bash
pip install fnv-audio-fix
```

Or install from source:

```bash
git clone https://github.com/michalrewak/fnv-audio-fix.git
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

1. Finds your FNV installation (Steam auto-detection or `--game-dir`)
2. Backs up all INI files before modification
3. Patches audio settings in `Fallout_default.ini`, `Fallout.ini`, and `FalloutPrefs.ini`
4. Stores a manifest for easy rollback

Backups are stored in `<game root>/AudioFixBackup/<timestamp>/` with a `manifest.json`.

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
git clone https://github.com/michalrewak/fnv-audio-fix.git
cd fnv-audio-fix
pip install -e ".[dev]"
pytest
```

## Credits

Audio fix settings from the [Viva New Vegas](https://vivanewvegas.moddinglinked.com/utilities.html) modding guide.

## License

[MIT](LICENSE)
