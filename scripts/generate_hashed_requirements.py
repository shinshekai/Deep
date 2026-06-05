#!/usr/bin/env python3
"""Generate requirements files with SHA256 hashes for supply-chain security.

Usage:
    python scripts/generate_hashed_requirements.py

This regenerates requirements.txt and requirements-dev.txt with --generate-hashes,
then verifies them with --require-hashes.
"""

import subprocess
import sys
from pathlib import Path


def run(cmd: list[str], check: bool = True) -> subprocess.CompletedProcess:
    """Run a command and return the result."""
    print(f"  $ {' '.join(cmd)}")
    result = subprocess.run(cmd, capture_output=True, text=True)
    if check and result.returncode != 0:
        print(f"ERROR: {result.stderr}", file=sys.stderr)
        sys.exit(1)
    return result


def main():
    backend_dir = Path(__file__).resolve().parent.parent / "backend"
    if not backend_dir.exists():
        print(f"ERROR: backend directory not found at {backend_dir}", file=sys.stderr)
        sys.exit(1)

    print("=== Generating hashed requirements ===\n")

    # Generate production requirements with hashes
    print("[1/3] Generating production requirements with hashes...")
    run([
        sys.executable, "-m", "piptools", "compile",
        "--generate-hashes",
        "--output-file=requirements-hashes.txt",
        "--strip-extras",
        "--upgrade",
        "pyproject.toml",
    ], check=False)

    # Generate dev requirements with hashes
    print("\n[2/3] Generating dev requirements with hashes...")
    run([
        sys.executable, "-m", "piptools", "compile",
        "--generate-hashes",
        "--extra=dev",
        "--output-file=requirements-dev-hashes.txt",
        "--strip-extras",
        "--upgrade",
        "pyproject.toml",
    ], check=False)

    # Verify hashed requirements
    print("\n[3/3] Verifying hashed requirements...")
    result = run([
        sys.executable, "-m", "pip", "install",
        "--require-hashes",
        "--dry-run",
        "-r", "requirements-hashes.txt",
    ], check=False)

    if result.returncode == 0:
        print("\n=== SUCCESS ===")
        print("Hashed requirements files generated:")
        print("  - backend/requirements-hashes.txt")
        print("  - backend/requirements-dev-hashes.txt")
        print("\nTo install with hash verification:")
        print("  pip install --require-hashes -r requirements-hashes.txt")
    else:
        print("\n=== WARNING ===")
        print("Hash verification had issues. Check the output above.")
        print("The files were generated but may need manual review.")


if __name__ == "__main__":
    main()
