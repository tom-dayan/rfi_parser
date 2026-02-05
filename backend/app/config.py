from pydantic_settings import BaseSettings
from typing import Literal, Optional
from pathlib import Path


class Settings(BaseSettings):
    # Database
    database_url: str = "sqlite:///./rfi_parser.db"

    # AI Service
    ai_provider: Literal["ollama", "claude", "gemini"] = "ollama"
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "llama3.2"
    claude_api_key: str = ""
    claude_model: str = "claude-sonnet-4-20250514"
    gemini_api_key: str = ""
    gemini_model: str = "gemini-2.0-flash-lite"

    # File Upload
    upload_dir: str = "./uploads"
    max_file_size: int = 10 * 1024 * 1024  # 10MB

    # CORS
    cors_origins: list[str] = ["http://localhost:5173", "http://localhost:3000"]

    # Knowledge Base / Shared Folders
    # Comma-separated list of paths to index (e.g., "/path/one,/path/two")
    shared_folders_root: str = ""
    # Auto-index on startup (disable for faster startup during development)
    auto_index_on_startup: bool = True
    # Allowed file extensions for indexing (comma-separated)
    allowed_extensions: str = ".pdf,.docx,.doc,.dwg,.dxf,.rvt,.xlsx,.xls,.txt,.md,.png,.jpg,.jpeg"

    class Config:
        env_file = ".env"

    def get_shared_folders(self) -> list[Path]:
        """Parse shared_folders_root into a list of Path objects."""
        if not self.shared_folders_root:
            return []
        paths = []
        for p in self.shared_folders_root.split(","):
            p = p.strip()
            if p:
                path = Path(p)
                if path.exists() and path.is_dir():
                    paths.append(path)
        return paths

    def get_allowed_extensions(self) -> set[str]:
        """Parse allowed_extensions into a set."""
        return {
            ext.strip().lower() if ext.strip().startswith(".") else f".{ext.strip().lower()}"
            for ext in self.allowed_extensions.split(",")
            if ext.strip()
        }


settings = Settings()
