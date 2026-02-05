#!/usr/bin/env python3
"""
Cross-Platform MCP Server Setup Script

This script helps set up the MCP server for use with Claude Desktop
and other MCP clients. Works on Windows, macOS, and Linux.

Usage:
    python scripts/setup_mcp.py

What it does:
    1. Detects your operating system
    2. Creates/checks virtual environment
    3. Finds the Claude Desktop config location
    4. Adds the MCP server configuration
    5. Provides instructions for shared folder setup
"""

import json
import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path


def get_os_info():
    """Get information about the current OS."""
    system = platform.system().lower()
    if system == "darwin":
        return "macos", "macOS"
    elif system == "windows":
        return "windows", "Windows"
    else:
        return "linux", "Linux"


def get_claude_config_path():
    """Get the Claude Desktop config path for the current OS."""
    os_type, _ = get_os_info()

    if os_type == "macos":
        return Path.home() / "Library" / "Application Support" / "Claude" / "claude_desktop_config.json"
    elif os_type == "windows":
        appdata = os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming")
        return Path(appdata) / "Claude" / "claude_desktop_config.json"
    else:  # Linux
        return Path.home() / ".config" / "Claude" / "claude_desktop_config.json"


def get_project_root():
    """Get the project root directory."""
    return Path(__file__).parent.parent.resolve()


def get_venv_python():
    """Get the Python executable from the virtual environment."""
    os_type, _ = get_os_info()
    project_root = get_project_root()
    
    if os_type == "windows":
        venv_python = project_root / "venv" / "Scripts" / "python.exe"
    else:
        venv_python = project_root / "venv" / "bin" / "python"
    
    return venv_python


def get_python_path():
    """Get the Python executable path (prefer venv if available)."""
    venv_python = get_venv_python()
    if venv_python.exists():
        return str(venv_python)
    return sys.executable


def get_server_path():
    """Get the MCP server script path."""
    project_root = get_project_root()
    server_path = project_root / "backend" / "mcp_server" / "server.py"
    return server_path.resolve()


def create_venv_if_needed():
    """Create virtual environment if it doesn't exist."""
    project_root = get_project_root()
    venv_path = project_root / "venv"
    os_type, os_name = get_os_info()
    
    if venv_path.exists():
        print(f"  [OK] Virtual environment exists at: {venv_path}")
        return True
    
    print(f"\nNo virtual environment found at: {venv_path}")
    create = input("Create virtual environment? (y/n): ").lower().strip()
    
    if create != "y":
        print("Skipping virtual environment creation.")
        print("Warning: Dependencies may not be installed correctly.")
        return False
    
    print("Creating virtual environment...")
    try:
        subprocess.run([sys.executable, "-m", "venv", str(venv_path)], check=True)
        print(f"  [OK] Created virtual environment at: {venv_path}")
        
        # Install requirements
        print("\nInstalling dependencies...")
        venv_python = get_venv_python()
        pip_cmd = [str(venv_python), "-m", "pip", "install", "-r", 
                   str(project_root / "backend" / "requirements.txt")]
        subprocess.run(pip_cmd, check=True)
        print("  [OK] Dependencies installed")
        return True
        
    except subprocess.CalledProcessError as e:
        print(f"  [!] Failed to create virtual environment: {e}")
        return False


def check_dependencies():
    """Check if required Python packages are installed."""
    print("Checking dependencies...")
    
    # Check Python version
    if sys.version_info < (3, 10):
        print(f"  [!] Python 3.10+ required, found {sys.version}")
        print("      Please install Python 3.10 or higher")
        return False
    print(f"  [OK] Python {sys.version_info.major}.{sys.version_info.minor}")
    
    try:
        import mcp
        print("  [OK] mcp package installed")
    except ImportError:
        print("  [!] mcp package not found")
        print("      Run: pip install -r backend/requirements.txt")
        return False

    try:
        import pydantic
        print("  [OK] pydantic package installed")
    except ImportError:
        print("  [!] pydantic package not found")
        return False

    return True


def create_claude_config(shared_folders: list[str], allowed_extensions: str):
    """Create or update Claude Desktop config."""
    config_path = get_claude_config_path()
    python_path = get_python_path()
    server_path = get_server_path()

    # Load existing config or create new
    config = {}
    if config_path.exists():
        try:
            with open(config_path, "r") as f:
                config = json.load(f)
            print(f"\nFound existing Claude config at: {config_path}")
        except json.JSONDecodeError:
            print(f"\nWarning: Could not parse existing config at {config_path}")
            config = {}

    # Ensure mcpServers exists
    if "mcpServers" not in config:
        config["mcpServers"] = {}

    # Add our server configuration
    config["mcpServers"]["firm-knowledge-base"] = {
        "command": str(python_path),
        "args": [str(server_path)],
        "env": {
            "SHARED_FOLDERS_ROOT": ",".join(shared_folders),
            "ALLOWED_EXTENSIONS": allowed_extensions,
        }
    }

    # Create parent directory if needed
    config_path.parent.mkdir(parents=True, exist_ok=True)

    # Backup existing config
    if config_path.exists():
        backup_path = config_path.with_suffix(".json.backup")
        shutil.copy(config_path, backup_path)
        print(f"Backed up existing config to: {backup_path}")

    # Write new config
    with open(config_path, "w") as f:
        json.dump(config, f, indent=2)

    print(f"\nUpdated Claude config at: {config_path}")
    return config_path


