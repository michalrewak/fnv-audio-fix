"""BSA v104 archive reader for Fallout 3 / New Vegas format."""

import os
import struct
import zlib

BSA_MAGIC = b"BSA\x00"
BSA_VERSION_FNV = 104
BSA_FLAG_COMPRESSED = 0x04
BSA_FLAG_EMBED_FILENAMES = 0x100


def read_bsa_file_list(bsa_path):
    """Parse a BSA archive and return its file records.

    Args:
        bsa_path: Path to the .bsa file.

    Returns:
        List of dicts with keys: folder, name, offset, size, compressed,
        embed_names.  Returns None if the file is not a valid FNV BSA.
    """
    with open(bsa_path, "rb") as f:
        magic = f.read(4)
        if magic != BSA_MAGIC:
            return None

        version, offset, archive_flags = struct.unpack("<III", f.read(12))
        folder_count, file_count = struct.unpack("<II", f.read(8))
        total_folder_name_len, total_file_name_len, file_flags = struct.unpack(
            "<III", f.read(12)
        )

        if version != BSA_VERSION_FNV:
            return None

        default_compressed = bool(archive_flags & BSA_FLAG_COMPRESSED)
        embed_names = bool(archive_flags & BSA_FLAG_EMBED_FILENAMES)

        # Read folder records
        f.seek(offset)
        folders = []
        for _ in range(folder_count):
            name_hash, fc, foffset = struct.unpack("<QII", f.read(16))
            folders.append({"count": fc, "offset": foffset})

        # Read file records with folder names
        file_recs = []
        for folder in folders:
            name_len = struct.unpack("<B", f.read(1))[0]
            folder_name = f.read(name_len).rstrip(b"\x00").decode(
                "utf-8", errors="replace"
            )

            for _ in range(folder["count"]):
                fhash, fsize_raw, foffset = struct.unpack("<QII", f.read(16))
                compress_toggle = bool(fsize_raw & 0x40000000)
                fsize = fsize_raw & 0x3FFFFFFF
                is_compressed = default_compressed ^ compress_toggle
                file_recs.append(
                    {
                        "folder": folder_name,
                        "offset": foffset,
                        "size": fsize,
                        "compressed": is_compressed,
                        "embed_names": embed_names,
                    }
                )

        # Read file name block
        names_data = f.read(total_file_name_len)
        idx = 0
        for rec in file_recs:
            end = names_data.index(b"\x00", idx)
            rec["name"] = names_data[idx:end].decode("utf-8", errors="replace")
            idx = end + 1

    return file_recs


def extract_file_from_bsa(bsa_path, file_rec):
    """Extract a single file's raw bytes from a BSA archive.

    Args:
        bsa_path: Path to the .bsa file.
        file_rec: A file record dict returned by read_bsa_file_list().

    Returns:
        The raw file bytes (decompressed if the record was compressed).
    """
    with open(bsa_path, "rb") as f:
        f.seek(file_rec["offset"])
        data_size = file_rec["size"]

        # Skip embedded filename if present
        if file_rec["embed_names"]:
            name_len = struct.unpack("<B", f.read(1))[0]
            f.seek(name_len, 1)
            data_size -= 1 + name_len

        if file_rec["compressed"]:
            original_size = struct.unpack("<I", f.read(4))[0]
            compressed_data = f.read(data_size - 4)
            try:
                return zlib.decompress(compressed_data)
            except zlib.error:
                return compressed_data
        else:
            return f.read(data_size)
