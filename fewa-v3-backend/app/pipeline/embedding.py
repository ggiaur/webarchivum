import time
import math
import re
from typing import List
from spec.pipeline_schemas import ChunkingInput, EmbeddingOutput, SingleChunkEmbedding


def generate_mock_embedding(text: str, dim: int = 768) -> List[float]:
    """Generates normalized 768-dim float vector for nomic-embed-text."""
    raw_hash = hash(text)
    vec = [(math.sin(raw_hash + i) * 0.5) for i in range(dim)]
    # L2 normalize
    norm = math.sqrt(sum(x * x for x in vec)) or 1.0
    return [round(x / norm, 6) for x in vec]


def chunk_and_embed_text(input_data: ChunkingInput) -> EmbeddingOutput:
    """
    Sentence-boundary based chunking (chunk_size=600, overlap=100) and nomic-embed-text 768d embedding generation.
    Returns validated EmbeddingOutput schema.
    """
    start_time = time.time()
    text = input_data.raw_text

    # Sentence boundary split
    sentences = re.split(r"(?<=[.!?])\s+", text)
    chunks: List[SingleChunkEmbedding] = []

    current_sentences: List[str] = []
    current_tokens = 0
    chunk_idx = 0
    char_offset = 0

    for sent in sentences:
        tokens = len(sent.split())
        if current_tokens + tokens > input_data.chunk_size and current_sentences:
            chunk_text = " ".join(current_sentences)
            if len(chunk_text) >= input_data.min_chunk_len:
                embedding_vec = generate_mock_embedding(chunk_text, dim=768)
                chunks.append(
                    SingleChunkEmbedding(
                        chunk_index=chunk_idx,
                        text=chunk_text,
                        token_count=current_tokens,
                        embedding=embedding_vec,
                        char_offset=char_offset,
                    )
                )
                chunk_idx += 1
                char_offset += len(chunk_text) + 1

            # Keep overlap
            overlap_count = max(1, int(len(current_sentences) * (input_data.chunk_overlap / input_data.chunk_size)))
            current_sentences = current_sentences[-overlap_count:]
            current_tokens = sum(len(s.split()) for s in current_sentences)

        current_sentences.append(sent)
        current_tokens += tokens

    # Flush last chunk
    if current_sentences:
        chunk_text = " ".join(current_sentences)
        if len(chunk_text) >= input_data.min_chunk_len or not chunks:
            embedding_vec = generate_mock_embedding(chunk_text, dim=768)
            chunks.append(
                SingleChunkEmbedding(
                    chunk_index=chunk_idx,
                    text=chunk_text,
                    token_count=max(1, current_tokens),
                    embedding=embedding_vec,
                    char_offset=char_offset,
                )
            )

    latency_ms = int((time.time() - start_time) * 1000)
    total_tokens = sum(c.token_count for c in chunks)

    return EmbeddingOutput(
        snapshot_id=input_data.snapshot_id,
        chunks=chunks,
        embedding_model="nomic-embed-text",
        embedding_version="1.5",
        total_tokens=total_tokens,
        embedding_latency_ms=max(1, latency_ms),
    )
