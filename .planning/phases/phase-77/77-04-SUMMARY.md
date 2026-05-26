---
phase: 77
plan: 04
status: completed
date: 2026-05-26
---

# 77-04: Index Parsing + PakFileReader — Summary

## What Was Done

### `src/uasset_read/pak/index.py`
- **`parse_primary_index(stream, pak_info, aes_key)`**: Main entry point. Reads index blob from `pak_info.index_offset`, decrypts if `pak_info.encrypted_index`, validates SHA1, then branches by version:
  - **v<10 (legacy)**: Flat `(FString path, FPakEntry)` list
  - **v10+ (PathHashIndex)**: PathHashSeed + optional PathHashIndex + optional DirectoryIndex + EncodedPakEntries (bitfield) + NonEncodedEntries (FString + bitfield)
- **`parse_path_hash_index(stream, offset, size, pak_info)`**: TMap<uint64, FPakEntryLocation> parser
- **`parse_directory_index(stream, offset, size, pak_info)`**: TMap<FString, TMap<FString, FPakEntryLocation>> parser

### `src/uasset_read/pak/reader.py`
- **`PakFileReader`**: Main orchestrator class with:
  - `open()` / `close()` + context manager (`__enter__`/`__exit__`)
  - `info` / `entries` / `mount_point` properties
  - `list_files()` — returns non-deleted paths
  - `get_entry(path)` — lookup by path
  - `extract(path)` — read + decompress file content
  - Offset bounds validation against file_size
  - Compression method resolution from FPakInfo table

### `tests/test_pak_index.py` — 6 tests
- Legacy single/multi entry parsing
- v10+ named entries with bitfield decoding
- PathHashIndex parsing
- DirectoryIndex parsing
- Encrypted index round-trip

### `tests/test_pak_reader_e2e.py` — 13 tests (1 skipped integration)
- Legacy pak: open, extract, list_files, get_entry, extract_not_found
- v10+ pak: open, extract
- Compressed entry extraction (Zlib round-trip)
- Encrypted index: correct key, wrong key (ParseError), no key (ParseError)
- Context manager open/close
- Real pak integration test (skipped without PAK_TEST_FILE)

## Test Results
- **62 passed, 1 skipped** across all `test_pak_*.py` files
- All success criteria from PLAN.md met

## Bugs Fixed During Implementation
1. **`bool(stream.read(1))` always True**: Non-empty bytes are truthy in Python. Changed to `stream.read(1)[0] != 0` for proper bool parsing in v10+ index flags.
2. **Missing compression blocks in index blob**: Legacy index writer didn't write `FPakCompressedBlock` entries. Added loop to serialize block offsets/sizes.
3. **AES hash mismatch on encrypted index**: `decrypt_aes_ecb` pads ciphertext to 16-byte alignment before decrypting. Test fixtures must compute SHA1 hash on padded plaintext to match.
4. **Mount point not threaded through v10+ parser**: `_parse_v10_index` didn't receive the mount_point from `parse_primary_index`. Added parameter.
