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
    """Run database migrations to add any missing columns and fix constraints"""
    # Simple column additions
    column_migrations = [
        # Add exclude_folders column to projects table
        {
            "table": "projects",
            "column": "exclude_folders",
            "sql": "ALTER TABLE projects ADD COLUMN exclude_folders TEXT"
        },
        # Add source_filename for path-based results
        {
            "table": "processing_results",
            "column": "source_filename",
            "sql": "ALTER TABLE processing_results ADD COLUMN source_filename VARCHAR(255)"
        },
        # Add source_file_path for path-based results
        {
            "table": "processing_results",
            "column": "source_file_path",
            "sql": "ALTER TABLE processing_results ADD COLUMN source_file_path VARCHAR(1024)"
        },
    ]
    
    with engine.connect() as conn:
        for migration in column_migrations:
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
        
        # Fix: Make source_file_id nullable in processing_results
        # SQLite doesn't support ALTER COLUMN, so we need to recreate the table
        try:
            result = conn.execute(text("PRAGMA table_info(processing_results)"))
            columns_info = result.fetchall()
            
            # Check if source_file_id is NOT NULL (notnull = 1)
            for col in columns_info:
                if col[1] == "source_file_id" and col[3] == 1:  # col[3] is notnull flag
                    print("Migration: Making source_file_id nullable in processing_results...")
                    
                    # Recreate the table with nullable source_file_id
                    conn.execute(text("""
                        CREATE TABLE IF NOT EXISTS processing_results_new (
                            id INTEGER PRIMARY KEY,
                            project_id INTEGER NOT NULL REFERENCES projects(id),
                            source_file_id INTEGER REFERENCES project_files(id),
                            source_filename VARCHAR(255),
                            source_file_path VARCHAR(1024),
                            document_type VARCHAR(50) NOT NULL,
                            response_text TEXT,
                            status VARCHAR(50),
                            consultant_type VARCHAR(100),
                            confidence FLOAT NOT NULL DEFAULT 0.0,
                            processed_date DATETIME DEFAULT CURRENT_TIMESTAMP,
                            spec_references TEXT
                        )
                    """))
                    
                    # Copy existing data
                    conn.execute(text("""
                        INSERT INTO processing_results_new 
                            (id, project_id, source_file_id, source_filename, source_file_path,
                             document_type, response_text, status, consultant_type, confidence,
                             processed_date, spec_references)
                        SELECT id, project_id, source_file_id, source_filename, source_file_path,
                               document_type, response_text, status, consultant_type, confidence,
                               processed_date, spec_references
                        FROM processing_results
                    """))
                    
                    # Drop old table and rename new one
                    conn.execute(text("DROP TABLE processing_results"))
                    conn.execute(text("ALTER TABLE processing_results_new RENAME TO processing_results"))
                    
                    conn.commit()
                    print("Migration: source_file_id is now nullable")
                    break
        except Exception as e:
            print(f"Migration warning (nullable fix): {e}")


def init_db():
    """Initialize database tables and run migrations"""
    # Create any new tables
    Base.metadata.create_all(bind=engine)
    
    # Run migrations for existing tables (add new columns)
    run_migrations()
