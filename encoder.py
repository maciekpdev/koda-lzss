import argparse
import struct

WINDOW_SIZE = 4096
LOOKAHEAD_SIZE = 18
MIN_MATCH = 3


def offset_bits(window_size: int) -> int:
    return (window_size - 1).bit_length()


def length_bits(lookahead_size: int) -> int:
    return (lookahead_size - 1).bit_length()


class BitWriter:
    def __init__(self):
        self._buf = bytearray()
        self._byte = 0
        self._fill = 0
        self.bits = []
        self.debug_tokens = []
        self.decoded = bytearray()

    def write_bit(self, bit: int) -> None:
        bit = bit & 1
        self.bits.append(str(bit))

        self._byte = (self._byte << 1) | bit
        self._fill += 1

        if self._fill == 8:
            self._buf.append(self._byte)
            self._byte = 0
            self._fill = 0

    def write_bits(self, value: int, n: int) -> None:
        for i in range(n - 1, -1, -1):
            self.write_bit((value >> i) & 1)

    def add_literal(self, byte_val: int):
        self.decoded.append(byte_val)
        self.debug_tokens.append(
            f"[LITERAL] '{chr(byte_val)}' (0x{byte_val:02X})"
        )

    def add_pair(self, offset: int, length: int):
        start = len(self.decoded) - offset
        repeated = bytearray()

        for i in range(length):
            b = self.decoded[start + i]
            repeated.append(b)
            self.decoded.append(b)

        try:
            text = repeated.decode('utf-8')
        except:
            text = str(repeated)

        self.debug_tokens.append(
            f"[PAIR] offset={offset} length={length} (\"{text}\")"
        )

    def flush(self) -> bytes:
        if self._fill:
            self._byte <<= (8 - self._fill)
            self._buf.append(self._byte)
            self._byte = 0
            self._fill = 0
        return bytes(self._buf)

    def byte_groups(self) -> str:
        out = []
        for i in range(0, len(self.bits), 8):
            out.append(''.join(self.bits[i:i + 8]).ljust(8, '0'))
        return ' '.join(out)


def find_longest_match(data: bytes, current_pos: int,
                       window_size: int, lookahead_size: int):

    best_length = 0
    best_offset = 0

    start_window = max(0, current_pos - window_size)
    end_lookahead = min(current_pos + lookahead_size, len(data))

    for j in range(start_window, current_pos):
        length = 0
        while (
            length < lookahead_size
            and current_pos + length < end_lookahead
            and j + length < len(data)
            and data[j + length] == data[current_pos + length]
        ):
            length += 1

        if length > best_length:
            best_length = length
            best_offset = current_pos - j

    return best_offset, best_length


def lzss_encode(data: bytes,
                window_size=WINDOW_SIZE,
                lookahead_size=LOOKAHEAD_SIZE,
                min_match=MIN_MATCH):

    writer = BitWriter()

    off_bits = offset_bits(window_size)
    len_bits = length_bits(lookahead_size)

    i = 0
    n = len(data)

    n_literals = 0
    n_pairs = 0

    while i < n:
        offset, length = find_longest_match(
            data, i, window_size, lookahead_size
        )

        if length >= min_match:
            writer.write_bit(1)
            writer.write_bits(offset, off_bits)
            writer.write_bits(length, len_bits)

            writer.add_pair(offset, length)

            i += length
            n_pairs += 1
        else:
            writer.write_bit(0)
            writer.write_bits(data[i], 8)

            writer.add_literal(data[i])

            i += 1
            n_literals += 1

    return writer.flush(), writer, n_literals, n_pairs


def save_lzss(filename, compressed,
              window_size, lookahead_size,
              min_match, original_size):

    with open(filename, 'wb') as f:
        f.write(struct.pack('>HBB', window_size, lookahead_size, min_match))
        f.write(struct.pack('>I', original_size))
        f.write(compressed)


def parse_args():
    p = argparse.ArgumentParser(description="LZSS Encoder")

    p.add_argument("input")
    p.add_argument("--output", default="compressed.lzss")
    p.add_argument("--debug", action="store_true")

    p.add_argument("--window", type=int, default=WINDOW_SIZE,
                   help=f"Window size (default: {WINDOW_SIZE})")

    p.add_argument("--lookahead", type=int, default=LOOKAHEAD_SIZE,
                   help=f"Lookahead buffer size (default: {LOOKAHEAD_SIZE})")

    p.add_argument("--min-match", type=int, default=MIN_MATCH,
                   help=f"Minimum match length (default: {MIN_MATCH})")

    return p.parse_args()


def main():
    args = parse_args()

    with open(args.input, "rb") as f:
        data = f.read()

    compressed, writer, n_literals, n_pairs = lzss_encode(data)

    save_lzss(
        args.output,
        compressed,
        WINDOW_SIZE,
        LOOKAHEAD_SIZE,
        MIN_MATCH,
        len(data)
    )

    if args.debug:
        with open(args.output + ".debug.txt", "w") as f:
            f.write("=== LZSS TOKEN TRACE ===\n\n")
            for t in writer.debug_tokens:
                f.write(t + "\n")

            f.write("\n=== BYTE VIEW (bit groups) ===\n")
            f.write(writer.byte_groups())

    orig_size = len(data)
    comp_size = len(compressed)
    ratio = orig_size / comp_size if comp_size else float('inf')

    print("✔ Compression finished")
    print(f"  Input size:        {orig_size} B")
    print(f"  Output size:       {comp_size} B")
    print(f"  Compression ratio: {ratio:.3f}")
    print(f"  Space saving:      {1 - comp_size / orig_size:.1%}")
    print(f"  Literals:          {n_literals}")
    print(f"  Matches:           {n_pairs}")


if __name__ == "__main__":
    main()