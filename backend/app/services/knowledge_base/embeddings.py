"""Embedding services for knowledge base."""
from abc import ABC, abstractmethod
from typing import Optional
from concurrent.futures import ThreadPoolExecutor, as_completed
import ollama


class EmbeddingService(ABC):
    """Abstract base class for embedding services."""

    @property
    @abstractmethod
    def model_name(self) -> str:
        """Return the model name."""
        pass

    @abstractmethod
    def embed(self, text: str) -> list[float]:
        """Embed a single text string."""
        pass

    @abstractmethod
    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Embed multiple text strings."""
        pass

    @property
    @abstractmethod
    def dimension(self) -> int:
        """Return the embedding dimension."""
        pass


class OllamaEmbeddings(EmbeddingService):
    """
    Embedding service using Ollama.

    Uses nomic-embed-text model by default, which is a good
    open-source embedding model optimized for retrieval.
    """

    def __init__(
        self,
        model: str = "nomic-embed-text",
        base_url: str = "http://localhost:11434"
    ):
        self._model = model
        self.base_url = base_url
        self._client = ollama.Client(host=base_url)
        self._dimension: Optional[int] = None

    @property
    def model_name(self) -> str:
        """Return the model name."""
        return f"ollama/{self._model}"

    def embed(self, text: str) -> list[float]:
        """Embed a single text string using Ollama."""
        # Truncate text if too long (nomic-embed-text has 8192 token limit)
        # Be conservative: ~3 chars per token, so limit to ~20000 chars
        max_chars = 20000
        if len(text) > max_chars:
            text = text[:max_chars]
        
        try:
            response = self._client.embeddings(
                model=self._model,
                prompt=text
            )
            embedding = response['embedding']

            # Cache dimension on first call
            if self._dimension is None:
                self._dimension = len(embedding)

            return embedding
        except Exception as e:
            # If embedding fails, try with even shorter text
            if "context length" in str(e).lower() or "input length" in str(e).lower():
                shorter_text = text[:5000]
                response = self._client.embeddings(
                    model=self._model,
                    prompt=shorter_text
                )
                return response['embedding']
            raise

    def embed_batch(self, texts: list[str], max_workers: int = 4) -> list[list[float]]:
        """
        Embed multiple texts with parallel processing.
        
        Uses ThreadPoolExecutor for concurrent API calls to Ollama,
        which significantly speeds up batch embedding.
        """
        if len(texts) <= 1:
            return [self.embed(text) for text in texts]
        
        # Use parallel processing for larger batches
        embeddings = [None] * len(texts)
        
        def embed_with_index(index: int, text: str):
            return index, self.embed(text)
        
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = [
                executor.submit(embed_with_index, i, text)
                for i, text in enumerate(texts)
            ]
            
            for future in as_completed(futures):
                idx, embedding = future.result()
                embeddings[idx] = embedding
        
        return embeddings

    @property
    def dimension(self) -> int:
        """Return embedding dimension (768 for nomic-embed-text)."""
        if self._dimension is None:
            # Get dimension by embedding a test string
            self.embed("test")
        return self._dimension or 768


class SentenceTransformerEmbeddings(EmbeddingService):
    """
    Embedding service using sentence-transformers.

    Fallback option if Ollama isn't available.
    Uses all-MiniLM-L6-v2 by default (fast and good quality).
    """

    def __init__(self, model_name_str: str = "all-MiniLM-L6-v2"):
        try:
            from sentence_transformers import SentenceTransformer
            self._model_name = model_name_str
            self.model = SentenceTransformer(model_name_str)
            self._dimension = self.model.get_sentence_embedding_dimension()
        except ImportError:
            raise ImportError(
                "sentence-transformers is required for SentenceTransformerEmbeddings. "
                "Install with: pip install sentence-transformers"
            )

    @property
    def model_name(self) -> str:
        """Return the model name."""
        return f"sentence-transformers/{self._model_name}"

    def embed(self, text: str) -> list[float]:
        """Embed a single text string."""
        embedding = self.model.encode(text, convert_to_numpy=True)
        return embedding.tolist()

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Embed multiple texts (batched for efficiency)."""
        embeddings = self.model.encode(texts, convert_to_numpy=True)
        return embeddings.tolist()

    @property
    def dimension(self) -> int:
        """Return embedding dimension."""
        return self._dimension
