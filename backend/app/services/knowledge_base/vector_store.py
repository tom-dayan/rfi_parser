"""Vector store implementations for knowledge base."""
import os
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional
import chromadb
from chromadb.config import Settings


@dataclass
class SearchResult:
    """A search result from the vector store."""
    text: str
    score: float
    metadata: dict

    @property
    def source_file_id(self) -> int:
        return self.metadata.get("source_file_id", 0)

    @property
    def source_filename(self) -> str:
        return self.metadata.get("source_filename", "")

    @property
    def section_title(self) -> str:
        return self.metadata.get("section_title", "")


class VectorStore(ABC):
    """Abstract base class for vector stores."""

    @abstractmethod
    def add_documents(
        self,
        texts: list[str],
        embeddings: list[list[float]],
        metadatas: list[dict],
        ids: list[str]
    ) -> None:
        """Add documents to the store."""
        pass

    @abstractmethod
    def search(
        self,
        query_embedding: list[float],
        n_results: int = 10,
        filter_metadata: Optional[dict] = None
    ) -> list[SearchResult]:
        """Search for similar documents."""
        pass

    @abstractmethod
    def delete_by_metadata(self, metadata_filter: dict) -> int:
        """Delete documents matching metadata filter. Returns count deleted."""
        pass

    @abstractmethod
    def count(self) -> int:
        """Return total document count."""
        pass

    @abstractmethod
    def clear(self) -> None:
        """Clear all documents."""
        pass


class ChromaVectorStore(VectorStore):
    """
    ChromaDB-based vector store.

    Each project gets its own collection for isolation.
    Data is persisted to disk for durability.
    """

    def __init__(
        self,
        project_id: int,
        persist_directory: str = "./data/chroma"
    ):
        self.project_id = project_id
        self.persist_directory = persist_directory
        self.collection_name = f"project_{project_id}"

        # Ensure directory exists
        os.makedirs(persist_directory, exist_ok=True)

        # Initialize ChromaDB client with persistence
        self._client = chromadb.PersistentClient(
            path=persist_directory,
            settings=Settings(
                anonymized_telemetry=False,
                allow_reset=True
            )
        )

        # Get or create collection for this project
        # Use cosine similarity which works better with normalized embeddings
        self._collection = self._client.get_or_create_collection(
            name=self.collection_name,
            metadata={"project_id": project_id, "hnsw:space": "cosine"}
        )

    def add_documents(
        self,
        texts: list[str],
        embeddings: list[list[float]],
        metadatas: list[dict],
        ids: list[str]
    ) -> None:
        """Add documents to the collection."""
        if not texts:
            return

        self._collection.add(
            documents=texts,
            embeddings=embeddings,
            metadatas=metadatas,
            ids=ids
        )

    def search(
        self,
        query_embedding: list[float],
        n_results: int = 10,
        filter_metadata: Optional[dict] = None
    ) -> list[SearchResult]:
        """Search for similar documents."""
        results = self._collection.query(
            query_embeddings=[query_embedding],
            n_results=n_results,
            where=filter_metadata,
            include=["documents", "metadatas", "distances"]
        )

        search_results = []
        if results and results['documents'] and results['documents'][0]:
            documents = results['documents'][0]
            metadatas = results['metadatas'][0] if results['metadatas'] else [{}] * len(documents)
            distances = results['distances'][0] if results['distances'] else [0.0] * len(documents)

            for doc, meta, dist in zip(documents, metadatas, distances):
                # Convert distance to similarity score
                # For cosine distance: 0 = identical, 2 = opposite
                # Convert to similarity: 1 - (dist / 2) gives 0-1 range
                score = max(0.0, 1.0 - (dist / 2.0))
                search_results.append(SearchResult(
                    text=doc,
                    score=score,
                    metadata=meta
                ))

        return search_results

    def delete_by_metadata(self, metadata_filter: dict) -> int:
        """Delete documents matching metadata filter."""
        # Get IDs of matching documents
        results = self._collection.get(
            where=metadata_filter,
            include=[]
        )

        if results and results['ids']:
            count = len(results['ids'])
            self._collection.delete(ids=results['ids'])
            return count
        return 0

    def delete_by_file_id(self, file_id: int) -> int:
        """Delete all chunks from a specific file."""
        return self.delete_by_metadata({"source_file_id": file_id})

    def count(self) -> int:
        """Return total document count."""
        return self._collection.count()

    def clear(self) -> None:
        """Clear all documents from the collection."""
        # Delete and recreate collection with cosine similarity
        self._client.delete_collection(self.collection_name)
        self._collection = self._client.create_collection(
            name=self.collection_name,
            metadata={"project_id": self.project_id, "hnsw:space": "cosine"}
        )

    def get_stats(self) -> dict:
        """Get statistics about the collection."""
        return {
            "project_id": self.project_id,
            "collection_name": self.collection_name,
            "document_count": self.count()
        }
