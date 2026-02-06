# OLI Knowledge Base

An intelligent knowledge base and document analysis system for architecture firms. Analyze RFIs, submittals, and specifications with AI-powered assistance.

## Features

### Document Analysis
- **Smart Analysis**: AI-assisted spec discovery - select RFIs, AI finds relevant specs, you approve, and get quality responses (no pre-indexing required!)
- **AI-Powered RFI/Submittal Analysis**: Automatically analyze documents against project specifications
- **Smart Response Generation**: Draft responses with relevant spec references
- **Co-Pilot Mode**: Interactive AI assistant for refining responses
- **OCR Support**: Extract text from scanned documents and images

### Knowledge Base
- **Project Management**: Organize documents by project with auto-discovery
- **Semantic Search**: Find relevant information across all project documents  
- **Global Search**: Search across all projects from the dashboard
- **Ask OLI**: Chat with your project documents

### Claude Desktop Integration
- **MCP Server**: Connect your firm's shared folders to Claude Desktop
- **Seamless Workflow**: Start in the app, continue drafting in Claude
- **Smart Tools**: Access projects, RFIs, and specs directly from Claude

## Quick Start

### One-Line Setup

**macOS/Linux:**
```bash
git clone https://github.com/your-org/rfi_parser.git
cd rfi_parser
chmod +x scripts/setup.sh && ./scripts/setup.sh
```

**Windows:**
```powershell
git clone https://github.com/your-org/rfi_parser.git
cd rfi_parser
scripts\setup.bat
```

### What Gets Installed
- Python virtual environment with all dependencies
- Frontend dependencies (if Node.js is installed)
- Configuration file template

### Configuration

Edit `backend/.env` to add your API key:

```env
AI_PROVIDER=claude
CLAUDE_API_KEY=your_api_key_here

# Optional: Path to shared folders for project discovery
SHARED_FOLDERS_ROOT=/path/to/your/shared/folders
```

### Start the Application

**macOS/Linux:**
```bash
./start.sh
```

**Windows:**
```powershell
start.bat
```

Then open http://localhost:5173 in your browser.

## Manual Installation

If you prefer to set up manually or need more control:

## Architecture

```
┌─────────────────────┐
│  React Frontend     │
│  (Vite + TypeScript)│
└──────────┬──────────┘
           │ REST API
┌──────────▼──────────┐
│  FastAPI Backend    │
│  • Document Parsing │
│  • RAG Pipeline     │
│  • AI Orchestration │
└──────────┬──────────┘
           │
    ┌──────┼──────┐
    │      │      │
┌───▼──┐ ┌─▼──┐ ┌─▼────┐
│Gemini│ │Olla│ │Claude│
│(Free)│ │-ma │ │ API  │
└──────┘ └────┘ └──────┘
```

## Tech Stack

### Frontend
- React with TypeScript
- Vite for fast development
- TailwindCSS for styling
- React Query for state management
- Axios for API calls

### Backend
- FastAPI (Python)
- SQLAlchemy ORM
- SQLite database (upgradeable to PostgreSQL)
- Document parsers (PyPDF2, pdfplumber, python-docx)
- ChromaDB for vector storage (RAG)
- SentenceTransformers for embeddings
- **AI Providers**:
  - Google Gemini (recommended - free tier available)
  - Ollama for local AI processing
  - Anthropic Claude API

## Quick Start

### Prerequisites

