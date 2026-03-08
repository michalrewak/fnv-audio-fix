"""Tests for BSA v104 reader."""

import struct
import pytest

from fnv_audio_fix.bsa import (
    BSA_MAGIC,
    BSA_VERSION_FNV,
    BSA_FLAG_COMPRESSED,
    BSA_FLAG_EMBED_FILENAMES,
    read_bsa_file_list,
    extract_file_from_bsa,
)


def _make_bsa(tmp_path, files, archive_flags=0):
    """Build a minimal BSA v104 for testing.

    Args:
        tmp_path: pytest tmp_path fixture.
        files: list of (folder, name, data) tuples.
        archive_flags: BSA archive flags.

    Returns:
        Path to the created .bsa file.
    """
    # Group files by folder
    folders = {}
    for folder, name, data in files:
        folders.setdefault(folder, []).append((name, data))

    folder_count = len(folders)
    file_count = len(files)

    # Pre-compute hashes (just sequential for testing)
    folder_names_list = sorted(folders.keys())

    # Build file name block
    file_names_bytes = b""
    for folder_name in folder_names_list:
        for fname, _ in folders[folder_name]:
            file_names_bytes += fname.encode("utf-8") + b"\x00"

    total_file_name_len = len(file_names_bytes)

    # Compute total folder name length (including length byte and null)
    total_folder_name_len = sum(len(f.encode("utf-8")) + 2 for f in folder_names_list)

    # Header offset (36 bytes header)
    header_offset = 36

    # Folder records start right after header
    folder_records_offset = header_offset
    # File records start after folder records
    file_records_start = folder_records_offset + folder_count * 16

    # Build the BSA in memory
    buf = bytearray()

    # Header
    buf += BSA_MAGIC
    buf += struct.pack("<I", BSA_VERSION_FNV)
    buf += struct.pack("<I", header_offset)  # offset (points to folder records)
    buf += struct.pack("<I", archive_flags)
    buf += struct.pack("<I", folder_count)
    buf += struct.pack("<I", file_count)
    buf += struct.pack("<I", total_folder_name_len)
    buf += struct.pack("<I", total_file_name_len)
    buf += struct.pack("<I", 0)  # file_flags

    # Folder records (we'll fix offsets after computing layout)
    folder_record_positions = []
    for i, folder_name in enumerate(folder_names_list):
        folder_record_positions.append(len(buf))
        fc = len(folders[folder_name])
        buf += struct.pack("<Q", i + 1)      # name_hash (dummy)
        buf += struct.pack("<I", fc)
        buf += struct.pack("<I", 0)           # offset placeholder
    assert len(buf) == file_records_start

    # File record blocks (with folder name prefix per folder)
    # We need to know where file data will go to set offsets
    # First pass: compute sizes
    file_record_blocks_size = total_folder_name_len + file_count * 16
    data_start = file_records_start + file_record_blocks_size + total_file_name_len

    # Write folder name + file records
    data_offset = data_start
    file_data_list = []
    for i, folder_name in enumerate(folder_names_list):
        block_offset = len(buf)
        # Patch folder record offset
        struct.pack_into("<I", buf, folder_record_positions[i] + 12, block_offset - total_file_name_len)

        # Folder name (length byte + name + null)
        encoded = folder_name.encode("utf-8") + b"\x00"
        buf += struct.pack("<B", len(encoded))
        buf += encoded

        for fname, fdata in folders[folder_name]:
            fhash = hash(fname) & 0xFFFFFFFFFFFFFFFF
            fsize = len(fdata)
            buf += struct.pack("<Q", fhash)
            buf += struct.pack("<I", fsize)
            buf += struct.pack("<I", data_offset)
            data_offset += len(fdata)
            file_data_list.append(fdata)

    # File names block
    buf += file_names_bytes

    # File data
    for fdata in file_data_list:
        buf += fdata

    bsa_path = tmp_path / "test.bsa"
    bsa_path.write_bytes(bytes(buf))
    return bsa_path


class TestReadBsaFileList:
    def test_invalid_magic(self, tmp_path):
        bad = tmp_path / "bad.bsa"
        bad.write_bytes(b"NOTBSA" + b"\x00" * 100)
        assert read_bsa_file_list(bad) is None

    def test_wrong_version(self, tmp_path):
        buf = BSA_MAGIC + struct.pack("<III", 999, 36, 0) + b"\x00" * 100
        bad = tmp_path / "wrongver.bsa"
        bad.write_bytes(buf)
        assert read_bsa_file_list(bad) is None

    def test_single_file(self, tmp_path):
        data = b"hello world"
        bsa = _make_bsa(tmp_path, [("sound", "test.ogg", data)])
        records = read_bsa_file_list(bsa)
        assert records is not None
        assert len(records) == 1
        assert records[0]["name"] == "test.ogg"
        assert records[0]["folder"] == "sound"

    def test_multiple_folders(self, tmp_path):
        files = [
            ("music", "song.mp3", b"mp3data"),
            ("sound\\fx", "boom.ogg", b"oggdata"),
        ]
        bsa = _make_bsa(tmp_path, files)
        records = read_bsa_file_list(bsa)
        assert len(records) == 2
        names = {r["name"] for r in records}
        assert names == {"song.mp3", "boom.ogg"}


class TestExtractFileFromBsa:
    def test_extract_uncompressed(self, tmp_path):
        data = b"raw audio bytes here"
        bsa = _make_bsa(tmp_path, [("sound", "test.wav", data)])
        records = read_bsa_file_list(bsa)
        extracted = extract_file_from_bsa(bsa, records[0])
        assert extracted == data

    def test_extract_multiple(self, tmp_path):
        files = [
            ("sfx", "a.ogg", b"alpha"),
            ("sfx", "b.ogg", b"bravo"),
        ]
        bsa = _make_bsa(tmp_path, files)
        records = read_bsa_file_list(bsa)
        assert extract_file_from_bsa(bsa, records[0]) == b"alpha"
        assert extract_file_from_bsa(bsa, records[1]) == b"bravo"
