"""Main knowledge base service that orchestrates document indexing and retrieval."""
import logging
from typing import Optional

from .chunker import DocumentChunker, Chunk
from .embeddings import EmbeddingService, OllamaEmbeddings, SentenceTransformerEmbeddings
from .vector_store import ChromaVectorStore, SearchResult

logger = logging.getLogger(__name__)


class KnowledgeBase:
    """
    Knowledge base for a project.

    Handles document indexing (chunking + embedding + storage) and
    semantic search for RAG-based response generation.
    """

    def __init__(
        self,
        project_id: int,
        persist_directory: str = "./data/chroma",
        embedding_service: Optional[EmbeddingService] = None,
        chunk_size: int = 1000,
        chunk_overlap: int = 200
    ):
        self.project_id = project_id
        self.chunker = DocumentChunker(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap
        )

        # Use provided embedding service or default to Ollama with fallback
        if embedding_service:
            self.embeddings = embedding_service
        else:
            self.embeddings = self._create_default_embeddings()

        self.vector_store = ChromaVectorStore(
            project_id=project_id,
            persist_directory=persist_directory
        )

    def _create_default_embeddings(self) -> EmbeddingService:
        """Create default embedding service with Ollama, falling back to SentenceTransformers."""
        try:
            ollama = OllamaEmbeddings()
            # Test if Ollama is available
            ollama.embed("test")
            logger.info("Using Ollama for embeddings")
            return ollama
        except Exception as e:
            logger.warning(f"Ollama not available ({e}), falling back to SentenceTransformers")
            return SentenceTransformerEmbeddings()

    def index_document(
        self,
        content: str,
        file_id: int,
        filename: str,
        is_specification: bool = False
    ) -> int:
        """
        Index a document into the knowledge base.

        Args:
            content: The text content of the document
            file_id: Database ID of the source file
            filename: Name of the source file
            is_specification: Whether this is a spec document (uses section-aware chunking)

        Returns:
            Number of chunks indexed
        """
        if not content or not content.strip():
            logger.warning(f"Empty content for file {filename}, skipping indexing")
            return 0

        # First, remove any existing chunks for this file
        self.remove_document(file_id)

        # Chunk the document
        chunks = self.chunker.chunk_document(
            text=content,
            file_id=file_id,
            filename=filename,
            content_type='specification' if is_specification else 'other'
        )

        if not chunks:
            logger.warning(f"No chunks generated for file {filename}")
            return 0

        # Generate embeddings for all chunks
        texts = [chunk.text for chunk in chunks]
        embeddings = self.embeddings.embed_batch(texts)

        # Prepare data for vector store
        ids = [f"{file_id}_{chunk.chunk_index}" for chunk in chunks]
        metadatas = [
            {
                "source_file_id": chunk.source_file_id,
                "source_filename": chunk.source_filename,
                "chunk_index": chunk.chunk_index,
                "section_title": chunk.section_title or "",
                "page_number": chunk.page_number or 0
            }
            for chunk in chunks
        ]

        # Add to vector store
        self.vector_store.add_documents(
            texts=texts,
            embeddings=embeddings,
            metadatas=metadatas,
            ids=ids
        )

        logger.info(f"Indexed {len(chunks)} chunks from {filename}")
        return len(chunks)

    def remove_document(self, file_id: int) -> int:
        """
        Remove a document from the knowledge base.

        Args:
            file_id: Database ID of the file to remove

        Returns:
            Number of chunks removed
        """
        count = self.vector_store.delete_by_file_id(file_id)
        if count > 0:
            logger.info(f"Removed {count} chunks for file_id {file_id}")
        return count

    def search(
        self,
        query: str,
        n_results: int = 10,
        min_score: float = 0.0
    ) -> list[SearchResult]:
        """
        Search the knowledge base for relevant content.

        Args:
            query: The search query
            n_results: Maximum number of results to return
            min_score: Minimum similarity score threshold

        Returns:
            List of search results sorted by relevance
        """
        # Generate query embedding
        query_embedding = self.embeddings.embed(query)

        # Search vector store
        results = self.vector_store.search(
            query_embedding=query_embedding,
            n_results=n_results
        )

        # Filter by minimum score
        if min_score > 0:
            results = [r for r in results if r.score >= min_score]

        return results

    def search_with_context(
        self,
        query: str,
        n_results: int = 5,
        context_chars: int = 500
    ) -> list[dict]:
        """
        Search and return results formatted for RAG context.

        Args:
            query: The search query
            n_results: Maximum number of results
            context_chars: Maximum characters per result (truncate if longer)

        Returns:
            List of dicts with 'text', 'source', 'section', 'score'
        """
        results = self.search(query, n_results=n_results)

        formatted = []
        for r in results:
            text = r.text
            if len(text) > context_chars:
                text = text[:context_chars] + "..."

            formatted.append({
                "text": text,
                "source": r.source_filename,
                "source_file_id": r.source_file_id,
                "section": r.section_title,
                "score": round(r.score, 4)
            })

        return formatted

    def search_multi_query(
        self,
        queries: list[str],
        n_results_per_query: int = 5,
        max_total_results: int = 10,
        context_chars: int = 1000,
        min_score: float = 0.3
    ) -> list[dict]:
        """
        Search with multiple queries and merge results.
        
        This improves retrieval by:
        1. Running multiple targeted queries
        2. Deduplicating results
        3. Boosting results that appear in multiple queries
        
        Args:
            queries: List of search queries
            n_results_per_query: Results per individual query
            max_total_results: Maximum total results to return
            context_chars: Maximum characters per result
            min_score: Minimum similarity score threshold
            
        Returns:
            Merged and deduplicated list of results, sorted by score
        """
        if not queries:
            return []
        
        # Collect all results with source tracking
        all_results: dict[str, dict] = {}  # key: source_file_id + chunk text hash
        
        for query in queries:
            if not query or len(query.strip()) < 5:
                continue
                
            results = self.search(query, n_results=n_results_per_query, min_score=min_score)
            
            for r in results:
                # Create unique key for deduplication
                key = f"{r.source_file_id}_{hash(r.text[:200])}"
                
                if key in all_results:
                    # Boost score for results appearing in multiple queries
                    existing = all_results[key]
                    existing["score"] = max(existing["score"], r.score) * 1.1
                    existing["match_count"] = existing.get("match_count", 1) + 1
                else:
                    text = r.text
                    if len(text) > context_chars:
                        text = text[:context_chars] + "..."
                    
                    all_results[key] = {
                        "text": text,
                        "source": r.source_filename,
                        "source_file_id": r.source_file_id,
                        "section": r.section_title,
                        "score": r.score,
                        "match_count": 1
                    }
        
        # Sort by score (descending) and limit results
        sorted_results = sorted(
            all_results.values(),
            key=lambda x: x["score"],
            reverse=True
        )[:max_total_results]
        
        # Clean up and round scores
        for r in sorted_results:
            r["score"] = round(min(r["score"], 1.0), 4)
            r.pop("match_count", None)
        
        logger.info(f"Multi-query search: {len(queries)} queries -> {len(sorted_results)} results")
        
        return sorted_results

    def hybrid_search(
        self,
        query: str,
        keywords: list[str] = None,
        n_results: int = 10,
        semantic_weight: float = 0.7,
        keyword_weight: float = 0.3,
        min_score: float = 0.2
    ) -> list[dict]:
        """
        Hybrid search combining semantic and keyword matching.
        
        This approach provides:
        1. Semantic understanding (via embeddings) for concept matching
        2. Keyword matching for exact term relevance
        3. Combined scoring for best of both approaches
        
        Args:
            query: The semantic search query
            keywords: Optional list of keywords for exact matching
            n_results: Maximum results to return
            semantic_weight: Weight for semantic similarity (0-1)
            keyword_weight: Weight for keyword matching (0-1)
            min_score: Minimum combined score threshold
            
        Returns:
            List of results sorted by combined score
        """
        import re
        
        # Get semantic search results (more than needed, we'll re-rank)
        semantic_results = self.search(query, n_results=n_results * 3, min_score=0.0)
        
        # Extract keywords from query if not provided
        if keywords is None:
            # Simple keyword extraction: remove stopwords and short words
            stopwords = {'the', 'a', 'an', 'is', 'are', 'was', 'were', 'be', 'been',
                        'being', 'have', 'has', 'had', 'do', 'does', 'did', 'will',
                        'would', 'could', 'should', 'may', 'might', 'must', 'can',
                        'for', 'and', 'nor', 'but', 'or', 'yet', 'so', 'of', 'in',
                        'on', 'at', 'to', 'from', 'by', 'with', 'what', 'which',
                        'who', 'whom', 'this', 'that', 'these', 'those', 'it'}
            
            words = re.findall(r'\b[a-zA-Z]+\b', query.lower())
            keywords = [w for w in words if w not in stopwords and len(w) > 2]
        
        # Score and combine results
        scored_results = []
        for r in semantic_results:
            text_lower = r.text.lower()
            
            # Calculate keyword score
            keyword_matches = 0
            for kw in keywords:
                if kw.lower() in text_lower:
                    keyword_matches += 1
            
            keyword_score = keyword_matches / max(len(keywords), 1) if keywords else 0
            
            # Calculate combined score
            combined_score = (
                r.score * semantic_weight + 
                keyword_score * keyword_weight
            )
            
            if combined_score >= min_score:
                scored_results.append({
                    "text": r.text,
                    "source": r.source_filename,
                    "source_file_id": r.source_file_id,
                    "section": r.section_title,
                    "score": round(combined_score, 4),
                    "semantic_score": round(r.score, 4),
                    "keyword_score": round(keyword_score, 4),
                })
        
        # Sort by combined score and limit
        scored_results.sort(key=lambda x: x["score"], reverse=True)
        results = scored_results[:n_results]
        
        logger.info(f"Hybrid search: '{query[:50]}...' -> {len(results)} results")
        
        return results

    def get_stats(self) -> dict:
        """Get statistics about the knowledge base."""
        store_stats = self.vector_store.get_stats()
        return {
            **store_stats,
            "embedding_model": self.embeddings.model_name,
            "chunk_size": self.chunker.chunk_size,
            "chunk_overlap": self.chunker.chunk_overlap
        }

    def clear(self) -> None:
        """Clear all documents from the knowledge base."""
        self.vector_store.clear()
        logger.info(f"Cleared knowledge base for project {self.project_id}")

    def count(self) -> int:
        """Get the total number of chunks in the knowledge base."""
        stats = self.vector_store.get_stats()
        return stats.get("document_count", 0)


# Factory function to create knowledge base for a project
def get_knowledge_base(
    project_id: int,
    persist_directory: str = "./data/chroma"
) -> KnowledgeBase:
    """
    Get or create a knowledge base for a project.

    Args:
        project_id: The project ID
        persist_directory: Directory for ChromaDB persistence

    Returns:
        KnowledgeBase instance for the project
    """
    return KnowledgeBase(
        project_id=project_id,
        persist_directory=persist_directory
    )
