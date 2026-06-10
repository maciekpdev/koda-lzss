#!/usr/bin/env python3
"""LZSS/LZ77 analysis: compress test files, compute entropy and metrics, save CSV and histograms."""

from argparse import Namespace
import csv
import sys
import time
import zlib
from pathlib import Path

import matplotlib
import numpy as np

matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from encoder import (
    LOOKAHEAD_SIZE,
    WINDOW_SIZE,
    lz77_encode,
    lzss_encode,
    save_encoded_to_file,
)

HISTOGRAM_DIR = Path("histograms")
HISTOGRAM_DIR.mkdir(exist_ok=True)

TMP_DIR = Path("_tmp_lzss")
TMP_DIR.mkdir(exist_ok=True)


def make_args(window_size=WINDOW_SIZE, lookahead_size=LOOKAHEAD_SIZE, min_match=3):
    return Namespace(window=window_size, lookahead=lookahead_size, min_match=min_match)


def compute_entropy_h1(arr: np.ndarray) -> float:
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
    _, counts = np.unique(triple_idx, return_counts=True)
    total = n - 2
    p = counts / total
    return float(-np.sum(p * np.log2(p)) / 3)


def save_histogram(arr: np.ndarray, title: str, out_path: Path) -> None:
    freq = np.bincount(arr, minlength=256)
    fig, ax = plt.subplots(figsize=(8, 4))
    ax.bar(range(256), freq, width=1.0, color="steelblue", edgecolor="none")
    ax.set_xlabel("Wartosc bajtu")
    ax.set_ylabel("Liczba wystapien")
    ax.set_title(f"Histogram - {title}")
    ax.set_xlim(-1, 256)
    fig.tight_layout()
    fig.savefig(out_path, dpi=100)
    plt.close(fig)


def extract_pixel_bytes(raw: bytes) -> np.ndarray:
    """Pixel bytes from P5 PGM; all bytes for other inputs."""
    if not raw.startswith(b"P5"):
        return np.frombuffer(raw, dtype=np.uint8)
    try:
        idx = 2
        tokens = []
        while len(tokens) < 3:
            while idx < len(raw) and chr(raw[idx]) in " \t\n\r":
                idx += 1
            if idx < len(raw) and raw[idx:idx + 1] == b"#":
                while idx < len(raw) and raw[idx:idx + 1] != b"\n":
                    idx += 1
                continue
            start = idx
            while idx < len(raw) and chr(raw[idx]).isdigit():
                idx += 1
            tokens.append(int(raw[start:idx]))
        idx += 1
        return np.frombuffer(raw[idx:], dtype=np.uint8)
    except Exception:
        return np.frombuffer(raw, dtype=np.uint8)


def analyze_file(file_path: Path, args: Namespace) -> dict:
    with open(file_path, "rb") as f:
        raw = f.read()

    orig_size = len(raw)
    name = file_path.name
    print(f"  [{name}]  {orig_size:,} B ...", end=" ", flush=True)

    arr_data = extract_pixel_bytes(raw)

    t0 = time.perf_counter()
    lzss_payload, _, _ = lzss_encode(raw, args)
    lzss_time = time.perf_counter() - t0

    lzss_file = TMP_DIR / f"{name}.lzss"
    save_encoded_to_file(lzss_file, lzss_payload, args.window, args.lookahead, orig_size)
    lzss_size = lzss_file.stat().st_size

    t0 = time.perf_counter()
    lz77_payload, _, _ = lz77_encode(raw, args)
    lz77_time = time.perf_counter() - t0

    lz77_file = TMP_DIR / f"{name}.lz77"
    save_encoded_to_file(lz77_file, lz77_payload, args.window, args.lookahead, orig_size)
    lz77_size = lz77_file.stat().st_size

    t0 = time.perf_counter()
    with open(lzss_file, "rb") as f:
        lzss_on_disk = f.read()
    compressor = zlib.compressobj(level=9, strategy=zlib.Z_HUFFMAN_ONLY)
    huff_data = compressor.compress(lzss_on_disk) + compressor.flush()
    huff_time = time.perf_counter() - t0
    huff_size = len(huff_data)

    # Entropy on pixel/data bytes only (PGM header excluded)
    h1 = compute_entropy_h1(arr_data)
    h2 = compute_entropy_h2(arr_data)
    h3 = compute_entropy_h3(arr_data)

    l_avg_lzss = (lzss_size * 8) / orig_size
    l_avg_lz77 = (lz77_size * 8) / orig_size

    safe_name = name.replace(".", "_")
    hist_path = HISTOGRAM_DIR / f"{safe_name}_hist.png"
    save_histogram(arr_data, name, hist_path)

    print(
        f"LZSS={lzss_size:,}B ({lzss_time:.1f}s)  "
        f"LZ77={lz77_size:,}B ({lz77_time:.1f}s)",
        flush=True,
    )

    return {
        "file": name,
        "orig_size": orig_size,
        "lzss_size": lzss_size,
        "lz77_size": lz77_size,
        "cr_lzss": orig_size / lzss_size if lzss_size else 0.0,
        "cr_lz77": orig_size / lz77_size if lz77_size else 0.0,
        "r_lzss_pct": (1 - lzss_size / orig_size) * 100 if orig_size else 0.0,
        "r_lz77_pct": (1 - lz77_size / orig_size) * 100 if orig_size else 0.0,
        "l_avg_lzss": l_avg_lzss,
        "l_avg_lz77": l_avg_lz77,
        "lzss_time": lzss_time,
        "lz77_time": lz77_time,
        "huff_size": huff_size,
        "huff_time": huff_time,
        "h1": h1,
        "h2": h2,
        "h3": h3,
        "hist_path": str(hist_path),
    }


