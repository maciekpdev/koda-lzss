from pathlib import Path
import struct
import zlib
import pytest
import time
from decoder import lzss_decode
from encoder import lzss_encode, save_encoded_to_file, WINDOW_SIZE, LOOKAHEAD_SIZE
import lz4.frame 
import os

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







@pytest.mark.parametrize("filepath", [
    #"obrazy_testowe/barbara.pgm"
    "rozklady_testowe/geometr_05.pgm"
])
def test_lzss_plus_huffman(filepath, tmp_path):
   
    with open(filepath, "rb") as f:
        original_data = f.read()

    orig_size = len(original_data)

    
    start_lzss = time.perf_counter()
    raw_lzss_bits, _, _, _ = lzss_encode(original_data)
    
   
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
    print(f"Gain from Huffman: {huffman_gain} B ({100 - (final_size/lzss_size * 100):.2f}%)")
    print(f"Final compression: {final_size / orig_size * 100:.2f}%")




@pytest.mark.parametrize("filepath", [
    "rozklady_testowe/geometr_05.pgm",
    "test.txt"
])
def test_lzss_vs_lz4_benchmark(filepath, tmp_path):
    

    with open(filepath, "rb") as f:
        data = f.read()

    orig_size = len(data)
    assert orig_size > 0, "Plik jest pusty"

    
    start_lzss = time.perf_counter()
    raw_lzss_bits, _, _, _ = lzss_encode(data)
    
    
    temp_lzss_file = tmp_path / "compressed_test.lzss"
    
    
    save_encoded_to_file(temp_lzss_file, raw_lzss_bits, WINDOW_SIZE, LOOKAHEAD_SIZE, orig_size)
    
    lzss_time = time.perf_counter() - start_lzss

    
    my_lzss_size = os.path.getsize(temp_lzss_file)

    
    start_lz4 = time.perf_counter()
    
    
    lz4_data = lz4.frame.compress(data, compression_level=9)
    lz4_size = len(lz4_data)
    
    lz4_time = time.perf_counter() - start_lz4

    
    print(f"\n\n--- Benchmark for file: {filepath} ---")
    print(f"Original size: {orig_size} bytes")
    
    print(f"\n[LZSS]")
    print(f" - Size after compression: {my_lzss_size} bytes")
    print(f" - Compression ratio:  {(my_lzss_size / orig_size) * 100:.1f}% of original")
    print(f" - Time:       {lzss_time:.4f} seconds")
    
    print(f"\n[Library LZ4]")
    print(f" - Size after compression: {lz4_size} bytes")
    print(f" - Compression ratio:  {(lz4_size / orig_size) * 100:.1f}% of original")
    print(f" - Time:       {lz4_time:.4f} seconds")
    
   
    size_diff = my_lzss_size - lz4_size
    
    print(f"\n[Summary of sizes]")
    if size_diff > 0:
        print(f"LZ4 compressed the data better by {size_diff} bytes.")
    else:
        print(f"LZSS compressed the data better by {abs(size_diff)} bytes than the LZ4 library.")

    assert my_lzss_size < orig_size, "LZSS did not reduce the file size"