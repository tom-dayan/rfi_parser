# MCP Server Integration Guide

This guide explains how to connect the Firm Knowledge Base MCP server to various AI clients including Claude Desktop, Cursor IDE, and custom applications.

## Table of Contents

1. [Overview](#overview)
2. [Prerequisites](#prerequisites)
3. [Claude Desktop Setup](#claude-desktop-setup)
4. [Cursor IDE Setup](#cursor-ide-setup)
5. [Custom Application Integration](#custom-application-integration)
6. [Configuration Options](#configuration-options)
7. [Security Considerations](#security-considerations)
8. [Troubleshooting](#troubleshooting)

---

## Overview

The MCP (Model Context Protocol) server exposes your firm's shared folders to AI assistants, allowing them to:

- **Browse folders** - Navigate the file structure
- **Search files** - Find documents by name, type, or content
- **Read content** - Extract text from PDFs, Word docs, and other files
- **Analyze drawings** - Get metadata from CAD files

The server runs on your local machine or internal server and communicates with AI clients using the MCP protocol.

---

## Prerequisites

### Software Requirements

- Python 3.10 or higher
- pip (Python package manager)

### Installation

1. **Clone or download the repository**

2. **Create a virtual environment (recommended):**

   **macOS/Linux:**
   ```bash
   cd rfi_parser
   python3 -m venv venv
   source venv/bin/activate
   ```

   **Windows (PowerShell):**
   ```powershell
   cd rfi_parser
   python -m venv venv
   .\venv\Scripts\Activate.ps1
   ```

   **Windows (Command Prompt):**
   ```cmd
   cd rfi_parser
   python -m venv venv
   venv\Scripts\activate.bat
   ```

3. **Install dependencies:**

   **macOS/Linux:**
   ```bash
   pip install -r backend/requirements.txt
   ```

   **Windows:**
   ```powershell
   pip install -r backend\requirements.txt
   ```

4. **Verify installation:**
   ```bash
   python -c "import mcp; print('MCP installed successfully')"
   ```

> **Note for macOS users:** If you see "externally-managed-environment" error, you must use a virtual environment as shown above.

---

## Claude Desktop Setup

### Automatic Setup

Run the setup script:

```bash
python scripts/setup_mcp.py
```

This will:
1. Detect your OS and Claude Desktop location
2. Ask for your shared folder paths
3. Update the Claude Desktop configuration

### Manual Setup

1. **Find your Claude Desktop config file:**

   | OS | Location |
   |---|---|
   | macOS | `~/Library/Application Support/Claude/claude_desktop_config.json` |
   | Windows | `%APPDATA%\Claude\claude_desktop_config.json` |
   | Linux | `~/.config/Claude/claude_desktop_config.json` |

2. **Add the MCP server configuration:**

   **macOS/Linux:**
   ```json
   {
     "mcpServers": {
       "firm-knowledge-base": {
         "command": "/path/to/python",
         "args": ["/path/to/rfi_parser/backend/mcp_server/server.py"],
         "env": {
           "SHARED_FOLDERS_ROOT": "/Volumes/Shared/Projects,/Users/Shared/Drawings",
           "ALLOWED_EXTENSIONS": ".pdf,.docx,.dwg,.dxf,.txt"
         }
       }
     }
   }
   ```

   **Windows:**
   ```json
   {
     "mcpServers": {
       "firm-knowledge-base": {
         "command": "C:\\Python312\\python.exe",
         "args": ["C:\\Projects\\rfi_parser\\backend\\mcp_server\\server.py"],
         "env": {
           "SHARED_FOLDERS_ROOT": "\\\\server\\SharedFolders\\Projects,C:\\SharedDrive",
           "ALLOWED_EXTENSIONS": ".pdf,.docx,.dwg,.dxf,.txt"
         }
       }
     }
   }
   ```

3. **Restart Claude Desktop**

4. **Verify the connection:**
   - Look for the MCP tools icon (hammer/wrench) in Claude's input area
   - Try asking: "List the shared folder roots"

### Remote Server Setup (via SSH)

If the MCP server runs on a different machine:

```json
{
  "mcpServers": {
    "firm-knowledge-base": {
      "command": "ssh",
      "args": [
        "user@internal-server.company.com",
        "python3 /opt/rfi_parser/backend/mcp_server/server.py"
      ],
      "env": {
        "SHARED_FOLDERS_ROOT": "/mnt/shared/projects"
      }
    }
  }
}
```

---

## Cursor IDE Setup

### Workspace Configuration

Create `.cursor/mcp.json` in your workspace:

```json
{
  "servers": {
    "firm-knowledge-base": {
      "command": "python",
      "args": ["backend/mcp_server/server.py"],
      "cwd": "${workspaceFolder}",
      "env": {
        "SHARED_FOLDERS_ROOT": "/path/to/shared/folders"
      }
    }
  }
}
```

### Global Configuration

For all workspaces, add to your Cursor settings.

---

## Custom Application Integration

### Python Client Example

```python
import asyncio
from mcp import ClientSession, StdioServerParameters

async def search_drawings():
    """Search for door details in the knowledge base."""
    
    server = StdioServerParameters(
        command="python",
        args=["backend/mcp_server/server.py"],
        env={
            "SHARED_FOLDERS_ROOT": "/path/to/shared/folders"
        }
    )
    
    async with ClientSession(server) as session:
        # Initialize the session
        await session.initialize()
        
        # List available tools
        tools = await session.list_tools()
        print("Available tools:", [t.name for t in tools])
        
        # Search for drawings
        result = await session.call_tool(
            "search_files",
            {
                "query": "*door*detail*",
                "file_types": ["pdf", "dwg"]
            }
        )
        print(result)

asyncio.run(search_drawings())
```

### HTTP/SSE Integration (Web Apps)

For web applications, use the SSE transport:

```bash
python backend/mcp_server/server.py --transport sse --port 8001
```

Then connect from your frontend:

```javascript
const eventSource = new EventSource('http://localhost:8001/mcp/sse');

eventSource.onmessage = (event) => {
  const data = JSON.parse(event.data);
  console.log('MCP response:', data);
};
```

---

## Configuration Options

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `SHARED_FOLDERS_ROOT` | Comma-separated paths to shared folders | (none - all paths allowed) |
| `ALLOWED_EXTENSIONS` | Comma-separated file extensions | `.pdf,.docx,.dwg,.dxf,.txt,...` |
| `MCP_MAX_FILE_SIZE` | Max file size to parse (bytes) | `52428800` (50MB) |
| `MCP_CACHE_TTL` | Content cache lifetime (seconds) | `86400` (24 hours) |
| `MCP_LOG_LEVEL` | Logging level | `INFO` |
| `MCP_LOG_FILE` | Path to log file | (console only) |

### Available Tools

#### File System Tools

| Tool | Description |
|------|-------------|
| `browse_folder` | List contents of a directory |
| `list_shared_roots` | Show configured shared folder roots |
| `search_files` | Search files by name pattern |
| `search_drawings` | Search specifically for drawing files |
| `get_file_content` | Get parsed text content of a file |
| `get_file_metadata` | Get file metadata without parsing |

#### OLI Knowledge Base Tools

These tools provide access to the OLI project data and AI analysis:

| Tool | Description |
|------|-------------|
| `list_projects` | List all projects in the OLI Knowledge Base |
| `get_project_info` | Get detailed information about a specific project |
| `get_rfi_context` | Get full context for an RFI/Submittal (content, analysis, spec references) |
| `search_specs` | Search indexed specifications using semantic search |
| `get_analysis_results` | Get AI analysis results for a project |

#### Example Usage in Claude Desktop

Once configured, you can ask Claude things like:

- "List all my OLI projects"
- "Show me the details for project 'Building A Renovation'"
- "Get the context for RFI #92 so I can help draft a response"
- "Search the specs for waterproofing requirements"
- "What are the analysis results for project 5?"

---

## Security Considerations

### Network Security

- The MCP server should only run on your internal network
- Use your existing VPN for remote access
- Never expose the server directly to the internet

### Path Restrictions

Always configure `SHARED_FOLDERS_ROOT` in production:

```bash
# Good - restricts access to specific folders
SHARED_FOLDERS_ROOT=/Volumes/Shared/Projects,/Volumes/Shared/Drawings

# Bad - allows access to entire file system
SHARED_FOLDERS_ROOT=
```

### File Type Restrictions

Limit parseable file types to prevent accidental exposure:

```bash
ALLOWED_EXTENSIONS=.pdf,.docx,.txt,.md,.dwg,.dxf
```

### Audit Logging

Enable logging to track file access:

```bash
MCP_LOG_LEVEL=INFO
MCP_LOG_FILE=/var/log/mcp_server.log
```

---

## Troubleshooting

### Claude Desktop Not Showing MCP Tools

1. **Check the config file syntax:**
   ```bash
   # macOS
   cat ~/Library/Application\ Support/Claude/claude_desktop_config.json | python -m json.tool
   
   # Windows PowerShell
   Get-Content "$env:APPDATA\Claude\claude_desktop_config.json" | python -m json.tool
   ```

2. **Check Claude logs:**
   - macOS: `~/Library/Logs/Claude/mcp*.log`
   - Windows: `%APPDATA%\Claude\logs\`

3. **Test the server manually:**
   ```bash
   python scripts/run_mcp_server.py --test
   ```

### Permission Denied Errors

1. Verify the server process has read access to shared folders
2. On macOS, grant Full Disk Access in System Preferences
3. On Windows, run as administrator if accessing network shares

### Slow File Parsing

First access to a file requires parsing (can take seconds for large PDFs). Subsequent access uses cache.

To warm the cache:
```python
# Pre-parse commonly accessed files
await session.call_tool("get_file_content", {"path": "/path/to/important/file.pdf"})
```

### Connection Timeouts

For large file systems, increase the search timeout:
```bash
MCP_SEARCH_TIMEOUT=60  # seconds
```

---

## Getting Help

- Check the logs: `MCP_LOG_LEVEL=DEBUG`
- Open an issue on the repository
- Contact your IT administrator for network/permission issues
