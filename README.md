# koda-lzss

Project for the Data Compression course implementing both:

- `LZSS` (default mode)
- `LZ77` (optional mode via `--lz77`)

Core files:

- `encoder.py` - encoder CLI and algorithms (`lzss_encode`, `lz77_encode`)
- `decoder.py` - decoder CLI and algorithms (`lzss_decode`, `lz77_decode`)
- `utilities/SplayTree.py` - dynamic dictionary acceleration
- `tests/test_lzss.py` - roundtrip + benchmark tests
- `tests/analysis.py` - entropy/histogram + benchmark analysis

## Compressed file format (`.lzss` / `.lz77`)

Both modes use the same file header followed by a mode-specific bitstream.

### Header (7 bytes)

| Bytes | Field            | Type   | Description |
|---|---|---|---|
| 0-1 | `window_size`    | uint16 | Sliding window size |
| 2   | `lookahead_size` | uint8  | Lookahead buffer size |
| 3-6 | `original_size`  | uint32 | Original data size in bytes |

All multi-byte values are big-endian.

Note: `min_match` is a runtime encoder parameter; it is not serialized in the file header.

## Bitstream overview

### LZSS tokens

- Literal: `0` + `8 bits` literal byte
- Match: `1` + `offset_bits` + `length_bits`

where:

- `offset_bits = ceil(log2(window_size))`
- `length_bits = ceil(log2(lookahead_size))`

### LZ77 tokens

- Always outputs triples: `offset_bits` + `length_bits` + `8 bits next_char`

## CLI usage

### Encode (LZSS default)

```bash
python encoder.py input.bin --output compressed.lzss
```

### Encode in LZ77 mode

```bash
python encoder.py input.bin --lz77 --output compressed.lz77
```

If `--lz77` is set and output is left as default, encoder switches output name to `compressed.lz77`.

### Decode (LZSS default)

```bash
python decoder.py compressed.lzss --output restored.bin
```

### Decode in LZ77 mode

```bash
python decoder.py compressed.lz77 --lz77 --output restored.bin
```

## Parameters

| Parameter | Meaning | Default |
|---|---|---|
| `--window` | window size | `4096` |
| `--lookahead` | lookahead buffer size | `18` |
| `--min-match` | minimum match length for LZSS | `3` |

## Tests and analysis

Run tests:

```bash
python -m pytest tests/test_lzss.py -v -s
```

Run analysis (LZSS vs LZ77 + entropy + histograms):

```bash
python tests/analysis.py
```

Outputs include:

- `analysis_results.csv`
- `analysis_results.txt` (if redirected)
- `histograms/`
