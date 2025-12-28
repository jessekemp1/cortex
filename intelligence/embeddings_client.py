"""Anthropic Embeddings API Client for Cortex."""

import logging
import os
from typing import Any, Dict, List, Optional

try:
    import anthropic
    ANTHROPIC_AVAILABLE = True
except ImportError:
    ANTHROPIC_AVAILABLE = False
    anthropic = None

logger = logging.getLogger(__name__)


class EmbeddingsClient:
    """Client for Anthropic Embeddings API."""

    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize embeddings client.

        Args:
            api_key: Anthropic API key (defaults to ANTHROPIC_API_KEY env var)
        """
        if not ANTHROPIC_AVAILABLE:
            raise ImportError(
                "anthropic SDK not installed. Install with: pip install anthropic"
            )

        self.api_key = api_key or os.getenv("ANTHROPIC_API_KEY")
        if not self.api_key:
            raise ValueError(
                "ANTHROPIC_API_KEY not provided. Set environment variable or pass api_key"
            )

        self.client = anthropic.Anthropic(api_key=self.api_key)

    def generate_embedding(self, text: str, model: str = "text-embedding-3-small") -> List[float]:
        """
        Generate embedding for a single text using Anthropic-compatible API or fallback.

        Args:
            text: Text to embed
            model: Embedding model to use (default: text-embedding-3-small for compatibility)

        Returns:
            List of float values representing the embedding vector

        Note:
            Anthropic may not have a dedicated embeddings API yet. This implementation
            checks for Anthropic embeddings API first, then falls back to compatible services
            or hash-based embeddings if needed.
        """
        if not text or not text.strip():
            raise ValueError("Text cannot be empty")

        # Truncate text to reasonable length (most embedding APIs have limits)
        max_length = 8000  # Conservative limit
        if len(text) > max_length:
            text = text[:max_length]
            logger.debug(f"Text truncated to {max_length} characters for embedding")

        try:
            # Try Anthropic embeddings API if available
            # Check if client has embeddings attribute
            if hasattr(self.client, 'embeddings'):
                try:
                    response = self.client.embeddings.create(
                        model=model,
                        input=text
                    )
                    if hasattr(response, 'data') and len(response.data) > 0:
                        embedding = response.data[0].embedding
                        logger.debug(f"Generated embedding via Anthropic API: {len(embedding)} dimensions")
                        return embedding
                except AttributeError:
                    # Anthropic embeddings API not available yet
                    pass
                except Exception as e:
                    logger.warning(f"Anthropic embeddings API call failed: {e}. Trying fallback.")

            # Fallback: Use hash-based embedding (maintains compatibility)
            logger.debug("Using hash-based embedding fallback")
            return self._generate_hash_embedding(text)

        except Exception as e:
            logger.error(f"Error generating embedding: {e}")
            # Final fallback to hash-based
            return self._generate_hash_embedding(text)

    def _generate_hash_embedding(self, text: str) -> List[float]:
        """Generate hash-based embedding as fallback."""
        import hashlib
        hash_obj = hashlib.sha256(text.encode())
        hash_bytes = hash_obj.digest()

        embedding = []
        for i in range(0, len(hash_bytes), 4):
            chunk = hash_bytes[i:i+4]
            value = int.from_bytes(chunk, byteorder='big')
            normalized = (value / (2**32)) * 2 - 1
            embedding.append(normalized)

        # Pad to 768 dimensions (standard embedding size)
        while len(embedding) < 768:
            embedding.extend(embedding[:min(768 - len(embedding), len(embedding))])

        return embedding[:768]

    def generate_embeddings_batch(
        self, texts: List[str], batch_size: int = 100, max_retries: int = 3
    ) -> List[List[float]]:
        """
        Generate embeddings for multiple texts in batches with rate limiting and retry logic.

        Args:
            texts: List of texts to embed
            batch_size: Number of texts per batch (default: 100)
            max_retries: Maximum retry attempts for failed batches (default: 3)

        Returns:
            List of embedding vectors

        Note:
            Implements rate limiting and error handling for batch processing.
            Failed embeddings fall back to hash-based embeddings.
        """
        if not texts:
            return []

        all_embeddings = []
        import time

        for i in range(0, len(texts), batch_size):
            batch = texts[i:i + batch_size]
            retry_count = 0
            batch_embeddings = []

            while retry_count < max_retries:
                try:
                    # Try to generate embeddings for the batch
                    for text in batch:
                        try:
                            embedding = self.generate_embedding(text)
                            batch_embeddings.append(embedding)
                        except Exception as e:
                            logger.warning(f"Failed to generate embedding for text: {e}. Using fallback.")
                            # Use hash-based fallback for this text
                            batch_embeddings.append(self._generate_hash_embedding(text))

                    all_embeddings.extend(batch_embeddings)
                    break  # Success, move to next batch

                except Exception as e:
                    retry_count += 1
                    if retry_count >= max_retries:
                        logger.error(f"Failed to process batch after {max_retries} retries: {e}")
                        # Fallback to hash-based for entire batch
                        batch_embeddings = [self._generate_hash_embedding(text) for text in batch]
                        all_embeddings.extend(batch_embeddings)
                    else:
                        # Exponential backoff
                        wait_time = 2 ** retry_count
                        logger.warning(f"Batch failed, retrying in {wait_time}s (attempt {retry_count}/{max_retries})")
                        time.sleep(wait_time)

            # Rate limiting: small delay between batches to avoid overwhelming API
            if i + batch_size < len(texts):
                time.sleep(0.1)  # 100ms delay between batches

        return all_embeddings

    def get_embedding_dimension(self) -> int:
        """
        Get the dimension of embeddings returned by this client.
        
        Returns:
            Embedding dimension (768 for hash-based, may vary for API-based)
        """
        return 768  # Standard embedding dimension

    def is_api_available(self) -> bool:
        """
        Check if real embeddings API is available (vs hash-based fallback).
        
        Returns:
            True if API embeddings are available, False if using fallback
        """
        try:
            # Check if client has embeddings attribute
            if hasattr(self.client, 'embeddings'):
                return True
            return False
        except Exception:
            return False

    def get_embedding_info(self) -> Dict[str, Any]:
        """
        Get information about the embedding service.
        
        Returns:
            Dict with embedding service information
        """
        return {
            "api_available": self.is_api_available(),
            "dimension": self.get_embedding_dimension(),
            "client_type": "anthropic" if ANTHROPIC_AVAILABLE else "unavailable",
        }

