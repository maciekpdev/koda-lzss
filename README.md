# koda-lzss
Project for data compression classes implementing dynamic dictionary coding LZSS

.lzss File Format
--------------------------------------
  Bytes 0–1  : window_size    (uint16, big-endian)
  Byte  2    : lookahead_size (uint8)
  Byte  3    : min_match      (uint8)
  Bytes 4–7  : original_size  (uint32, big-endian)
  Bytes 8+   : Compressed bitstream

Bitstream Token Format
----------------------
  Flag bit = 0  →  Literal : next 8 bits = symbol
  Flag bit = 1  →  Pair    : offset (off_bits bits) + length (len_bits bits)
