#!/usr/bin/env python3
"""
analysis.py – LZSS project analysis script.

For every file in rozklady_testowe/, obrazy_testowe/, and test.txt:
  - Runs LZSS encode and saves compressed file
  - Applies zlib Huffman-only on top of LZSS output
  - Compresses with LZ4 for comparison
  - Computes H1 (Shannon entropy), H2/2 and H3/3 (block/Markov per-symbol entropy)
  - Computes average bit length l_avg = compressed_bits / original_symbols
  - Saves histogram as PNG

Three result tables are printed and saved to analysis_results.csv.
Histograms are saved in histograms/.
"""

import csv
import sys
import time
import zlib
from pathlib import Path

import lz4.frame
import matplotlib
import numpy as np

matplotlib.use("Agg")
import matplotlib.pyplot as plt

from encoder import LOOKAHEAD_SIZE, WINDOW_SIZE, lzss_encode, save_encoded_to_file

# Directories

HISTOGRAM_DIR = Path("histograms")
HISTOGRAM_DIR.mkdir(exist_ok=True)

TMP_DIR = Path("_tmp_lzss")
TMP_DIR.mkdir(exist_ok=True)



# Entropy helpers

def compute_entropy_h1(arr: np.ndarray) -> float:
    """Shannon entropy H(X) in bits per symbol."""
    counts = np.bincount(arr, minlength=256)
    counts = counts[counts > 0]
    p = counts / counts.sum()
    return float(-np.sum(p * np.log2(p)))


def compute_entropy_h2(arr: np.ndarray) -> float:
    """Per-symbol block entropy of order 2: H_joint(2) / 2."""
    n = len(arr)
    if n < 2:
        return 0.0
    pair_idx = arr[:-1].astype(np.int32) * 256 + arr[1:].astype(np.int32)
    counts = np.bincount(pair_idx, minlength=65536)
    counts = counts[counts > 0]
    total = n - 1
    p = counts / total
    return float(-np.sum(p * np.log2(p)) / 2)


def compute_entropy_h3(arr: np.ndarray) -> float:
    """Per-symbol block entropy of order 3: H_joint(3) / 3."""
    n = len(arr)
    if n < 3:
        return 0.0
    a = arr[:-2].astype(np.int64)
    b = arr[1:-1].astype(np.int64)
    c = arr[2:].astype(np.int64)
    triple_idx = a * 65536 + b * 256 + c
    # np.unique is sparse-friendly (no 16 M-entry bincount array)
    _, counts = np.unique(triple_idx, return_counts=True)
    total = n - 2
    p = counts / total
    return float(-np.sum(p * np.log2(p)) / 3)


# Histogram

def save_histogram(arr: np.ndarray, title: str, out_path: Path) -> None:
    freq = np.bincount(arr, minlength=256)
    fig, ax = plt.subplots(figsize=(8, 4))
    ax.bar(range(256), freq, width=1.0, color="steelblue", edgecolor="none")
    ax.set_xlabel("Wartość bajtu")
    ax.set_ylabel("Liczba wystąpień")
    ax.set_title(f"Histogram – {title}")
    ax.set_xlim(-1, 256)
    fig.tight_layout()
    fig.savefig(out_path, dpi=100)
    plt.close(fig)


# PGM pixel extraction (strip ASCII header)

def extract_pixel_bytes(raw: bytes) -> np.ndarray:
    """Return just the pixel byte array for a P5 PGM file, or all bytes otherwise."""
    if not raw.startswith(b"P5"):
        return np.frombuffer(raw, dtype=np.uint8)
    try:
        idx = 2
        tokens = []
        while len(tokens) < 3:
            # skip whitespace and # comments
            while idx < len(raw) and chr(raw[idx]) in " \t\n\r":
                idx += 1
            if idx < len(raw) and raw[idx:idx+1] == b"#":
                while idx < len(raw) and raw[idx:idx+1] != b"\n":
                    idx += 1
                continue
            start = idx
            while idx < len(raw) and chr(raw[idx]).isdigit():
                idx += 1
            tokens.append(int(raw[start:idx]))
        # skip exactly one whitespace byte after maxval
        idx += 1
        pixel_bytes = raw[idx:]
        return np.frombuffer(pixel_bytes, dtype=np.uint8)
    except Exception:
        return np.frombuffer(raw, dtype=np.uint8)


# Per-file analysis

