from sqlalchemy import Column, Integer, String, Text, Float, DateTime, ForeignKey, JSON, BigInteger
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from .database import Base


class Project(Base):
    """A project containing RFIs and specification files"""
    __tablename__ = "projects"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    rfi_folder_path = Column(String(1024), nullable=False)
    specs_folder_path = Column(String(1024), nullable=False)
    created_date = Column(DateTime(timezone=True), server_default=func.now())
    last_scanned = Column(DateTime(timezone=True), nullable=True)

    # Relationships
    files = relationship("ProjectFile", back_populates="project", cascade="all, delete-orphan")
    results = relationship("RFIResult", back_populates="project", cascade="all, delete-orphan")


class ProjectFile(Base):
    """An indexed file within a project (RFI, spec, drawing, etc.)"""
    __tablename__ = "project_files"

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False)

    # File info
    file_path = Column(String(1024), nullable=False)  # Absolute path
    filename = Column(String(255), nullable=False)
    file_type = Column(String(50), nullable=False)  # pdf, docx, dwg, dxf, png, jpg, etc.
    file_size = Column(BigInteger, nullable=False)
    modified_date = Column(DateTime(timezone=True), nullable=False)
    last_indexed = Column(DateTime(timezone=True), nullable=True)

    # Content classification
    content_type = Column(String(50), nullable=False)  # rfi, specification, drawing, image, other

    # Extracted content
    content_text = Column(Text, nullable=True)  # Extracted text content
    file_metadata = Column(JSON, nullable=True)  # File-specific metadata (layers, pages, dimensions, etc.)

    # Relationships
    project = relationship("Project", back_populates="files")
    rfi_results = relationship("RFIResult", back_populates="rfi_file",
                               foreign_keys="RFIResult.rfi_file_id")


class RFIResult(Base):
    """Result of processing an RFI against specifications"""
    __tablename__ = "rfi_results"

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False)
    rfi_file_id = Column(Integer, ForeignKey("project_files.id"), nullable=False)

    # Analysis result
    status = Column(String(50), nullable=False)  # accepted, rejected, comment, refer_to_consultant
    consultant_type = Column(String(100), nullable=True)  # structural, electrical, mechanical, etc.
    reason = Column(Text, nullable=True)  # Explanation for the decision
    confidence = Column(Float, nullable=False, default=0.0)
    processed_date = Column(DateTime(timezone=True), server_default=func.now())

    # File references - which files were used in the analysis
    referenced_file_ids = Column(JSON, nullable=True)  # Array of ProjectFile IDs
    spec_references = Column(JSON, nullable=True)  # [{file_id, section, quote}, ...]

    # Relationships
    project = relationship("Project", back_populates="results")
    rfi_file = relationship("ProjectFile", back_populates="rfi_results",
                           foreign_keys=[rfi_file_id])
