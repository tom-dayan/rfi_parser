from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .database import init_db
from .config import settings
from .routers import projects, files, process

# Initialize FastAPI app
app = FastAPI(
    title="RFI Processing Tool API",
    description="API for processing RFIs against architectural specifications using local folders",
    version="2.0.0"
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


@app.on_event("startup")
def startup_event():
    """Initialize database on startup"""
    init_db()
    print("Database initialized")
    print(f"AI Provider: {settings.ai_provider}")
    if settings.ai_provider == "ollama":
        print(f"Ollama URL: {settings.ollama_base_url}")
        print(f"Ollama Model: {settings.ollama_model}")


@app.get("/")
def root():
    """Root endpoint"""
    return {
        "message": "RFI Processing Tool API",
        "version": "2.0.0",
        "docs": "/docs",
        "ai_provider": settings.ai_provider
    }


@app.get("/health")
def health_check():
    """Health check endpoint"""
    return {"status": "healthy"}
