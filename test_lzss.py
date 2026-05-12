# tests/test_lzss_files.py

from pathlib import Path
import struct

import pytest

from encoder import lzss_encode, save_lzss
from decoder import lzss_decode

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

    encoded, writer, n_literals, n_pairs = lzss_encode(
    original_data,
    window_size=window_size,
    lookahead_size=lookahead_size,
    min_match=min_match,
)

    header = struct.pack(
        '>HBI',
        window_size,
        lookahead_size,
        len(original_data)
    )

    compressed = header + encoded

    decoded = lzss_decode(compressed)

    assert decoded == original_data, f"Mismatch for file: {file_path}"

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