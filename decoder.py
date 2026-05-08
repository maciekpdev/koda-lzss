import argparse
import struct
import sys

class BitReader:
    def __init__(self, data: bytes):
        self.data = data
        self.byte_idx = 0
        self.bit_idx = 7  

    def read_bit(self) -> int:
        if self.byte_idx >= len(self.data):
            raise EOFError("Unexpected end of data stream.")
        
        bit = (self.data[self.byte_idx] >> self.bit_idx) & 1
        
        if self.bit_idx == 0:
            self.bit_idx = 7
            self.byte_idx += 1
        else:
            self.bit_idx -= 1
            
        return bit

    def read_bits(self, n: int) -> int:
        value = 0
        for _ in range(n):
            value = (value << 1) | self.read_bit()
        return value


def lzss_decode(compressed_data: bytes) -> bytes:
    
    header_format = '>HBB'
    header_size = struct.calcsize(header_format)
    
    if len(compressed_data) < header_size + 4:
        raise ValueError("File is too small, missing complete header.")

    window_size, lookahead_size, min_match = struct.unpack(
        header_format, compressed_data[:header_size]
    )
    original_size = struct.unpack('>I', compressed_data[header_size:header_size + 4])[0]
    
    bitstream = compressed_data[header_size + 4:]
    
    off_bits = (window_size - 1).bit_length()
    len_bits = (lookahead_size - 1).bit_length()

    reader = BitReader(bitstream)
    decoded = bytearray()

    while len(decoded) < original_size:
        try:
            flag = reader.read_bit()
        except EOFError:
            break

        if flag == 1:
            
            offset = reader.read_bits(off_bits)
            length = reader.read_bits(len_bits)
           
            if offset == 0:
                print("Warning: Read offset equal to 0. The encoder likely truncated bits.", file=sys.stderr)
                offset = window_size - 1  
                
            start = len(decoded) - offset
            
            for i in range(length):
                if start + i < 0:
                    decoded.append(0) 
                else:
                    decoded.append(decoded[start + i])
        else:
            
            literal = reader.read_bits(8)
            decoded.append(literal)

    return bytes(decoded)


def parse_args():
    p = argparse.ArgumentParser(description="LZSS Decoder")
    p.add_argument("input", help="Input file (.lzss)")
    p.add_argument("--output", default="decoded.txt", help="Output file for decompressed data")
    return p.parse_args()


def main():
    args = parse_args()

    try:
        with open(args.input, "rb") as f:
            compressed = f.read()
    except FileNotFoundError:
        print(f"Error: File '{args.input}' not found.")
        sys.exit(1)

    print(f"Starting decompression of file: {args.input}")
    
    decoded_data = lzss_decode(compressed)

    with open(args.output, "wb") as f:
        f.write(decoded_data)

    print("Decompression finished")
    print(f"  Input size:        {len(compressed)} B")
    print(f"  Output size:       {len(decoded_data)} B")
    print(f"  Saved to:          {args.output}")

if __name__ == "__main__":
    main()