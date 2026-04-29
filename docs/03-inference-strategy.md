# Multi-Model Inference Strategy & Benchmarking Framework

Production specification for DeepTutor + PageIndex + TurboQuant KV Cache system running on FastAPI + React/Next.js + LM Studio.

---

## Executive Summary

This specification defines five interconnected subsystems for a unified local AI application: model role specialization across three tiers, dynamic KV cache allocation using quantized cache techniques inspired by TurboQuant research, a benchmarking harness with concrete FastAPI instrumentation, runtime model switching logic, and a real-time performance dashboard. Every component is designed for LM Studio's OpenAI-compatible REST API on consumer/prosumer GPU hardware with zero cloud dependencies.

---

## 1. Model Role Specialization

Three model tiers map to distinct pipeline stages. Each tier is justified by latency, VRAM, and quality tradeoffs measured against the system's document Q&A workflow.

### Tier Architecture

| Tier | Pipeline Stage | Recommended Models | Params | Quant | VRAM (Weights) | KV Cache (4K ctx) | Latency Target |
|------|---------------|-------------------|--------|-------|----------------|-------------------|----------------|
| **T1 — Lightweight** | PageIndex embedding, retrieval scoring, query classification | Qwen3-0.6B (Q4_K_M), Qwen3-1.7B (Q4_K_M) | 0.6B–1.7B | Q4_K_M | 0.5–1.2 GB | 50–120 MB | < 50ms/query |
| **T2 — Medium** | DeepTutor intermediate reasoning, chunk relevance re-ranking, query decomposition | Qwen3-4B (Q4_K_M), Qwen3-8B (Q5_K_M) | 4B–8B | Q4–Q5 | 2.5–5.5 GB | 200–500 MB | 100–500ms |
| **T3 — Heavy** | Final answer synthesis, multi-hop reasoning, complex document analysis | Qwen3-14B (Q4_K_M), Qwen3-30B-A3B (Q4_K_M) | 14B / 30B-MoE | Q4_K_M | 8.5–18 GB | 800 MB–1.5 GB | 1–5s |

### Tier Justifications

**T1 — Lightweight (0.6B–1.7B)**