def print_table1(results):
    print("\n" + "=" * 100)
    print("TABLE 1 - Compression Results (LZSS vs LZ77)")
    print("=" * 100)
    print(
        f"  {'File':<24} {'Orig(B)':>9} {'LZSS(B)':>9} {'LZ77(B)':>9} "
        f"{'CR_LZSS':>8} {'CR_LZ77':>8} {'R_LZSS(%)':>10} {'R_LZ77(%)':>10}"
    )
    print("  " + "-" * 96)
    for r in results:
        print(
            f"  {r['file']:<24} {r['orig_size']:>9,} {r['lzss_size']:>9,} {r['lz77_size']:>9,} "
            f"{r['cr_lzss']:>8.3f} {r['cr_lz77']:>8.3f} {r['r_lzss_pct']:>10.2f} {r['r_lz77_pct']:>10.2f}"
        )


def print_table2(results):
    print("\n" + "=" * 100)
    print("TABLE 2 - Entropy vs Average Bit Length (bits per symbol)")
    print("=" * 100)
    print(
        f"  {'File':<24} {'H1':>7} {'H2/2':>7} {'H3/3':>7} "
        f"{'l_avg_LZSS':>11} {'l_avg_LZ77':>11} {'LZSS<H1':>8} {'LZ77<H1':>8}"
    )
    print("  " + "-" * 96)
    for r in results:
        lzss_flag = "TAK" if r["l_avg_lzss"] < r["h1"] else "NIE"
        lz77_flag = "TAK" if r["l_avg_lz77"] < r["h1"] else "NIE"
        print(
            f"  {r['file']:<24} {r['h1']:>7.4f} {r['h2']:>7.4f} {r['h3']:>7.4f} "
            f"{r['l_avg_lzss']:>11.3f} {r['l_avg_lz77']:>11.3f} {lzss_flag:>8} {lz77_flag:>8}"
        )


def print_table3(results):
    print("\n" + "=" * 100)
    print("TABLE 3 - Runtime + LZSS+Huffman Gain")
    print("=" * 100)
    print(
        f"  {'File':<24} {'t_LZSS(s)':>10} {'t_LZ77(s)':>10} "
        f"{'LZSS(B)':>10} {'LZSS+Huff(B)':>14} {'HuffGain(B)':>11} {'HuffGain(%)':>11}"
    )
    print("  " + "-" * 96)
    for r in results:
        huff_gain_bytes = r["lzss_size"] - r["huff_size"]
        huff_gain_pct = (huff_gain_bytes / r["lzss_size"] * 100) if r["lzss_size"] else 0.0
        print(
            f"  {r['file']:<24} {r['lzss_time']:>10.3f} {r['lz77_time']:>10.3f} "
            f"{r['lzss_size']:>10,} {r['huff_size']:>14,} {huff_gain_bytes:>11,} {huff_gain_pct:>11.2f}"
        )


def collect_files():
    dirs = [Path("rozklady_testowe"), Path("obrazy_testowe")]
    files = []
    for directory in dirs:
        if directory.exists():
            files.extend(sorted(path for path in directory.rglob("*") if path.is_file()))
    txt = Path("test.txt")
    if txt.exists():
        files.append(txt)
    return files


def main():
    files = collect_files()
    if not files:
        print("ERROR: No test files found. Make sure obrazy_testowe/ and rozklady_testowe/ exist.")
        sys.exit(1)

    args = make_args()
    print(f"Found {len(files)} files.\n")

    results = []
    for file_path in files:
        try:
            results.append(analyze_file(file_path, args))
        except Exception as exc:
            print(f"\n  ERROR on {file_path.name}: {exc}", flush=True)

    print_table1(results)
    print_table2(results)
    print_table3(results)

    csv_path = Path("analysis_results.csv")
    fields = [
        "file",
        "orig_size",
        "lzss_size",
        "lz77_size",
        "cr_lzss",
        "cr_lz77",
        "r_lzss_pct",
        "r_lz77_pct",
        "l_avg_lzss",
        "l_avg_lz77",
        "lzss_time",
        "lz77_time",
        "huff_size",
        "huff_time",
        "h1",
        "h2",
        "h3",
        "hist_path",
    ]
    with open(csv_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(results)

    print(f"\nCSV saved -> {csv_path}")
    print(f"Histograms -> {HISTOGRAM_DIR}/")


if __name__ == "__main__":
    main()
