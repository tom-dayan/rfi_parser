import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .database import init_db
from .config import settings
from .routers import projects, files, process, chat, search
from .services.metadata_index import get_metadata_index

logger = logging.getLogger(__name__)

# Track indexing status
_indexing_status = {
    "in_progress": False,
    "last_run": None,
    "stats": None,
    "error": None,
}


async def _index_shared_folders_background():
    """Background task to index shared folders."""
    global _indexing_status
    
    folders = settings.get_shared_folders()
    if not folders:
        logger.info("No shared folders configured for indexing")
        return
    
    _indexing_status["in_progress"] = True
    _indexing_status["error"] = None
    
    try:
        index = get_metadata_index()
        # Strip leading dots from extensions (scan_directory expects 'pdf' not '.pdf')
        allowed_extensions = {ext.lstrip(".") for ext in settings.get_allowed_extensions()}
        
        total_stats = {"indexed": 0, "skipped": 0, "errors": 0}
        
        for folder in folders:
            logger.info(f"Indexing shared folder: {folder}")
            try:
                stats = index.scan_directory(
                    root_path=folder,
                    allowed_extensions=allowed_extensions,
                )
                total_stats["indexed"] += stats.get("indexed", 0)
                total_stats["skipped"] += stats.get("skipped", 0)
                total_stats["errors"] += stats.get("errors", 0)
                logger.info(f"Indexed {folder}: {stats}")
            except Exception as e:
                logger.error(f"Error indexing {folder}: {e}")
                total_stats["errors"] += 1
        
        _indexing_status["stats"] = total_stats
        _indexing_status["last_run"] = asyncio.get_event_loop().time()
        logger.info(f"Indexing complete: {total_stats}")
        
    except Exception as e:
        logger.error(f"Background indexing failed: {e}")
        _indexing_status["error"] = str(e)
    finally:
        _indexing_status["in_progress"] = False


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler."""
    # Startup
    init_db()
    logger.info("Database initialized")
    logger.info(f"AI Provider: {settings.ai_provider}")
    
    if settings.ai_provider == "ollama":
        logger.info(f"Ollama URL: {settings.ollama_base_url}")
        logger.info(f"Ollama Model: {settings.ollama_model}")
    
    # Start background indexing if configured
    if settings.auto_index_on_startup and settings.shared_folders_root:
        folders = settings.get_shared_folders()
        if folders:
            logger.info(f"Starting background indexing of {len(folders)} folder(s)")
            asyncio.create_task(_index_shared_folders_background())
        else:
            logger.warning("SHARED_FOLDERS_ROOT set but no valid folders found")
    
    yield  # App runs here
    
    # Shutdown (cleanup if needed)
    logger.info("Application shutting down")


# Initialize FastAPI app with lifespan
app = FastAPI(
    title="OLILab API",
    description="API for processing RFIs against architectural specifications using local folders",
    version="2.2.0",
    lifespan=lifespan,
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(projects.router)
app.include_router(files.router)
app.include_router(process.router)
app.include_router(chat.router)
app.include_router(search.router)


@app.get("/")
def root():
    """Root endpoint"""
    return {
        "message": "OLILab API",
        "version": "2.2.0",
        "docs": "/docs",
        "ai_provider": settings.ai_provider,
        "shared_folders": [str(f) for f in settings.get_shared_folders()],
    }


@app.get("/health")
def health_check():
    """Health check endpoint"""
    return {"status": "healthy"}


@app.get("/api/indexing/status")
def indexing_status():
    """Get the current indexing status."""
    index = get_metadata_index()
    return {
        "indexing": _indexing_status,
        "index_stats": index.get_stats(),
        "configured_folders": [str(f) for f in settings.get_shared_folders()],
    }


@app.post("/api/indexing/trigger")
async def trigger_indexing():
    """Manually trigger indexing of shared folders."""
    if _indexing_status["in_progress"]:
        return {"status": "already_running", "message": "Indexing is already in progress"}
    
    folders = settings.get_shared_folders()
    if not folders:
        return {"status": "no_folders", "message": "No shared folders configured"}
    
    asyncio.create_task(_index_shared_folders_background())
    return {"status": "started", "message": f"Started indexing {len(folders)} folder(s)"}