def analyze_file(file_path: Path) -> dict:
    with open(file_path, "rb") as f:
        raw = f.read()

    orig_size = len(raw)
    name = file_path.name
    print(f"  [{name}]  {orig_size:,} B ...", end=" ", flush=True)

    arr_data = extract_pixel_bytes(raw)

    t0 = time.perf_counter()
    compressed_bits, _, _, _ = lzss_encode(raw)
    lzss_encode_time = time.perf_counter() - t0

    tmp_lzss = TMP_DIR / (name + ".lzss")
    save_encoded_to_file(tmp_lzss, compressed_bits, WINDOW_SIZE, LOOKAHEAD_SIZE, orig_size)
    lzss_size = tmp_lzss.stat().st_size

    # LZSS + Huffman (zlib Huffman-only)
    t0 = time.perf_counter()
    with open(tmp_lzss, "rb") as f:
        lzss_bytes_on_disk = f.read()
    comp = zlib.compressobj(level=9, strategy=zlib.Z_HUFFMAN_ONLY)
    huff_data = comp.compress(lzss_bytes_on_disk) + comp.flush()
    huff_time = time.perf_counter() - t0
    huff_size = len(huff_data)

    # LZ4
    t0 = time.perf_counter()
    lz4_data = lz4.frame.compress(raw, compression_level=9)
    lz4_time = time.perf_counter() - t0
    lz4_size = len(lz4_data)

    # Entropy (on data bytes only, excluding PGM header)
    h1 = compute_entropy_h1(arr_data)
    h2 = compute_entropy_h2(arr_data)
    h3 = compute_entropy_h3(arr_data)

    # l_avg: bits per original byte (using full LZSS file size)
    l_avg = (lzss_size * 8) / orig_size

    safe_name = name.replace(".", "_")
    hist_path = HISTOGRAM_DIR / f"{safe_name}_hist.png"
    save_histogram(arr_data, name, hist_path)

    print(
        f"LZSS={lzss_size:,}B ({lzss_encode_time:.1f}s)  "
        f"H1={h1:.3f}  l_avg={l_avg:.3f}",
        flush=True,
    )

    return {
        "file": name,
        "orig_size": orig_size,
        "lzss_size": lzss_size,
        "cr": orig_size / lzss_size if lzss_size else 0.0,
        "r_pct": (1 - lzss_size / orig_size) * 100 if orig_size else 0.0,
        "l_avg": l_avg,
        "lzss_time": lzss_encode_time,
        "huff_size": huff_size,
        "huff_time": huff_time,
        "lz4_size": lz4_size,
        "lz4_time": lz4_time,
        "h1": h1,
        "h2": h2,
        "h3": h3,
        "hist_path": str(hist_path),
    }


# Table printers

def print_table1(results):
    print("\n" + "=" * 72)
    print("TABLE 1 – Compression Results")
    print("=" * 72)
    print(f"  {'File':<24} {'Orig(B)':>9} {'LZSS(B)':>9} {'CR':>6} {'R(%)':>7} {'l_avg':>7}")
    print("  " + "-" * 68)
    for r in results:
        print(
            f"  {r['file']:<24} {r['orig_size']:>9,} {r['lzss_size']:>9,}"
            f"  {r['cr']:>5.3f}  {r['r_pct']:>6.2f}  {r['l_avg']:>6.3f}"
        )

def print_table2(results):
    print("\n" + "=" * 72)
    print("TABLE 2 – Entropy Analysis  (bits per symbol)")
    print("=" * 72)
    print(f"  {'File':<24} {'H1':>7} {'H2/2':>7} {'H3/3':>7} {'l_avg':>7} {'l<H1':>6}")
    print("  " + "-" * 63)
    for r in results:
        flag = "TAK" if r["l_avg"] < r["h1"] else "NIE"
        print(
            f"  {r['file']:<24} {r['h1']:>7.4f} {r['h2']:>7.4f}"
            f" {r['h3']:>7.4f} {r['l_avg']:>7.3f} {flag:>6}"
        )

def print_table3(results):
    print("\n" + "=" * 80)
    print("TABLE 3 – LZSS vs LZSS+Huffman vs LZ4  (sizes in bytes, times in seconds)")
    print("=" * 80)
    print(
        f"  {'File':<24} {'LZSS':>9} {'t_enc':>7}"
        f" {'LZSS+Huff':>10} {'t_huff':>7} {'LZ4':>9} {'t_lz4':>7}"
    )
    print("  " + "-" * 76)
    for r in results:
        print(
            f"  {r['file']:<24} {r['lzss_size']:>9,} {r['lzss_time']:>7.2f}"
            f" {r['huff_size']:>10,} {r['huff_time']:>7.4f}"
            f" {r['lz4_size']:>9,} {r['lz4_time']:>7.4f}"
        )


# File collection

def collect_files():
    dirs = [Path("rozklady_testowe"), Path("obrazy_testowe")]
    files = []
    for d in dirs:
        if d.exists():
            files.extend(sorted(p for p in d.rglob("*") if p.is_file()))
    txt = Path("test.txt")
    if txt.exists():
        files.append(txt)
    return files


# Main

def main():
    files = collect_files()
    if not files:
        print("ERROR: No test files found. Make sure obrazy_testowe/ and rozklady_testowe/ exist.")
        sys.exit(1)

    print(f"Found {len(files)} files.\n")

    results = []
    for fp in files:
        try:
            results.append(analyze_file(fp))
        except Exception as exc:
            print(f"\n  ERROR on {fp.name}: {exc}", flush=True)

    print_table1(results)
    print_table2(results)
    print_table3(results)

    # Save CSV
    csv_path = Path("analysis_results.csv")
    fields = [
        "file", "orig_size", "lzss_size", "cr", "r_pct", "l_avg",
        "lzss_time", "huff_size", "huff_time", "lz4_size", "lz4_time",
        "h1", "h2", "h3", "hist_path",
    ]
    with open(csv_path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(results)

    print(f"\nCSV saved → {csv_path}")
    print(f"Histograms → {HISTOGRAM_DIR}/")


if __name__ == "__main__":
    main()
