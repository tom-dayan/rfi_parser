# RFI Processing Tool

An intelligent web application for architects to upload RFIs (Request for Information) and specifications, then automatically analyze and respond to each RFI based on the specifications using AI.

## Features

- **Document Upload**: Support for PDF, DOCX, and text-based documents
- **AI-Powered Analysis**: Automatically analyze RFIs against specifications
- **Smart Status Detection**:
  - ✅ Accepted - RFI aligns with specifications
  - ❌ Rejected - RFI contradicts specifications
  - 💬 Comment - Needs clarification
  - 👥 Refer to Consultant - Requires expert consultation
- **Detailed Reporting**:
  - Reasons for non-accepted RFIs
  - Specification references that support decisions
  - Relevant quotes from specifications
  - Confidence scores
- **User-Friendly Interface**: Modern, responsive design built with React and TailwindCSS
- **Flexible AI Backend**: Choose from Google Gemini (recommended), local Ollama, or Claude API
- **RAG-Powered**: Vector search retrieves relevant specification sections for accurate responses

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

1. **Create a Project**: Enter a project name and configure your RFI, Submittal, and Specs folder paths
2. **Scan & Index**: Click "Scan & Index" to discover files and build the knowledge base from your specifications
3. **Process Documents**: Go to the Results tab and click "Process Documents" to analyze RFIs and Submittals against specs
4. **Review Results**: View AI responses with specification references and relevance scores
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
│   └── requirements.txt
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
