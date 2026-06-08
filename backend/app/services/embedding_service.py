"""EmbeddingService — batch text embedding via LM Studio /v1/embeddings.

Wraps LMStudioClient.embed() with:
- Automatic batching (configurable batch_size, default 32)
- Graceful degradation: returns [] when LM Studio is unavailable
- embed_texts()  — accepts raw strings, returns float vectors
- embed_chunks() — accepts chunk dicts, returns same dicts with 'embedding' field added
"""

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.services.lm_studio_client import LMStudioClient

logger = logging.getLogger(__name__)


class EmbeddingService:
    """Batch embedding service backed by LM Studio /v1/embeddings."""

    def __init__(self, lm_client: "LMStudioClient", batch_size: int = 32):
        self.lm_client = lm_client
        self.batch_size = batch_size

    async def embed_texts(
        self,
        texts: list[str],
        model: str | None = None,
    ) -> list[list[float]]:
        """Embed a list of texts, splitting into batches automatically.

        Returns a list of float vectors in the same order as input.
        Returns [] (empty list, not per-text) on total failure.
        Individual empty strings are skipped and get a zero-vector placeholder.
        """
        if not texts:
            return []

        all_vectors: list[list[float]] = []

        for i in range(0, len(texts), self.batch_size):
            batch = texts[i : i + self.batch_size]
            try:
                vectors = await self.lm_client.embed(batch, model=model)
                if not vectors:
                    # LM Studio returned empty — substitute zero vectors
                    logger.warning(
                        f"EmbeddingService: embed() returned empty for batch "
                        f"{i // self.batch_size + 1} ({len(batch)} texts). "
                        "Substituting zero vectors."
                    )
                    # We don't know the dimension yet; defer resolution
                    all_vectors.extend([] for _ in batch)
                else:
                    all_vectors.extend(vectors)
            except Exception as e:
                logger.error(f"EmbeddingService: batch {i // self.batch_size + 1} failed: {e}")
                # On failure, emit empty placeholders so indexes align
                all_vectors.extend([] for _ in batch)

        # Replace any empty-placeholder entries with zero vectors of the inferred dim
        dim = next((len(v) for v in all_vectors if v), 0)
        if dim:
            all_vectors = [v if v else [0.0] * dim for v in all_vectors]

        return all_vectors

    async def embed_chunks(
        self,
        chunks: list[dict],
        text_key: str = "text",
        model: str | None = None,
    ) -> list[dict]:
        """Embed chunk dicts, adding an 'embedding' field to each.

        Args:
            chunks: List of dicts, each with at least a `text_key` field.
            text_key: Key in each chunk dict that holds the text to embed.
            model: Optional embedding model override.

        Returns:
            Same list of dicts with 'embedding' added. Chunks for which
            embedding fails get embedding=[] so they can be skipped downstream.
        """
        if not chunks:
            return []

        texts = [c.get(text_key, "") for c in chunks]
        vectors = await self.embed_texts(texts, model=model)

        enriched = []
        for chunk, vec in zip(chunks, vectors, strict=False):
            enriched.append({**chunk, "embedding": vec})

        logger.info(
            f"EmbeddingService: embedded {len(enriched)} chunks (model={model or 'default'})"
        )
        return enriched