- Purpose: All high-frequency, low-complexity operations. PageIndex calls this tier on every query to score page-level relevance and generate embeddings for retrieval.
- Why these models: [Qwen3-0.6B at Q4 quantization requires approximately 0.5 GB VRAM](https://partimus.com/en/ai-language-models/qwen3-1-7b/) for weights alone, leaving substantial headroom for KV cache and concurrent requests. At 4-bit quantization, the 1.7B variant fits in roughly 1.2 GB ([Gradient Flow](https://gradientflow.com/qwen-3/)). These models run entirely in GPU VRAM with sub-50ms latency for single-token classification tasks.
- Quality tradeoff: Insufficient for multi-hop reasoning or nuanced synthesis, but fully adequate for binary relevance scoring, query intent classification, and embedding generation. [Small dense models in the 0.6B–4B range run on consumer GPUs with 8–16 GB VRAM](https://gradientflow.com/qwen-3/), making them ideal for the always-loaded resident model.
- VRAM budget: T1 models stay resident in VRAM permanently. Budget allocation: 1–2 GB.

**T2 — Medium (4B–8B)**

- Purpose: DeepTutor's intermediate reasoning pipeline — chunk-level re-ranking, query decomposition for multi-part questions, and generating structured intermediate representations before final synthesis.
- Why these models: [Qwen3-4B at FP16 requires approximately 8–10 GB VRAM; at 4-bit quantization, 2–4 GB](https://apxml.com/models/qwen3-4b). The 8B variant at Q5_K_M fits in approximately 5.5 GB. These models balance reasoning capability against the need to co-reside with T1 and potentially T3 models. [Medium dense models (8B–14B) typically require 16–24 GB VRAM when quantized](https://gradientflow.com/qwen-3/), but at Q4/Q5 the 4B and 8B variants remain well within single-GPU budgets.
- Quality tradeoff: Strong enough for structured reasoning over 3–5 retrieved chunks. Struggles with documents exceeding 10K tokens or requiring cross-document synthesis — those escalate to T3.
- VRAM budget: T2 loaded on-demand or semi-resident. Budget allocation: 3–6 GB.

**T3 — Heavy (14B / 30B-MoE)**

- Purpose: Final answer generation for complex queries. Activated only when T2's confidence score falls below threshold or query complexity signals demand it.
- Why these models: [Qwen3-30B-A3B uses MoE architecture with only 3B parameters active per inference](https://blog.premai.io/best-open-source-llms-for-rag-in-2026-10-models-ranked-by-retrieval-accuracy/), delivering 30B-quality outputs at 3B-level compute cost. Users report approximately [34 tokens/second on consumer GPUs](https://gradientflow.com/qwen-3/). The 14B dense model at Q4_K_M requires approximately 8.5 GB and serves as the primary T3 option on 16 GB GPUs where the 30B-MoE won't fit.
- Quality tradeoff: [RAGAS faithfulness score of 0.91 for Qwen3-30B-A3B](https://blog.premai.io/best-open-source-llms-for-rag-in-2026-10-models-ranked-by-retrieval-accuracy/), comparable to GPT-4o on retrieval-grounded QA. This is the quality ceiling for the system.
- VRAM budget: Loaded on-demand, with aggressive TTL-based unloading. Budget allocation: 8–18 GB.

### Embedding Model Selection

For PageIndex vector embeddings specifically (separate from the LLM tiers above):

| Model | Dimensions | MTEB Score | VRAM | Context |
|-------|-----------|------------|------|---------|
| Snowflake Arctic Embed M (GGUF) | 768 | 54.90 NDCG@10 | ~0.5 GB | 512 tokens |
| nomic-embed-text-v1.5 (GGUF) | 768 | 53.25 NDCG@10 | ~0.5 GB | 8192 tokens |
| BGE-M3 | 1024 | 63.0 MTEB | ~1.2 GB | 8192 tokens |

[Snowflake Arctic Embed M achieves state-of-the-art retrieval at its size class](https://github.com/Snowflake-Labs/arctic-embed) and has verified GGUF availability for LM Studio. nomic-embed-text offers longer context at comparable quality. BGE-M3 is the stronger option if VRAM allows.

> **Verification Status**: Qwen3 models (0.6B through 30B-A3B) are verified available in GGUF format on LM Studio's model catalog. Snowflake Arctic Embed GGUF is [available on Hugging Face](https://huggingface.co/ChristianAzinn/snowflake-arctic-embed-m-gguf) and confirmed compatible with LM Studio's embedding endpoint. VRAM figures are reasoned estimates based on parameter count × quantization bit-width; actual consumption varies with context length and batch size.

---

## 2. Dynamic KV Cache Allocation

### Background: What TurboQuant Establishes

[TurboQuant, published by Google Research for ICLR 2026](https://research.google/blog/turboquant-redefining-ai-efficiency-with-extreme-compression/), compresses KV caches to 3–3.5 bits per value using a two-stage pipeline:

1. **PolarQuant** — converts vectors to polar coordinates, eliminating per-block normalization overhead. Enables quantization with zero metadata storage cost.
2. **QJL (Quantized Johnson-Lindenstrauss)** — applies 1-bit residual correction to preserve inner-product fidelity for attention scores.

Verified results from the paper and [Google's blog](https://research.google/blog/turboquant-redefining-ai-efficiency-with-extreme-compression/):
- At least 6x KV memory reduction at 3.5 bits with zero accuracy loss on LongBench, Needle-in-Haystack, and RULER benchmarks
- Up to 8x speedup for attention logit computation on H100 GPUs (vs. 32-bit unquantized)
- Training-free, data-oblivious — no calibration needed
- Tested on Llama-3.1-8B-Instruct, Gemma, and Mistral models

**Critical caveat**: TurboQuant is a research paper with custom CUDA kernels benchmarked on H100 GPUs. It is not yet integrated into llama.cpp or LM Studio. The production implementation below uses llama.cpp's existing KV cache quantization (`q4_0`, `q8_0`, `q5_1`) as the immediately deployable approximation, with TurboQuant principles informing the architecture for future integration.

### What llama.cpp / LM Studio Supports Today

[LM Studio uses llama.cpp as its inference engine](https://lmstudio.ai/docs/app/advanced/parallel-requests), which supports KV cache quantization via `--cache-type-k` and `--cache-type-v` flags with types: `f32`, `f16`, `bf16`, `q8_0`, `q4_0`, `q4_1`, `iq4_nl`, `q5_0`, `q5_1` ([llama.cpp GitHub](https://news.ycombinator.com/item?id=44009321)).

Measured savings from [community benchmarks](https://www.reddit.com/r/LocalLLaMA/comments/1dalkm8/memory_tests_using_llamacpp_kv_cache_quantization/):

| KV Cache Type | Memory vs. f16 | Quality Impact |
|---------------|----------------|----------------|
| `f16` (default) | Baseline | None |
| `q8_0` | ~50% reduction | Negligible |
| `q4_0` | ~75% reduction | Minor — [keys more sensitive than values](https://news.ycombinator.com/item?id=44009321) |
| `K:q8_0 / V:q4_0` | ~62% reduction | Best tradeoff — [0.86% perplexity loss](https://news.ycombinator.com/item?id=44009321) |

Key finding: [Keys need higher precision than values](https://news.ycombinator.com/item?id=44009321). Using `q8_0` for keys and `q4_0` for values yields the best quality/memory tradeoff — 59% memory reduction with only 0.86% perplexity loss vs. 6.06% for the inverse configuration.

### KV Cache Budget Allocation Per Tier

Total KV cache budget is dynamically partitioned based on active models and current memory pressure. The following table assumes a 24 GB VRAM GPU:

| Tier | KV Cache Type | KV Budget (4K ctx) | KV Budget (16K ctx) | Priority |
|------|--------------|--------------------|--------------------|----------|
| T1 (0.6B–1.7B) | `K:q4_0 / V:q4_0` | 12–30 MB | 50–120 MB | Lowest — always fits |
| T2 (4B–8B) | `K:q8_0 / V:q4_0` | 100–250 MB | 400–1000 MB | Medium |
| T3 (14B–30B) | `K:q8_0 / V:q8_0` | 400–750 MB | 1.5–3.0 GB | Highest quality |

Rationale for asymmetric quantization per tier:
- **T1** uses aggressive `q4_0` for both K and V because its tasks (classification, scoring) are tolerant of small precision losses and the model runs at high frequency.
- **T2** uses the empirically optimal `K:q8_0 / V:q4_0` split, preserving key precision for reasoning quality while saving memory on values.
- **T3** uses `q8_0` for both because final answer quality is the top priority and T3 is loaded less frequently.

> **Implementation decision (not from TurboQuant research)**: The asymmetric K/V quantization per tier is a design choice based on community benchmarks and the KVSplit research. TurboQuant itself does not prescribe per-tier differentiation — it compresses uniformly. The tiered approach is this system's adaptation for multi-model co-residency.

### Priority Queuing Logic

Three queue classes, processed by the FastAPI orchestrator:

```
QUEUE PRIORITY (highest first):
1. RETRIEVAL (T1) — PageIndex scoring, embedding generation
   - Rationale: Blocks everything downstream. Must complete before 
     reasoning or generation can start.
   - Max concurrent: 4 (matches LM Studio default)
   - Timeout: 5s
   
2. REASONING (T2) — Chunk re-ranking, query decomposition
   - Rationale: Intermediate step; user is already waiting.
   - Max concurrent: 2
   - Timeout: 30s
   
3. GENERATION (T3) — Final answer synthesis
   - Rationale: Longest-running task, but only one needed per query.
   - Max concurrent: 1
   - Timeout: 120s
```

Implementation via FastAPI:

```python
import asyncio
from enum import IntEnum

class InferencePriority(IntEnum):
    RETRIEVAL = 1    # Highest
    REASONING = 2
    GENERATION = 3

class PriorityQueue:
    def __init__(self):
        self._queue = asyncio.PriorityQueue()
        self._semaphores = {
            InferencePriority.RETRIEVAL: asyncio.Semaphore(4),
            InferencePriority.REASONING: asyncio.Semaphore(2),
            InferencePriority.GENERATION: asyncio.Semaphore(1),
        }
    
    async def submit(self, priority: InferencePriority, request):
        await self._queue.put((priority, request))
    
    async def process(self):
        priority, request = await self._queue.get()
        async with self._semaphores[priority]:
            return await self._execute(request)
```

### Memory Pressure Thresholds and Fallback

Four pressure levels, monitored via `nvidia-smi` or `pynvml`:

| Level | VRAM Utilization | Action |
|-------|-----------------|--------|
| **GREEN** | < 70% | All tiers available. T3 can load on-demand. |
| **YELLOW** | 70–85% | Downgrade T3 KV cache from `q8_0` to `K:q8_0/V:q4_0`. Reduce T2 context window by 50%. |
| **ORANGE** | 85–93% | Unload T3. Route all generation requests to T2. Reduce T1 max concurrent to 2. |
| **RED** | > 93% | Emergency: Unload T2. Run T1 only. Queue all complex requests until memory frees. |

Fallback cascade:
1. T3 unavailable → T2 handles generation with longer inference time and reduced quality ceiling
2. T2 unavailable → T1 handles everything with aggressive prompt truncation (first 2K tokens only)
3. T1 unavailable → System returns error; this should never happen as T1 fits in < 2 GB

```python
# Memory pressure monitor (runs every 2 seconds)
async def check_memory_pressure() -> str:
    import pynvml
    pynvml.nvmlInit()
    handle = pynvml.nvmlDeviceGetHandleByIndex(0)
    info = pynvml.nvmlDeviceGetMemoryInfo(handle)
    utilization = info.used / info.total
    
    if utilization < 0.70:
        return "GREEN"
    elif utilization < 0.85:
        return "YELLOW"
    elif utilization < 0.93:
        return "ORANGE"
    else:
        return "RED"
```

---

## 3. Benchmarking Harness

### Test Categories and Cases

#### Category A: End-to-End Document Q&A Latency

| Test ID | Test Case | Input | Success Criteria |
|---------|-----------|-------|-----------------|
| A1 | Simple factual query, single-page answer | 10-page PDF, "What is the fee for X?" | E2E < 3s, TTFT < 1s |
| A2 | Multi-chunk reasoning query | 50-page document, "Compare provisions in sections 3 and 7" | E2E < 8s, TTFT < 2s |
| A3 | Needle-in-haystack retrieval | 100-page document, fact on page 73 | E2E < 10s, correct page retrieved |
| A4 | Multi-document synthesis | 5 documents × 20 pages, cross-reference query | E2E < 15s, cites ≥ 2 sources |
| A5 | Short-context fast path | 2-page document, simple extraction | E2E < 1.5s (T1+T2 only, no T3) |

#### Category B: KV Cache Memory Efficiency

| Test ID | Test Case | Measurement Method | Success Criteria |
|---------|-----------|-------------------|-----------------|
| B1 | Baseline KV memory (f16) | `nvidia-smi` before/after 4K context fill | Establish baseline |
| B2 | q8_0 KV cache | Same measurement at identical context | ≥ 45% reduction vs. B1 |
| B3 | q4_0 KV cache | Same measurement | ≥ 70% reduction vs. B1 |
| B4 | K:q8_0/V:q4_0 split | Same measurement | ≥ 55% reduction vs. B1 |
| B5 | Max context with quantized KV | Increase context until OOM, measure max | ≥ 2x context length vs. B1 |
| B6 | Perplexity impact | Run perplexity benchmark on WikiText-2 for each KV type | < 1% degradation for q8_0, < 3% for q4_0 |

#### Category C: Answer Quality and Relevance

| Test ID | Test Case | Scoring Method | Success Criteria |
|---------|-----------|---------------|-----------------|
| C1 | RAGAS Faithfulness | Automated RAGAS evaluation on 50 Q&A pairs | Score ≥ 0.85 |
| C2 | RAGAS Answer Relevancy | Same dataset | Score ≥ 0.80 |
| C3 | Retrieval Precision@5 | Known-answer test set, check if correct chunk in top 5 | ≥ 90% |
| C4 | Retrieval Recall@10 | Same test set, all relevant chunks | ≥ 85% |
| C5 | Quality degradation under KV quantization | Compare C1/C2 scores across f16, q8_0, q4_0 | < 5% score drop at q8_0 |
| C6 | Tier fallback quality | Force T2 to handle T3 queries | < 15% quality drop vs. T3 |

#### Category D: Throughput Under Concurrent Load

| Test ID | Test Case | Load Pattern | Success Criteria |
|---------|-----------|-------------|-----------------|
| D1 | Single user, sequential queries | 1 req/s for 60s | Stable latency, no degradation |
| D2 | 3 concurrent users | 3 parallel streams, 1 req/5s each | P95 latency < 2x single-user |
| D3 | Burst load | 10 requests in 2 seconds | All complete within 30s, no OOM |
| D4 | Mixed workload | Interleaved simple + complex queries | Simple queries unaffected by complex |
| D5 | Sustained load with model switching | 100 queries alternating T2/T3 | No memory leak over time |

### Metric Definitions

| Metric | Definition | Collection Point |
|--------|-----------|-----------------|
| **TTFT** (Time to First Token) | Time from request receipt to first streamed token | FastAPI middleware |
| **ITL** (Inter-Token Latency) | Average time between consecutive tokens | Streaming response handler |
| **E2E Latency** | Total time from request receipt to final response | FastAPI middleware |
| **Retrieval Latency** | Time for PageIndex to return scored chunks | Pre/post retrieval function |
| **Model Load Time** | Time to load a model into VRAM via LM Studio SDK | Model manager wrapper |
| **VRAM Utilization** | Current GPU memory usage as percentage | `pynvml` polling |
| **KV Cache Size** | Memory consumed by KV cache for active requests | Computed from context length × model config |
| **Throughput (tok/s)** | Tokens generated per second across all requests | Aggregated from streaming responses |
| **Queue Depth** | Number of pending requests per priority level | Priority queue instrumentation |
| **Cache Hit Rate** | Percentage of KV cache reuse across requests | LM Studio server logs (if available) |

### FastAPI Instrumentation Points

The benchmarking harness instruments the FastAPI layer at seven specific points using OpenTelemetry spans:

```python
from opentelemetry import trace
from fastapi import FastAPI, Request
from time import perf_counter

tracer = trace.get_tracer("deeptutor.benchmark")

@app.middleware("http")
async def benchmark_middleware(request: Request, call_next):
    """POINT 1: Request-level E2E timing"""
    start = perf_counter()
    request.state.start_time = start
    request.state.metrics = {}
    
    response = await call_next(request)
    
    e2e_ms = (perf_counter() - start) * 1000
    metrics_collector.record("e2e_latency_ms", e2e_ms, {
        "path": request.url.path,
        "model_tier": request.state.metrics.get("model_tier", "unknown"),
    })
    return response

async def pageindex_retrieve(query: str, doc_id: str):
    """POINT 2: Retrieval stage timing"""
    with tracer.start_as_current_span("pageindex.retrieve") as span:
        start = perf_counter()
        
        # POINT 3: Embedding generation
        with tracer.start_as_current_span("pageindex.embed_query"):
            query_embedding = await embed_query(query)
        
        # POINT 4: Vector search + scoring
        with tracer.start_as_current_span("pageindex.vector_search"):
            scored_chunks = await vector_search(query_embedding, doc_id)
        
        retrieval_ms = (perf_counter() - start) * 1000
        span.set_attribute("retrieval.latency_ms", retrieval_ms)
        span.set_attribute("retrieval.chunks_returned", len(scored_chunks))
        return scored_chunks

async def deeptutor_reason(query: str, chunks: list):
    """POINT 5: Reasoning stage timing"""
    with tracer.start_as_current_span("deeptutor.reason") as span:
        model_tier = select_model_tier(query, chunks)
        span.set_attribute("reasoning.model_tier", model_tier)
        span.set_attribute("reasoning.input_tokens", count_tokens(chunks))
        
        # POINT 6: LM Studio inference call
        with tracer.start_as_current_span("lmstudio.inference") as inf_span:
            ttft_start = perf_counter()
            first_token_received = False
            tokens = []
            
            async for token in stream_from_lmstudio(model_tier, prompt):
                if not first_token_received:
                    ttft_ms = (perf_counter() - ttft_start) * 1000
                    inf_span.set_attribute("inference.ttft_ms", ttft_ms)
                    first_token_received = True
                tokens.append(token)
            
            inf_span.set_attribute("inference.total_tokens", len(tokens))
            inf_span.set_attribute("inference.model", model_tier)
        
        return "".join(tokens)

# POINT 7: Memory pressure monitoring (background task)
async def vram_monitor():
    """Runs every 2 seconds, records VRAM state"""
    while True:
        pressure = await check_memory_pressure()
        vram_info = get_vram_info()
        metrics_collector.record("vram_utilization_pct", vram_info.used_pct)
        metrics_collector.record("vram_free_mb", vram_info.free_mb)
        metrics_collector.record("memory_pressure_level", pressure)
        await asyncio.sleep(2)
```

### Benchmark Runner

```python
# benchmark_runner.py — orchestrates all test categories
import asyncio
import httpx
import json
from dataclasses import dataclass

@dataclass
class BenchmarkResult:
    test_id: str
    metric: str
    value: float
    passed: bool
    threshold: float

async def run_benchmark_suite(base_url: str = "http://localhost:8000"):
    results = []
    
    # Category A: E2E Latency
    for test in LATENCY_TESTS:
        async with httpx.AsyncClient(timeout=120) as client:
            start = perf_counter()
            ttft = None
            
            async with client.stream("POST", f"{base_url}/api/query",
                json=test.payload) as response:
                async for chunk in response.aiter_bytes():
                    if ttft is None:
                        ttft = (perf_counter() - start) * 1000
            
            e2e = (perf_counter() - start) * 1000
            results.append(BenchmarkResult(
                test_id=test.id, metric="e2e_ms",
                value=e2e, passed=e2e < test.e2e_threshold,
                threshold=test.e2e_threshold
            ))
    
    # Category D: Concurrent load
    for concurrency in [1, 3, 10]:
        tasks = [
            send_query(base_url, random.choice(QUERY_SET))
            for _ in range(concurrency)
        ]
        latencies = await asyncio.gather(*tasks)
        p95 = sorted(latencies)[int(len(latencies) * 0.95)]
        results.append(BenchmarkResult(
            test_id=f"D_concurrent_{concurrency}",
            metric="p95_latency_ms", value=p95,
            passed=p95 < CONCURRENT_THRESHOLD[concurrency],
            threshold=CONCURRENT_THRESHOLD[concurrency]
        ))
    
    return results
```

---

## 4. Model Switching Logic

### Decision Signals

The model switching engine evaluates four signals to determine which tier handles a request:

| Signal | Source | Measurement | Weight |
|--------|--------|------------|--------|
| **Query Complexity Score** | Query analysis (T1) | Token count, question word analysis, presence of comparison/reasoning keywords | 0.35 |
| **Document Size** | PageIndex metadata | Total pages, total tokens in retrieved chunks | 0.25 |
| **Retrieved Chunk Count** | PageIndex retrieval | Number of chunks scoring above relevance threshold | 0.15 |
| **Available VRAM** | Memory pressure monitor | Current free VRAM in MB | 0.25 |

### Complexity Scoring Function

```python
def compute_complexity_score(query: str, doc_metadata: dict, 
                              retrieval_result: dict) -> float:
    """Returns 0.0 (trivial) to 1.0 (maximum complexity)."""
    score = 0.0
    
    # Signal 1: Query linguistic complexity (weight: 0.35)
    query_tokens = len(query.split())
    has_comparison = any(w in query.lower() for w in [
        "compare", "contrast", "difference", "versus", "vs",
        "pros and cons", "advantages", "disadvantages"
    ])
    has_reasoning = any(w in query.lower() for w in [
        "why", "how", "explain", "analyze", "evaluate",
        "implications", "consequences", "recommend"
    ])
    has_multi_part = "and" in query.lower() or ";" in query
    
    query_score = min(1.0, (
        (query_tokens / 50) * 0.3 +          # Longer queries = more complex
        (0.3 if has_comparison else 0.0) +
        (0.25 if has_reasoning else 0.0) +
        (0.15 if has_multi_part else 0.0)
    ))
    score += query_score * 0.35
    
    # Signal 2: Document size (weight: 0.25)
    total_pages = doc_metadata.get("total_pages", 1)
    total_tokens = doc_metadata.get("total_tokens", 500)
    doc_score = min(1.0, (
        (total_pages / 100) * 0.5 +
        (total_tokens / 50000) * 0.5
    ))
    score += doc_score * 0.25
    
    # Signal 3: Retrieved chunk count (weight: 0.15)
    relevant_chunks = retrieval_result.get("chunk_count", 1)
    chunk_score = min(1.0, relevant_chunks / 10)
    score += chunk_score * 0.15
    
    # Signal 4: Available VRAM (weight: 0.25)
    # Inverse: less VRAM = higher pressure to use lighter models
    vram_free_gb = get_free_vram_gb()
    vram_score = max(0.0, 1.0 - (vram_free_gb / 12))  # 12 GB = "plenty"
    score += vram_score * 0.25
    
    return score
```

### Decision Tree

```
                    compute_complexity_score(query)
                              │
                    ┌─────────┼──────────┐
                    │         │          │
              score < 0.3   0.3-0.6   score > 0.6
                    │         │          │
                 USE T1     USE T2    USE T3
              (fast path)  (balanced) (quality path)
                    │         │          │
                    │         │     ┌────┴────┐
                    │         │   T3 loaded?  T3 not loaded
                    │         │     │              │
                    │         │   USE T3    VRAM > 10GB free?
                    │         │              │          │
                    │         │            YES         NO
                    │         │              │          │
                    │         │         LOAD T3    USE T2
                    │         │         (async)   (fallback)
                    │         │              │
                    │         │         TTL = 300s
                    │         │
                    └─────────┴──── Return response
```

### Fallback Order

When the preferred tier is unavailable (VRAM constraint or model load failure):

| Preferred | Fallback 1 | Fallback 2 | Behavior Change |
|-----------|-----------|-----------|----------------|
| T3 (14B+) | T2 (8B) | T2 (4B) | Increase max_tokens, add "be thorough" system prompt |
| T2 (8B) | T2 (4B) | T1 (1.7B) | Reduce context to first 2K tokens |
| T1 (1.7B) | T1 (0.6B) | Error | Should never fail — T1 always resident |

### FastAPI Model Manager

```python
class ModelManager:
    """Manages model lifecycle via LM Studio SDK."""
    
    def __init__(self, lmstudio_base_url: str = "http://localhost:1234"):
        self.base_url = lmstudio_base_url
        self.loaded_models: dict[str, ModelState] = {}
        self.tier_configs = {
            "T1": ModelTierConfig(
                models=["qwen3-0.6b-q4_k_m", "qwen3-1.7b-q4_k_m"],
                kv_cache_type_k="q4_0", kv_cache_type_v="q4_0",
                context_length=4096, ttl=None,  # Always resident
                max_concurrent=4,
            ),
            "T2": ModelTierConfig(
                models=["qwen3-4b-q4_k_m", "qwen3-8b-q5_k_m"],
                kv_cache_type_k="q8_0", kv_cache_type_v="q4_0",
                context_length=8192, ttl=600,  # 10 min idle
                max_concurrent=2,
            ),
            "T3": ModelTierConfig(
                models=["qwen3-14b-q4_k_m", "qwen3-30b-a3b-q4_k_m"],
                kv_cache_type_k="q8_0", kv_cache_type_v="q8_0",
                context_length=16384, ttl=300,  # 5 min idle
                max_concurrent=1,
            ),
        }
    
    async def get_model_for_tier(self, tier: str) -> str:
        """Returns model identifier, loading if necessary."""
        config = self.tier_configs[tier]
        
        # Try each model in the tier, from largest to smallest
        for model_id in reversed(config.models):
            if model_id in self.loaded_models:
                return model_id
        
        # Need to load — check VRAM
        pressure = await check_memory_pressure()
        if pressure in ("ORANGE", "RED") and tier == "T3":
            # Fallback to T2
            return await self.get_model_for_tier("T2")
        
        # Load the best model that fits
        for model_id in reversed(config.models):
            estimated_vram = estimate_vram(model_id)
            if estimated_vram < get_free_vram_mb():
                await self._load_model(model_id, config)
                return model_id
        
        # Nothing fits — fall back to lower tier
        fallback = {"T3": "T2", "T2": "T1"}.get(tier)
        if fallback:
            return await self.get_model_for_tier(fallback)
        raise RuntimeError("Cannot load any model — system out of memory")
    
    async def _load_model(self, model_id: str, config: ModelTierConfig):
        """Load model via LM Studio's OpenAI-compatible API."""
        # LM Studio SDK supports loading with custom config
        # via the TypeScript SDK or REST endpoint
        async with httpx.AsyncClient() as client:
            # This uses LM Studio's model management API
            await client.post(f"{self.base_url}/api/v0/models/load", json={
                "model": model_id,
                "context_length": config.context_length,
                "gpu_offload": "max",
            })
        self.loaded_models[model_id] = ModelState(
            loaded_at=time.time(), last_used=time.time()
        )
```

> **Note**: LM Studio's REST API for programmatic model loading is available via the [TypeScript SDK](https://lmstudio.ai/docs/typescript/manage-models/loading) (`client.llm.load()`). The Python-side integration above calls LM Studio's internal API; the exact endpoint path (`/api/v0/models/load`) should be verified against your LM Studio version. An alternative is to use the `lms` CLI tool via subprocess.

---

## 5. Performance Dashboard

### Architecture

```
┌─────────────────┐     WebSocket      ┌──────────────────┐
│  React/Next.js   │◄──────────────────►│   FastAPI Backend  │
│  Dashboard UI    │   /ws/metrics      │                    │
│                  │                    │  MetricsCollector  │
│  Components:     │     REST           │  ├─ VRAMMonitor    │
│  - MetricsGrid   │◄──────────────────►│  ├─ LatencyTracker │
│  - LatencyChart  │   /api/metrics/*   │  ├─ QueueMonitor   │
│  - VRAMGauge     │                    │  └─ ModelRegistry  │
│  - ModelStatus   │                    │                    │
│  - QueueView     │                    │  OpenTelemetry     │
│  - BenchResults  │                    │  └─ Jaeger export  │
└─────────────────┘                    └──────────────────┘
```

### Backend API Endpoints

#### WebSocket: Real-Time Metrics Stream

```
WS /ws/metrics
```

Pushes every 2 seconds. Payload:

```typescript
interface MetricsFrame {
  timestamp: number;           // Unix epoch ms
  vram: {
    total_mb: number;
    used_mb: number;
    free_mb: number;
    utilization_pct: number;
    pressure_level: "GREEN" | "YELLOW" | "ORANGE" | "RED";
  };
  models: {
    model_id: string;
    tier: "T1" | "T2" | "T3";
    loaded: boolean;
    vram_mb: number;
    active_requests: number;
    tokens_generated_total: number;
    avg_tok_per_sec: number;
  }[];
  inference: {
    active_requests: number;
    queued_requests: number;
    avg_ttft_ms: number;        // Rolling 60s window
    avg_itl_ms: number;
    avg_e2e_ms: number;
    p95_e2e_ms: number;
    throughput_tok_per_sec: number;
  };
  queue: {
    retrieval_depth: number;
    reasoning_depth: number;
    generation_depth: number;
  };
  kv_cache: {
    total_allocated_mb: number;
    per_model: {
      model_id: string;
      kv_type_k: string;
      kv_type_v: string;
      context_used: number;
      context_max: number;
      kv_size_mb: number;
    }[];
  };
}
```

#### REST: Historical Metrics and Benchmarks

```
GET /api/metrics/history?window=3600&resolution=10
  → TimeseriesData[]  (VRAM, latency, throughput over time)

GET /api/metrics/models
  → ModelStatus[]  (current state of all loaded/available models)

GET /api/metrics/benchmarks/latest
  → BenchmarkResult[]  (last benchmark run results)

POST /api/metrics/benchmarks/run
  → { run_id: string }  (trigger benchmark suite, returns ID for polling)

GET /api/metrics/benchmarks/{run_id}
  → BenchmarkRunStatus  (poll for completion and results)
```

### Frontend Component Specification

#### Component 1: MetricsGrid

- Purpose: Top-level KPI cards showing current system state at a glance.
- Data source: WebSocket `MetricsFrame`
- Update cadence: Every 2 seconds
- Cards:
  - **Active Model Tier** — Shows which tier is currently handling requests (T1/T2/T3)
  - **VRAM Usage** — Current utilization as percentage with color coding matching pressure level
  - **Avg Latency** — Rolling 60s average E2E latency in ms
  - **Throughput** — Current tokens/second across all models
  - **Queue Depth** — Total pending requests across all priority levels
  - **Memory Pressure** — GREEN/YELLOW/ORANGE/RED with semantic meaning

#### Component 2: LatencyChart

- Purpose: Time-series line chart showing latency breakdown over the last hour.
- Data source: REST `/api/metrics/history` on mount + WebSocket append
- Update cadence: Append new data point every 2 seconds; full refresh every 60 seconds
- Lines:
  - TTFT (ms) — blue
  - E2E Latency (ms) — green
  - Retrieval Latency (ms) — orange
  - P95 E2E (ms) — red dashed
- Interaction: Hover for exact values. Click to freeze. Zoom on time axis.

```typescript
interface LatencyChartProps {
  data: TimeseriesPoint[];
  windowSeconds: number;       // Default 3600
  refreshInterval: number;     // Default 2000ms
}

interface TimeseriesPoint {
  timestamp: number;
  ttft_ms: number;
  e2e_ms: number;
  retrieval_ms: number;
  p95_e2e_ms: number;
}
```

#### Component 3: VRAMGauge

- Purpose: Visual gauge showing VRAM allocation breakdown by category.
- Data source: WebSocket `MetricsFrame.vram` + `MetricsFrame.kv_cache`
- Update cadence: Every 2 seconds
- Segments:
  - Model weights (per loaded model)
  - KV cache (per loaded model)
  - System/overhead
  - Free
- Visual: Stacked horizontal bar with color-coded segments. Pressure level indicator.

```typescript
interface VRAMGaugeProps {
  totalMB: number;
  segments: VRAMSegment[];
  pressureLevel: "GREEN" | "YELLOW" | "ORANGE" | "RED";
}

interface VRAMSegment {
  label: string;               // "Qwen3-8B Weights", "Qwen3-8B KV Cache"
  sizeMB: number;
  category: "weights" | "kv_cache" | "system" | "free";
}
```

#### Component 4: ModelStatus

- Purpose: Table showing all model tiers, their current state, and key stats.
- Data source: WebSocket `MetricsFrame.models`
- Update cadence: Every 2 seconds
- Columns: Tier, Model ID, Status (Loaded/Unloaded/Loading), VRAM, Active Requests, Avg tok/s, KV Cache Type, Context Used/Max
- Actions: Manual Load/Unload buttons (POST to `/api/models/{id}/load` or `/unload`)

#### Component 5: QueueView

- Purpose: Real-time visualization of the priority queue state.
- Data source: WebSocket `MetricsFrame.queue`
- Update cadence: Every 2 seconds
- Display: Three horizontal bars (Retrieval, Reasoning, Generation) showing queue depth. Color intensity increases with depth.

#### Component 6: BenchmarkResults

- Purpose: Display results from the most recent benchmark run.
- Data source: REST `/api/metrics/benchmarks/latest`
- Update cadence: On mount + after triggered run completes
- Display: Table of test results with pass/fail indicators, grouped by category (A/B/C/D). Expandable rows for detailed metrics.
- Action: "Run Benchmarks" button triggers POST to `/api/metrics/benchmarks/run`

### WebSocket Implementation (FastAPI)

```python
from fastapi import WebSocket
import asyncio
import json

class MetricsWebSocket:
    def __init__(self):
        self.active_connections: list[WebSocket] = []
        self.metrics_collector = MetricsCollector()
    
    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
    
    async def broadcast_metrics(self):
        """Runs as background task, broadcasts every 2 seconds."""
        while True:
            frame = self.metrics_collector.get_current_frame()
            payload = json.dumps(frame, default=str)
            
            disconnected = []
            for ws in self.active_connections:
                try:
                    await ws.send_text(payload)
                except Exception:
                    disconnected.append(ws)
            
            for ws in disconnected:
                self.active_connections.remove(ws)
            
            await asyncio.sleep(2)

metrics_ws = MetricsWebSocket()

@app.websocket("/ws/metrics")
async def websocket_endpoint(websocket: WebSocket):
    await metrics_ws.connect(websocket)
    try:
        while True:
            await websocket.receive_text()  # Keep connection alive
    except Exception:
        metrics_ws.active_connections.remove(websocket)

@app.on_event("startup")
async def startup():
    asyncio.create_task(metrics_ws.broadcast_metrics())
```

---

## Implementation Sequence

| Phase | Deliverable | Dependencies | Estimated Effort |
|-------|------------|-------------|-----------------|
| 1 | Model Manager + T1/T2/T3 loading via LM Studio SDK | LM Studio installed, GGUF models downloaded | 2–3 days |
| 2 | Priority Queue + FastAPI middleware instrumentation | Phase 1 | 1–2 days |
| 3 | Memory pressure monitor + fallback cascade | Phase 1 + pynvml | 1 day |
| 4 | Complexity scoring + model switching decision tree | Phase 1 + 2 | 2 days |
| 5 | KV cache quantization configuration per tier | Phase 1 (llama.cpp flags) | 1 day |
| 6 | Benchmark harness + test cases A/B/C/D | Phase 1–4 | 3–4 days |
| 7 | WebSocket metrics stream + REST endpoints | Phase 2 + 3 | 2 days |
| 8 | React dashboard components | Phase 7 | 3–4 days |
| 9 | Integration testing + benchmark validation | All phases | 2–3 days |

---

## Verification Status Summary

| Claim | Status | Source |
|-------|--------|--------|
| TurboQuant achieves 6x KV cache compression at 3.5 bits | Verified | [Google Research blog](https://research.google/blog/turboquant-redefining-ai-efficiency-with-extreme-compression/), ICLR 2026 |
| TurboQuant uses PolarQuant + QJL two-stage pipeline | Verified | [Google Research blog](https://research.google/blog/turboquant-redefining-ai-efficiency-with-extreme-compression/) |
| TurboQuant is integrated into llama.cpp / LM Studio | **Not verified — assumed unavailable** | No evidence of integration as of March 2026 |
| LM Studio supports loading multiple models simultaneously | Verified | [LM Studio SDK docs](https://lmstudio.ai/docs/typescript/manage-models/loading) |
| LM Studio supports parallel requests (default: 4 concurrent) | Verified | [LM Studio docs](https://lmstudio.ai/docs/app/advanced/parallel-requests) |
| llama.cpp supports q4_0/q8_0 KV cache quantization | Verified | [llama.cpp GitHub](https://github.com/ggml-org/llama.cpp/issues/15039), community benchmarks |
| K:q8_0/V:q4_0 yields 59% memory reduction, 0.86% perplexity loss | Verified | [KVSplit research](https://news.ycombinator.com/item?id=44009321) |
| Qwen3 models available in GGUF on LM Studio | Verified | [LM Studio SDK examples](https://lmstudio.ai/docs/typescript/manage-models/loading) reference `qwen/qwen3-4b-2507` |
| Qwen3-30B-A3B achieves RAGAS faithfulness 0.91 | Claimed by single source | [Prem AI benchmark](https://blog.premai.io/best-open-source-llms-for-rag-in-2026-10-models-ranked-by-retrieval-accuracy/) — independent verification recommended |
| Snowflake Arctic Embed GGUF available for LM Studio | Verified | [Hugging Face model card](https://huggingface.co/ChristianAzinn/snowflake-arctic-embed-m-gguf) |
| LM Studio internal model load API path (/api/v0/models/load) | **Reasoned estimate** | Exact REST endpoint for programmatic loading not documented; use TypeScript SDK or `lms` CLI as verified alternatives |
| VRAM estimates per model tier | Reasoned estimates | Based on parameter count × bit-width; actual varies with context length and batch size |
