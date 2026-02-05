#!/usr/bin/env python3
"""
Run the MCP Server directly.

This script is a convenience wrapper to run the MCP server
from anywhere. Use this for testing or when you want to run
the server manually.

Usage:
    python scripts/run_mcp_server.py [options]

Options:
    --test          Run in test mode with verbose logging
    --folders PATH  Set shared folders root (comma-separated)

Example:
    python scripts/run_mcp_server.py --test
    python scripts/run_mcp_server.py --folders /path/to/shared,/another/path
"""

import argparse
import os
import sys
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description="Run MCP Server")
    parser.add_argument(
        "--test",
        action="store_true",
        help="Run in test mode with verbose logging",
    )
    parser.add_argument(
        "--folders",
        type=str,
        help="Shared folders root (comma-separated paths)",
    )
    parser.add_argument(
        "--extensions",
        type=str,
        default=".pdf,.docx,.doc,.txt,.md,.dwg,.dxf,.png,.jpg,.jpeg,.gif",
        help="Allowed file extensions (comma-separated)",
    )
    args = parser.parse_args()

    # Set environment variables
    if args.test:
        os.environ["MCP_LOG_LEVEL"] = "DEBUG"
        print("Running in test mode with DEBUG logging", file=sys.stderr)

    if args.folders:
        os.environ["SHARED_FOLDERS_ROOT"] = args.folders
        print(f"Using shared folders: {args.folders}", file=sys.stderr)

    os.environ["ALLOWED_EXTENSIONS"] = args.extensions

    # Add backend to path and run server
    script_dir = Path(__file__).parent.resolve()
    backend_dir = script_dir.parent / "backend"
    mcp_server_dir = backend_dir / "mcp_server"

    sys.path.insert(0, str(backend_dir))
    sys.path.insert(0, str(mcp_server_dir))

    # Import and run
    from mcp_server.server import main as server_main
    server_main()


if __name__ == "__main__":
    main()
