# RFI Processing Tool - Deployment Guide

This guide explains how to deploy the RFI Processing Tool for internal use within your firm.

## Prerequisites

- **Docker** and **Docker Compose** installed on the server
- Access to the server from your firm's network (or VPN)
- A folder containing your project files (RFIs, Submittals, Specs)

## Quick Start

### 1. Clone the Repository

```bash
git clone <repository-url>
cd rfi_parser
```

### 2. Configure Environment

Create a `.env` file in the root directory:

```bash
# AI Provider: Choose 'ollama' for local or 'gemini' for Google AI
AI_PROVIDER=ollama

# For Ollama (runs locally - recommended for internal use)
OLLAMA_BASE_URL=http://host.docker.internal:11434
OLLAMA_MODEL=llama3.2

# For Gemini (optional - requires API key)
# GEMINI_API_KEY=your-api-key-here
# GEMINI_MODEL=gemini-2.0-flash-lite
```

### 3. Start with Ollama (Recommended)

If using Ollama for local AI processing:

```bash
# Install Ollama on the host machine (not in Docker)
curl https://ollama.ai/install.sh | sh

# Pull the required model
ollama pull llama3.2

# Start Ollama service
ollama serve
```

### 4. Launch the Application

```bash
docker-compose up -d
```

The application will be available at:
- **Frontend**: http://your-server-ip:5173
- **Backend API**: http://your-server-ip:8000

### 5. Access from Other Computers

Staff members can access the tool by:
1. Connecting to your firm's VPN (if accessing remotely)
2. Opening a browser to `http://<server-internal-ip>:5173`

## Configuration Options

### AI Provider

Choose between local AI (Ollama) or cloud AI (Gemini):

| Provider | Pros | Cons |
|----------|------|------|
| Ollama | Free, runs locally, no data leaves network | Requires decent CPU/GPU |
| Gemini | Better quality, fast | Requires API key, data goes to Google |

### Volume Mounts

The docker-compose.yml mounts these volumes:
- `./data` - Database and application data (persisted)
- Project folders can be mounted for direct access

### Ports

Default ports:
- `5173` - Frontend web interface
- `8000` - Backend API

To change ports, edit `docker-compose.yml`:
```yaml
ports:
  - "8080:80"  # Access frontend on port 8080 instead
```

## Maintenance

### View Logs

```bash
# All services
docker-compose logs -f

# Backend only
docker-compose logs -f backend

# Frontend only
docker-compose logs -f frontend
```

### Restart Services

```bash
docker-compose restart
```

### Update Application

```bash
git pull
docker-compose build
docker-compose up -d
```

### Backup Data

The database is stored in `./data/rfi_parser.db`. To backup:

```bash
cp ./data/rfi_parser.db ./backups/rfi_parser_$(date +%Y%m%d).db
```

## Troubleshooting

### "Cannot connect to Ollama"

Ensure Ollama is running on the host machine:
```bash
ollama serve
```

And that the `OLLAMA_BASE_URL` uses `host.docker.internal`:
```
OLLAMA_BASE_URL=http://host.docker.internal:11434
```

### "AI processing failed"

1. Check the backend logs: `docker-compose logs backend`
2. Verify your AI provider is configured correctly
3. For Gemini: ensure your API key is valid

### "Cannot access from another computer"

1. Check firewall settings on the server
2. Ensure VPN connection is active (for remote access)
3. Verify the server IP address

## Security Notes

- This application is designed for **internal use only**
- Do not expose ports 5173 or 8000 to the public internet
- Use your existing VPN infrastructure for remote access
- All project data stays within your network (when using Ollama)

## System Requirements

- **Minimum**: 4GB RAM, 2 CPU cores
- **Recommended**: 8GB RAM, 4 CPU cores (especially for Ollama)
- **Storage**: 10GB+ depending on document volume
