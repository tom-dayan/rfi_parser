#!/bin/bash
# OLILab - Setup Script for macOS/Linux
# This script installs all dependencies and configures the application

set -e

echo ""
echo "╔════════════════════════════════════════════════╗"
echo "║        OLILab - Setup              ║"
echo "║     Document Analysis & AI Assistant           ║"
echo "╚════════════════════════════════════════════════╝"
echo ""

# Get the script directory
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$( dirname "$SCRIPT_DIR" )"

cd "$PROJECT_ROOT"

echo "📁 Project root: $PROJECT_ROOT"
echo ""

# Check Python version
echo "🔍 Checking Python installation..."
PYTHON_CMD=""
for cmd in python3.13 python3.12 python3.11 python3.10 python3; do
    if command -v $cmd &> /dev/null; then
        version=$($cmd -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
        major=$(echo $version | cut -d. -f1)
        minor=$(echo $version | cut -d. -f2)
        if [ "$major" -ge 3 ] && [ "$minor" -ge 10 ]; then
            PYTHON_CMD=$cmd
            echo "   ✓ Found Python $version at $(which $cmd)"
            break
        fi
    fi
done

if [ -z "$PYTHON_CMD" ]; then
    echo ""
    echo "❌ ERROR: Python 3.10 or higher is required"
    echo ""
    echo "Please install Python:"
    echo "  - macOS: brew install python@3.12"
    echo "  - Ubuntu/Debian: sudo apt install python3.12"
    echo ""
    exit 1
fi

# Check for Node.js (for frontend)
echo "🔍 Checking Node.js installation..."
if command -v node &> /dev/null; then
    NODE_VERSION=$(node -v)
    echo "   ✓ Found Node.js $NODE_VERSION"
else
    echo "   ⚠ Node.js not found (optional, for frontend development)"
    echo "     Install from: https://nodejs.org/"
fi

# Create backend virtual environment
echo ""
echo "🔧 Setting up Python environment..."
if [ ! -d "backend/venv" ]; then
    echo "   Creating virtual environment..."
    $PYTHON_CMD -m venv backend/venv
    echo "   ✓ Virtual environment created"
else
    echo "   ✓ Virtual environment exists"
fi

# Activate and install dependencies
echo ""
echo "📦 Installing Python dependencies..."
source backend/venv/bin/activate
pip install --upgrade pip -q
pip install -r backend/requirements.txt -q
echo "   ✓ Python dependencies installed"

# Check for Tesseract (OCR)
echo ""
echo "🔍 Checking OCR dependencies..."
if command -v tesseract &> /dev/null; then
    TESSERACT_VERSION=$(tesseract --version 2>&1 | head -n1)
    echo "   ✓ Tesseract OCR: $TESSERACT_VERSION"
else
    echo "   ⚠ Tesseract OCR not found (recommended for PDF/image analysis)"
    echo "     Install with: brew install tesseract (macOS)"
    echo "                   sudo apt install tesseract-ocr (Ubuntu)"
fi

# Create .env file if it doesn't exist
if [ ! -f "backend/.env" ]; then
    echo ""
    echo "📝 Creating configuration file..."
    cat > backend/.env << 'EOF'
# OLILab Configuration

# AI Provider: ollama, claude, or gemini
AI_PROVIDER=claude
CLAUDE_API_KEY=your_api_key_here
# GEMINI_API_KEY=your_api_key_here

# Shared folder root for project discovery
# SHARED_FOLDERS_ROOT=/path/to/your/shared/folders

# Auto-index on startup (set to false for faster startup)
AUTO_INDEX_ON_STARTUP=false
EOF
    echo "   ✓ Created backend/.env (please edit with your API key)"
fi

# Setup frontend
echo ""
echo "🎨 Setting up frontend..."
cd "$PROJECT_ROOT/frontend"
if [ ! -d "node_modules" ] && command -v npm &> /dev/null; then
    npm install -q
    echo "   ✓ Frontend dependencies installed"
else
    echo "   ✓ Frontend ready"
fi

cd "$PROJECT_ROOT"

# Create start script
cat > start.sh << 'EOF'
#!/bin/bash
# Start OLILab

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

echo ""
echo "🚀 Starting OLILab..."
echo ""

# Start backend
echo "Starting backend server..."
cd backend
source venv/bin/activate
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000 &
BACKEND_PID=$!
cd ..

# Wait for backend
sleep 2

# Start frontend
echo "Starting frontend..."
cd frontend
npm run dev &
FRONTEND_PID=$!
cd ..

echo ""
echo "╔════════════════════════════════════════════════╗"
echo "║           OLILab Running           ║"
echo "╠════════════════════════════════════════════════╣"
echo "║  Frontend: http://localhost:5173              ║"
echo "║  Backend:  http://localhost:8000              ║"
echo "║  API Docs: http://localhost:8000/docs         ║"
echo "╚════════════════════════════════════════════════╝"
echo ""
echo "Press Ctrl+C to stop all services"

# Handle shutdown
trap "kill $BACKEND_PID $FRONTEND_PID 2>/dev/null; exit" SIGINT SIGTERM
wait
EOF
chmod +x start.sh

echo ""
echo "╔════════════════════════════════════════════════╗"
echo "║              Setup Complete! 🎉                ║"
echo "╚════════════════════════════════════════════════╝"
echo ""
echo "📋 Next Steps:"
echo ""
echo "   1. Edit configuration:"
echo "      nano backend/.env"
echo "      - Add your Claude API key"
echo "      - Set your shared folders path"
echo ""
echo "   2. Start the application:"
echo "      ./start.sh"
echo ""
echo "   3. Open in browser:"
echo "      http://localhost:5173"
echo ""
echo "   4. (Optional) Setup Claude Desktop integration:"
echo "      python scripts/setup_mcp.py"
echo ""
