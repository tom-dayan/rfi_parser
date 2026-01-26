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
- **Flexible AI Backend**: Start with local Ollama, easily switch to Claude API

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
│  • AI Orchestration │
└──────────┬──────────┘
           │
    ┌──────┴──────┐
    │             │
┌───▼────┐   ┌───▼────┐
│ Ollama │   │ Claude │
│(Local) │   │  API   │
└────────┘   └────────┘
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
- Ollama for local AI processing
- Anthropic SDK for Claude API support

## Quick Start

### Prerequisites

- Node.js 18+ and npm
- Python 3.10+
- [Ollama](https://ollama.ai) installed (for local AI)

### 1. Install Ollama (if not already installed)

```bash
# macOS/Linux
curl https://ollama.ai/install.sh | sh

# Or download from https://ollama.ai

# Pull the model
ollama pull llama3.2
```

### 2. Set Up Backend

```bash
cd backend

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Copy environment file
cp .env.example .env

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

1. **Upload Specifications**: Go to the "Upload Documents" tab and upload your specification documents
2. **Upload RFIs**: Upload your RFI documents in the same tab
3. **Process RFIs**: Navigate to the "Results Dashboard" and click "Process All RFIs"
4. **Review Results**: View the analysis results with status, reasons, and specification references
5. **Filter Results**: Filter by status (Accepted, Rejected, Comment, Referred)

## Switching to Claude API

To use Claude API instead of Ollama:

1. Get your API key from [https://console.anthropic.com](https://console.anthropic.com)
2. Update `backend/.env`:
   ```
   AI_PROVIDER=claude
   CLAUDE_API_KEY=your_api_key_here
   ```
3. Restart the backend server

That's it! No code changes needed.

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

- [ ] Batch processing with progress tracking
- [ ] Advanced specification indexing and search
- [ ] Multi-project support
- [ ] User authentication and permissions
- [ ] Audit trail for decisions
- [ ] Export to various formats (PDF reports, Excel)
- [ ] Integration with project management tools

## License

MIT

## Support

For issues, questions, or contributions, please open an issue in the project repository.
