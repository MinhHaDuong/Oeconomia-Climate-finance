"""Shared I/O argument parsing for pipeline scripts.

Provides a common --input / --output interface so the Makefile can pass
paths to scripts via pattern rules, and scripts become testable with
fixture data.

Usage in a script::

    from script_io_args import parse_io_args, validate_io

    def main():
        args, extra = parse_io_args()
        validate_io(output=args.output, inputs=args.input)
        # ... use args.output for save path, args.input for data paths
"""

import argparse
import os


def parse_io_args(argv=None):
    """Parse --input and --output arguments, pass through the rest.

    Parameters
    ----------
    argv : list[str] | None
        Argument list (defaults to sys.argv[1:]).

    Returns
    -------
    (args, extra) : tuple
        args.output : str (required)
        args.input : list[str] | None (optional, nargs="+")
        extra : list[str] — remaining args for script-specific parsing
    """
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument(
        "--output", required=True,
        help="Output file path (required)",
    )
    parser.add_argument(
        "--input", nargs="+", default=None,
        help="Input file path(s) (optional — scripts may use default data)",
    )
    return parser.parse_known_args(argv)


def validate_io(output, inputs=None):
    """Validate that output directory exists and input files are readable.

    Parameters
    ----------
    output : str
        Output file path. Its parent directory must exist.
    inputs : list[str] | None
        Input file paths. Each must exist.

    Raises
    ------
    FileNotFoundError
        If output directory or any input file is missing.
    """
    out_dir = os.path.dirname(output)
    if out_dir and not os.path.isdir(out_dir):
        raise FileNotFoundError(
            f"Output directory does not exist: {out_dir}"
        )
    if inputs:
        for path in inputs:
            if not os.path.exists(path):
                raise FileNotFoundError(f"Input file not found: {path}")
