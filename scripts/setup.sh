#!/bin/bash
# Cross-platform setup script for macOS/Linux

set -e

echo ""
echo "=============================================="
echo "RFI Parser - MCP Server Setup"
echo "=============================================="
echo ""

# Get the script directory
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$( dirname "$SCRIPT_DIR" )"

cd "$PROJECT_ROOT"

echo "Project root: $PROJECT_ROOT"
echo ""

# Check Python version
PYTHON_CMD=""
for cmd in python3.13 python3.12 python3.11 python3.10 python3; do
    if command -v $cmd &> /dev/null; then
        version=$($cmd -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
        major=$(echo $version | cut -d. -f1)
        minor=$(echo $version | cut -d. -f2)
        if [ "$major" -ge 3 ] && [ "$minor" -ge 10 ]; then
            PYTHON_CMD=$cmd
            echo "Found Python $version at $(which $cmd)"
            break
        fi
    fi
done

if [ -z "$PYTHON_CMD" ]; then
    echo "ERROR: Python 3.10 or higher is required"
    echo "Please install Python 3.10+ and try again"
    exit 1
fi

# Create virtual environment if it doesn't exist
if [ ! -d "venv" ]; then
    echo ""
    echo "Creating virtual environment..."
    $PYTHON_CMD -m venv venv
    echo "Virtual environment created at: $PROJECT_ROOT/venv"
fi

# Activate virtual environment
echo ""
echo "Activating virtual environment..."
source venv/bin/activate

# Upgrade pip
echo ""
echo "Upgrading pip..."
pip install --upgrade pip

# Install requirements
echo ""
echo "Installing dependencies..."
pip install -r backend/requirements.txt

echo ""
echo "=============================================="
echo "Setup complete!"
echo "=============================================="
echo ""
echo "Next steps:"
echo "  1. Run the MCP setup: python scripts/setup_mcp.py"
echo "  2. Or manually configure Claude Desktop"
echo ""
echo "To activate the virtual environment later:"
echo "  source venv/bin/activate"
echo ""