def prompt_for_folders():
    """Prompt user to enter shared folder paths."""
    print("\n" + "=" * 60)
    print("SHARED FOLDER CONFIGURATION")
    print("=" * 60)
    print("\nEnter the paths to your firm's shared folders.")
    print("These are the folders the AI will be able to search.")
    print("Enter each path on a new line. Press Enter twice when done.\n")

    os_type, os_name = get_os_info()

    if os_type == "macos":
        print("Example paths:")
        print("  /Volumes/SharedDrive/Projects")
        print("  /Users/Shared/Drawings")
    elif os_type == "windows":
        print("Example paths:")
        print("  \\\\server\\SharedFolders\\Projects")
        print("  C:\\SharedDrive\\Drawings")
    else:
        print("Example paths:")
        print("  /mnt/shared/Projects")
        print("  /home/shared/Drawings")

    folders = []
    while True:
        path = input("\nFolder path (or Enter to finish): ").strip()
        if not path:
            if folders:
                break
            else:
                print("Please enter at least one folder path.")
                continue

        path_obj = Path(path)
        if path_obj.exists():
            folders.append(str(path_obj.resolve()))
            print(f"  [OK] Added: {path_obj.resolve()}")
        else:
            print(f"  [!] Path does not exist: {path}")
            add_anyway = input("      Add anyway? (y/n): ").lower().strip()
            if add_anyway == "y":
                folders.append(path)
                print(f"  [OK] Added: {path}")

    return folders


def main():
    """Main setup function."""
    os_type, os_name = get_os_info()

    print("\n" + "=" * 60)
    print("MCP SERVER SETUP")
    print("=" * 60)
    print(f"\nDetected OS: {os_name}")
    print(f"Project root: {get_project_root()}")
    print(f"Server: {get_server_path()}")

    # Create virtual environment if needed
    venv_created = create_venv_if_needed()
    
    if venv_created:
        venv_python = get_venv_python()
        print(f"Using Python: {venv_python}")
    else:
        print(f"Using Python: {sys.executable}")

    # Check dependencies
    if not check_dependencies():
        print("\nPlease install missing dependencies first:")
        print("  1. Create venv: python -m venv venv")
        if os_type == "windows":
            print("  2. Activate: .\\venv\\Scripts\\Activate.ps1")
        else:
            print("  2. Activate: source venv/bin/activate")
        print("  3. Install: pip install -r backend/requirements.txt")
        sys.exit(1)

    # Check if Claude Desktop is installed
    config_path = get_claude_config_path()
    if not config_path.parent.exists():
        print(f"\nNote: Claude Desktop config folder not found.")
        print(f"Expected at: {config_path.parent}")
        print("Make sure Claude Desktop is installed.")
        create_anyway = input("\nCreate config anyway? (y/n): ").lower().strip()
        if create_anyway != "y":
            sys.exit(0)

    # Get shared folder paths
    folders = prompt_for_folders()

    # Default allowed extensions
    default_extensions = ".pdf,.docx,.doc,.txt,.md,.dwg,.dxf,.png,.jpg,.jpeg,.gif,.csv,.json,.xml"
    print(f"\nDefault allowed extensions: {default_extensions}")
    customize = input("Customize extensions? (y/n): ").lower().strip()
    if customize == "y":
        extensions = input("Enter extensions (comma-separated): ").strip()
    else:
        extensions = default_extensions

    # Create the config
    config_path = create_claude_config(folders, extensions)

    # Success message
    print("\n" + "=" * 60)
    print("SETUP COMPLETE!")
    print("=" * 60)
    print("\nNext steps:")
    print("1. Restart Claude Desktop to load the new configuration")
    print("2. Look for the MCP server icon (hammer/tools) in Claude's input area")
    print("3. Try asking: 'List all projects in the knowledge base'")
    print("\nTo modify settings later, edit:")
    print(f"  {config_path}")

    # Show manual config for reference
    print("\n" + "-" * 60)
    print("Manual configuration (if needed):\n")
    print(json.dumps({
        "mcpServers": {
            "firm-knowledge-base": {
                "command": str(get_python_path()),
                "args": [str(get_server_path())],
                "env": {
                    "SHARED_FOLDERS_ROOT": ",".join(folders),
                    "ALLOWED_EXTENSIONS": extensions,
                }
            }
        }
    }, indent=2))


if __name__ == "__main__":
    main()
