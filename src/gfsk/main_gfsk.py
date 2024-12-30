# main.py
#!/usr/bin/env python3

import sys
import argparse

from dsp import gfsk_modulate, modulate

def parse_bitstream(input_source: str) -> list:
    """
    Parse the input bitstream from a string or file.
    input_source: 'str:<bitstring>' or 'file:<filepath>'
    Returns a list of booleans representing the bitstream.
    """
    if input_source.startswith("str:"):
        bitstr = input_source[4:]
        return [c == '1' for c in bitstr if c in ['0', '1']]
    elif input_source.startswith("file:"):
        filepath = input_source[5:]
        try:
            with open(filepath, 'r') as f:
                bitstr = f.read().strip()
                return [c == '1' for c in bitstr if c in ['0', '1']]
        except IOError:
            sys.stderr.write(f"Error reading bitstream file '{filepath}'\n")
            sys.exit(1)
    else:
        sys.stderr.write("Invalid input source. Use 'str:<bits>' or 'file:<filepath>'\n")
        sys.exit(1)

def usage():
    sys.stderr.write(
        "Usage: gfsk_modulator.py -i <input_source> [-o <output>] [-f <format>] "
        "[-b <baud_rate>] [-r <sample_rate>] [-d <freq_deviation>] [-t <bt>]\n"
        "   -i input_source  - input bitstream, 'str:<bits>' or 'file:<filepath>'\n"
        "   -o output        - output file (default stdout)\n"
        "   -f format        - output format: f32 (default), s8 (HackRF), pcm\n"
        "   -b baud_rate     - baud rate in symbols per second (default 1200)\n"
        "   -r sample_rate   - sample rate in Hz (default 48000)\n"
        "   -d freq_dev      - frequency deviation in Hz (default 750)\n"
        "   -t bt            - bandwidth-time product (default 0.3)\n"
        "   -v               - print debug info\n"
    )
    sys.exit(1)

def main():
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("-i", dest="input_source", type=str, required=True,
                        help="Input bitstream: 'str:<bits>' or 'file:<filepath>'")
    parser.add_argument("-o", dest="output", type=str, default=None,
                        help="Output file (default stdout)")
    parser.add_argument("-f", dest="fmt", type=str, default="f32",
                        help="Output format: f32 (default), s8 (HackRF), pcm")
    parser.add_argument("-b", dest="baud_rate", type=int, default=1200,
                        help="Baud rate in symbols per second (default 1200)")
    parser.add_argument("-r", dest="sample_rate", type=int, default=48000,
                        help="Sample rate in Hz (default 48000)")
    parser.add_argument("-d", dest="freq_deviation", type=float, default=750.0,
                        help="Frequency deviation in Hz (default 750)")
    parser.add_argument("-t", dest="bt", type=float, default=0.3,
                        help="Bandwidth-time product (default 0.3)")
    parser.add_argument("-v", dest="debug", action="store_true",
                        help="Print debug info")
    args, extra = parser.parse_known_args()

    # Parse bitstream
    bitstream = parse_bitstream(args.input_source)

    if args.debug:
        print(f"Bitstream length: {len(bitstream)} bits")

    # Perform GFSK modulation
    iq_samples = gfsk_modulate(
        bitstream=bitstream,
        baud_rate=args.baud_rate,
        sample_rate=args.sample_rate,
        freq_deviation=args.freq_deviation,
        bt=args.bt
    )

    # Determine output format
    iq_sf = args.fmt.lower()
    if iq_sf == "s8":
        out_fmt = "IQ_S8"
    elif iq_sf == "f32":
        out_fmt = "IQ_F32"
    elif iq_sf == "pcm":
        out_fmt = "PCM"
    else:
        sys.stderr.write(f"Incorrect sample format: {args.fmt}\n")
        sys.exit(1)

    # Open output file or use stdout
    fout = None
    if args.output:
        try:
            fout = open(args.output, "wb")
        except IOError:
            sys.stderr.write(f"Error creating output file '{args.output}'\n")
            sys.exit(1)
    else:
        # Default to stdout as binary
        fout = sys.stdout.buffer

    # Write I/Q samples
    modulate(iq_samples, out_fmt, fout)

    if fout is not sys.stdout.buffer:
        fout.close()

    if args.debug:
        print(f"Modulation complete. Output written to '{args.output if args.output else 'stdout'}'.")

if __name__ == "__main__":
    main()
