from sqlalchemy import create_engine, text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from .config import settings

engine = create_engine(
    settings.database_url,
    connect_args={"check_same_thread": False} if "sqlite" in settings.database_url else {},
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db():
    """Dependency for FastAPI routes to get database session"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def run_migrations():
    """Run database migrations to add any missing columns"""
    migrations = [
        # Add exclude_folders column to projects table
        {
            "table": "projects",
            "column": "exclude_folders",
            "sql": "ALTER TABLE projects ADD COLUMN exclude_folders TEXT"
        },
    ]
    
    with engine.connect() as conn:
        for migration in migrations:
            # Check if column exists
            result = conn.execute(text(
                f"PRAGMA table_info({migration['table']})"
            ))
            columns = [row[1] for row in result.fetchall()]
            
            if migration["column"] not in columns:
                try:
                    conn.execute(text(migration["sql"]))
                    conn.commit()
                    print(f"Migration: Added column '{migration['column']}' to '{migration['table']}'")
                except Exception as e:
                    print(f"Migration warning: {e}")


def init_db():
    """Initialize database tables and run migrations"""
    # Create any new tables
    Base.metadata.create_all(bind=engine)
    
    # Run migrations for existing tables (add new columns)
    run_migrations()