- Node.js 18+ and npm
- Python 3.10+
- **One of the following AI providers**:
  - Google Gemini API key (recommended - free tier: 15 RPM, 1M tokens/day)
  - [Ollama](https://ollama.ai) installed (for local AI)
  - Anthropic Claude API key

### 1. Get a Gemini API Key (Recommended)

1. Go to [https://aistudio.google.com/app/apikey](https://aistudio.google.com/app/apikey)
2. Click "Create API Key"
3. Copy the key - you'll use it in step 2

> **Alternative**: If you prefer local AI, install [Ollama](https://ollama.ai) and run `ollama pull llama3.2`

### 2. Set Up Backend

```bash
cd backend

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Copy environment file and configure
cp .env.example .env

# Edit .env and set your AI provider:
# AI_PROVIDER=gemini
# GEMINI_API_KEY=your-api-key-here

# Run the server
uvicorn app.main:app --reload
```

Backend will be running at [http://localhost:8000](http://localhost:8000)

### 3. Set Up Frontend

```bash
cd frontend

# Install dependencies
npm install

# Copy environment file
cp .env.example .env

# Run the development server
npm run dev
```

Frontend will be running at [http://localhost:5173](http://localhost:5173)

## Usage

### Smart Analysis (Recommended - No Pre-Indexing!)

1. **Create a Project**: Enter a project name and configure your RFI/Submittal and Specs folder paths
2. **Open Project**: Click on your project from the dashboard
3. **Click "Smart Analysis"** (in the project header tabs)
4. **Select Documents**: Choose which RFIs/Submittals you want to analyze
5. **Review AI Suggestions**: AI automatically finds relevant spec files for each document
6. **Approve & Analyze**: Adjust spec selections if needed, then click "Start Analysis"
7. **Use Co-Pilot**: Click "Co-Pilot" on any result to refine the response with AI assistance

### Traditional Workflow

1. **Create a Project**: Enter a project name and configure your folder paths
2. **Scan & Index**: Click "Scan & Index" to discover files and build the knowledge base
3. **Process Documents**: Go to the Results tab and click "Process Documents"
4. **Review Results**: View AI responses with specification references
5. **Filter Results**: Filter by document type (RFI/Submittal) or status

## Switching AI Providers

Update `backend/.env` and restart the backend server. No code changes needed.

### Google Gemini (Recommended)
```env
AI_PROVIDER=gemini
GEMINI_API_KEY=your-api-key-here
```
Get your free API key at [https://aistudio.google.com/app/apikey](https://aistudio.google.com/app/apikey)

### Ollama (Local)
```env
AI_PROVIDER=ollama
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=llama3.2
```
Make sure Ollama is running with `ollama serve` and the model is pulled.

### Claude API
```env
AI_PROVIDER=claude
CLAUDE_API_KEY=your-api-key-here
```
Get your API key at [https://console.anthropic.com](https://console.anthropic.com)

## MCP Server Setup (Claude Desktop Integration)

The MCP server allows Claude Desktop to search and access your firm's shared folders.

### Quick Setup

**macOS/Linux:**
```bash
./scripts/setup.sh
python scripts/setup_mcp.py
```

**Windows:**
```cmd
scripts\setup.bat
python scripts\setup_mcp.py
```

This will:
1. Create a virtual environment with all dependencies
2. Configure Claude Desktop to use the MCP server
3. Set up access to your shared folders

See [docs/MCP_INTEGRATION.md](docs/MCP_INTEGRATION.md) for detailed instructions.

## Project Structure

```
rfi_parser/
├── frontend/              # React application
│   ├── src/
│   │   ├── components/   # UI components
│   │   ├── services/     # API client
│   │   └── types/        # TypeScript types
│   └── package.json
│
├── backend/              # Python FastAPI application
│   ├── app/
│   │   ├── routers/     # API endpoints
│   │   ├── services/    # Business logic
│   │   ├── models.py    # Database models
│   │   └── main.py      # App entry point
│   ├── mcp_server/      # MCP server for Claude Desktop
│   │   ├── server.py    # Main entry point
│   │   ├── tools/       # MCP tools (browse, search, content)
│   │   └── config.py    # Configuration
│   └── requirements.txt
│
├── scripts/              # Setup and utility scripts
│   ├── setup.sh         # macOS/Linux setup
│   ├── setup.bat        # Windows setup
│   └── setup_mcp.py     # MCP configuration wizard
│
├── docs/                 # Documentation
│   └── MCP_INTEGRATION.md
│
└── README.md
```

## API Documentation

Once the backend is running, visit:
- Swagger UI: [http://localhost:8000/docs](http://localhost:8000/docs)
- ReDoc: [http://localhost:8000/redoc](http://localhost:8000/redoc)

## Development

### Backend Development

```bash
cd backend
source venv/bin/activate

# Run with auto-reload
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Run tests (if implemented)
pytest
```

### Frontend Development

```bash
cd frontend

# Run development server
npm run dev

# Build for production
npm run build

# Preview production build
npm run preview
```

## Troubleshooting

### Ollama Issues

**Problem**: "Ollama service is not available"

**Solution**:
```bash
# Check if Ollama is running
ollama list

# If not running, start it
ollama serve

# Pull the model if not downloaded
ollama pull llama3.2
```

### Database Issues

**Problem**: Database errors on startup

**Solution**:
```bash
# Delete the database file and restart
cd backend
rm rfi_parser.db
# Restart the server - it will recreate the database
```

### File Upload Issues

**Problem**: "Failed to parse PDF"

**Solution**: Ensure your PDF is not password-protected and is a valid PDF file. Try converting to DOCX or plain text.

### OCR Issues (Windows)

**Problem**: "OCR failed - tesseract is not installed" or "poppler is not installed"

**Solution**: Install both Poppler and Tesseract:

```powershell
# Run PowerShell as Administrator
choco install poppler
choco install tesseract

# Or download manually:
# Poppler: https://github.com/osber/poppler/releases
# Tesseract: https://github.com/UB-Mannheim/tesseract/wiki

# Restart your terminal/IDE after installation
```

Make sure both are in your PATH by testing:
```cmd
pdftoppm -v
tesseract --version
```

### OCR Issues (macOS)

**Solution**:
```bash
brew install poppler tesseract
```

## Future Enhancements

- [x] Batch processing with progress tracking
- [x] Advanced specification indexing and search (RAG with vector embeddings)
- [x] Multi-project support
- [ ] User authentication and permissions
- [ ] Audit trail for decisions
- [ ] Export to various formats (PDF reports, Excel)
- [ ] Integration with project management tools

## License

MIT

## Support

For issues, questions, or contributions, please open an issue in the project repository.
