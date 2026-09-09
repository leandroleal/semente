"""Semente CLI — thin entry points for running an app's interfaces.

Usage:
    semente streamlit   # run the Streamlit chat UI (reads SEMENTE_MANIFEST)
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


def _streamlit_webapp() -> Path:
    return Path(__file__).parent / "interfaces" / "streamlit" / "streamlit_webapp.py"


def run_streamlit() -> None:
    webapp = _streamlit_webapp()
    subprocess.run([sys.executable, "-m", "streamlit", "run", str(webapp)])


def main() -> None:
    parser = argparse.ArgumentParser(prog="semente", description="Semente app runner")
    sub = parser.add_subparsers(dest="command")

    sub.add_parser("streamlit", help="Run the Streamlit chat interface")

    args = parser.parse_args()
    if args.command == "streamlit":
        run_streamlit()
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
