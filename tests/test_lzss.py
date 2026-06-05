from argparse import Namespace
from pathlib import Path
import struct
import time
import zlib

import pytest

from decoder import lz77_decode, lzss_decode
from encoder import (
    LOOKAHEAD_SIZE,
    WINDOW_SIZE,
    lz77_encode,
    lzss_encode,
    save_encoded_to_file,
)


TEST_DIRECTORIES = [
    Path("obrazy_testowe"),
    Path("rozklady_testowe"),
]


def collect_test_files():
    files = []
    for directory in TEST_DIRECTORIES:
        if directory.exists():
            files.extend(
                [
                    path
                    for path in directory.rglob("*")
                    if path.is_file()
                ]
            )
    return sorted(files)


TEST_FILES = collect_test_files()


def make_args(window_size=WINDOW_SIZE, lookahead_size=LOOKAHEAD_SIZE, min_match=3):
    return Namespace(window=window_size, lookahead=lookahead_size, min_match=min_match)


@pytest.mark.parametrize("file_path", TEST_FILES, ids=lambda p: str(p))
@pytest.mark.parametrize(
    "window_size,lookahead_size,min_match",
    [
        (4096, 18, 3),
    ],
)
def test_lzss_file_roundtrip(
    file_path,
    window_size,
    lookahead_size,
    min_match,
):
    with open(file_path, "rb") as f:
        original_data = f.read()

    args = make_args(window_size, lookahead_size, min_match)
    encoded, n_literals, n_pairs = lzss_encode(original_data, args)

    header = struct.pack(
        ">HBI",
        window_size,
        lookahead_size,
        len(original_data),
    )
    compressed = header + encoded
    decoded = lzss_decode(compressed)

    assert decoded == original_data, f"Mismatch for file: {file_path}"
    assert n_literals + n_pairs > 0


@pytest.mark.parametrize("file_path", TEST_FILES, ids=lambda p: str(p))
@pytest.mark.parametrize(
    "window_size,lookahead_size,min_match",
    [
        (4096, 18, 3),
    ],
)
def test_lz77_file_roundtrip(
    file_path,
    window_size,
    lookahead_size,
    min_match,
):
    with open(file_path, "rb") as f:
        original_data = f.read()

    args = make_args(window_size, lookahead_size, min_match)
    encoded, n_literals, n_pairs = lz77_encode(original_data, args)

    header = struct.pack(
        ">HBI",
        window_size,
        lookahead_size,
        len(original_data),
    )
    compressed = header + encoded
    decoded = lz77_decode(compressed)

    assert decoded == original_data, f"Mismatch for file: {file_path}"
    assert n_literals + n_pairs > 0


def test_test_directories_exist():
    missing = [
        str(directory)
        for directory in TEST_DIRECTORIES
        if not directory.exists()
    ]
    assert not missing, f"Missing test directories: {missing}"


def test_test_files_found():
    assert TEST_FILES, (
        "No files found in obrazy_testowe/ "
        "or rozklady_testowe/"
    )


@pytest.mark.parametrize(
    "filepath",
    [
        "rozklady_testowe/geometr_05.pgm",
    ],
)
def test_lzss_plus_huffman(filepath, tmp_path):
    with open(filepath, "rb") as f:
        original_data = f.read()

    args = make_args()
    orig_size = len(original_data)

    start_lzss = time.perf_counter()
    raw_lzss_bits, _, _ = lzss_encode(original_data, args)
    temp_lzss_file = tmp_path / "compressed_test.lzss"
    save_encoded_to_file(temp_lzss_file, raw_lzss_bits, WINDOW_SIZE, LOOKAHEAD_SIZE, orig_size)
    lzss_time = time.perf_counter() - start_lzss

    with open(temp_lzss_file, "rb") as f:
        lzss_data = f.read()
    lzss_size = len(lzss_data)

    start_huff = time.perf_counter()
    compressor = zlib.compressobj(level=9, strategy=zlib.Z_HUFFMAN_ONLY)
    final_data = compressor.compress(lzss_data) + compressor.flush()
    huff_time = time.perf_counter() - start_huff
    final_size = len(final_data)

    decoded_huffman = zlib.decompress(final_data)
    assert decoded_huffman == lzss_data, "Error! zlib decompression returned corrupted data."

    decoded_lzss = lzss_decode(decoded_huffman)
    assert decoded_lzss == original_data, "Error! LZSS decompression returned corrupted data."

    print(f"\n\n--- Results for file: {filepath} ---")
    print(f"Original: {orig_size} B")
    print(f"After LZSS:  {lzss_size} B (Time: {lzss_time:.4f} s)")
    print(f"After Huff:  {final_size} B (Time: {huff_time:.4f} s)")

    huffman_gain = lzss_size - final_size
    print(f"Gain from Huffman: {huffman_gain} B ({100 - (final_size / lzss_size * 100):.2f}%)")
    print(f"Final compression: {final_size / orig_size * 100:.2f}%")


@pytest.mark.parametrize(
    "filepath",
    [
        "rozklady_testowe/geometr_05.pgm",
        "test.txt",
    ],
)
def test_lzss_vs_lz77_benchmark(filepath, tmp_path):
    with open(filepath, "rb") as f:
        data = f.read()

    orig_size = len(data)
    assert orig_size > 0, "Plik jest pusty"
    args = make_args()

    start_lzss = time.perf_counter()
    raw_lzss_bits, _, _ = lzss_encode(data, args)
    temp_lzss_file = tmp_path / "compressed_test.lzss"
    save_encoded_to_file(temp_lzss_file, raw_lzss_bits, WINDOW_SIZE, LOOKAHEAD_SIZE, orig_size)
    lzss_time = time.perf_counter() - start_lzss
    lzss_size = temp_lzss_file.stat().st_size

    start_lz77 = time.perf_counter()
    raw_lz77_bits, _, _ = lz77_encode(data, args)
    temp_lz77_file = tmp_path / "compressed_test.lz77"
    save_encoded_to_file(temp_lz77_file, raw_lz77_bits, WINDOW_SIZE, LOOKAHEAD_SIZE, orig_size)
    lz77_time = time.perf_counter() - start_lz77
    lz77_size = temp_lz77_file.stat().st_size

    with open(temp_lzss_file, "rb") as f:
        lzss_on_disk = f.read()
    with open(temp_lz77_file, "rb") as f:
        lz77_on_disk = f.read()

    assert lzss_decode(lzss_on_disk) == data
    assert lz77_decode(lz77_on_disk) == data

    print(f"\n\n--- Benchmark for file: {filepath} ---")
    print(f"Original size: {orig_size} bytes")

    print("\n[LZSS]")
    print(f" - Size after compression: {lzss_size} bytes")
    print(f" - Compression ratio:  {(lzss_size / orig_size) * 100:.1f}% of original")
    print(f" - Time:       {lzss_time:.4f} seconds")

    print("\n[LZ77]")
    print(f" - Size after compression: {lz77_size} bytes")
    print(f" - Compression ratio:  {(lz77_size / orig_size) * 100:.1f}% of original")
    print(f" - Time:       {lz77_time:.4f} seconds")

    size_diff = lzss_size - lz77_size
    print("\n[Summary of sizes]")
    if size_diff > 0:
        print(f"LZ77 compressed the data better by {size_diff} bytes.")
    else:
        print(f"LZSS compressed the data better by {abs(size_diff)} bytes.")

    assert lzss_size > 0
    assert lz77_size > 0
