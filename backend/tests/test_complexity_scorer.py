import pytest
from app.services.complexity_scorer import score_query_complexity

def test_simple_query():
    score, tier = score_query_complexity(
        query_text="What is the capital of France?",
        doc_pages=1,
        retrieved_chunks=1,
        free_vram_mb=8192 # 8GB free -> 0 vram signal
    )
    # query_signal = (6/200)*0.35
    # doc_signal = (1/300)*0.25
    # chunk_signal = (1/10)*0.15
    # vram_signal = 0
    assert score < 0.3
    assert tier == 1

def test_complex_query():
    score, tier = score_query_complexity(
        query_text="Please compare and contrast the implications of X? What are the implications of Y? Provide a comprehensive multi-hop analysis of the relationship between both components, evaluate their tradeoffs, and justify this configuration. Let's make sure to analyze the code implementation and describe how the complexity scorer routes this query.",
        doc_pages=300,
        retrieved_chunks=10,
        free_vram_mb=24576  # 24GB free = no VRAM penalty
    )
    # With abundant VRAM, tier 3 is appropriate for complex queries
    assert score > 0.5  # Still high score due to query + doc + chunk signals
    assert tier == 3

def test_medium_query():
    score, tier = score_query_complexity(
        query_text="Analyze the document.",
        doc_pages=150,
        retrieved_chunks=5,
        free_vram_mb=4096
    )
    assert 0.3 <= score <= 0.6
    assert tier == 2

def test_low_vram_caps_complex_query_to_tier_1():
    _, tier = score_query_complexity(
        query_text="Please compare and contrast every implication across these documents? What tradeoffs matter?",
        doc_pages=300,
        retrieved_chunks=10,
        free_vram_mb=1024,
    )
    assert tier == 1

def test_mid_vram_caps_complex_query_to_tier_2():
    score, tier = score_query_complexity(
        query_text="Please compare and contrast every implication across these documents? What tradeoffs matter?",
        doc_pages=300,
        retrieved_chunks=10,
        free_vram_mb=6000,
    )
    assert score > 0.6
    assert tier == 2
