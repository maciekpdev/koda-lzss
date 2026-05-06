# koda-lzss

Implementation of the **LZSS (Lempel–Ziv–Storer–Szymanski)** compression algorithm  
created for data compression classes.

This project uses a **dynamic dictionary (sliding window)** to encode repeated patterns efficiently.

---

# 🚀 Overview

LZSS works by replacing repeated data with references to earlier occurrences.

Instead of storing:
AAAAAA

it stores:
A + (offset=1, length=5)

This reduces redundancy and improves compression — especially for repetitive data.

---

# 🗂️ File Format (`.lzss`)

Each compressed file consists of a **header** followed by a **bitstream**.

## 📌 Header (8 bytes)

| Bytes | Field            | Type     | Description |
|------|-----------------|----------|------------|
| 0–1  | `window_size`   | uint16   | Sliding window size |
| 2    | `lookahead_size`| uint8    | Lookahead buffer size |
| 3    | `min_match`     | uint8    | Minimum match length |
| 4–7  | `original_size` | uint32   | Size of original data (bytes) |

All multi-byte values are stored in **big-endian** format.

---

## 📊 Bitstream (data section)

After the header, the file contains a **bit-level encoded stream of tokens**.

There are two types of tokens:

---

### 🔹 Literal

0 [8 bits]

- `0` → flag indicating literal  
- next 8 bits → raw byte (ASCII or binary)

Example:
0 01000001 → 'A'

---

### 🔹 Match (Pair)

1 [offset] [length]

- `1` → flag indicating match  
- `offset` → distance backwards in the window  
- `length` → number of bytes to copy  

Bit sizes depend on parameters:

offset_bits = ceil(log2(window_size))  
length_bits = ceil(log2(lookahead_size))

Example:
1 000000000001 00101  
→ offset = 1  
→ length = 5  

---

# 🧠 How decoding works

When a match is encountered:

1. Go back `offset` bytes in already decoded data  
2. Copy `length` bytes from that position  
3. Append them to output  

This supports **overlapping matches**, e.g.:

offset=1, length=5 → AAAAA

---

# ⚙️ Parameters

| Parameter        | Description |
|------------------|------------|
| `window_size`    | How far back we can search for matches |
| `lookahead_size` | Maximum match length |
| `min_match`      | Minimum length to encode as a match |

---

# 🧪 Usage example

python encoder.py input.txt --output file.lzss --debug

Optional tuning:

python encoder.py input.txt --window 8192 --lookahead 32 --min-match 4

---

# 🔍 Debug mode

With `--debug`, the encoder generates a human-readable file:

[LITERAL] 'A'  
[PAIR] offset=1 length=5 ("AAAAA")

Plus a bit-level view:

00100000 11000000 ...

