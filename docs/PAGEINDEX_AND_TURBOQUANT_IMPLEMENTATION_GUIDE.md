# PageIndex & TurboQuant: In-Depth Implementation Research

---

## Part 1: PageIndex — Vectorless, Reasoning-Based RAG

### What It Is

PageIndex is a vectorless RAG framework developed by [Vectify AI](https://pageindex.ai/blog/pageindex-intro) that completely eliminates vector databases, embeddings, and artificial chunking. Instead, it builds a hierarchical tree-structured index from documents and uses LLM reasoning to navigate that tree — mimicking how a human expert scans a table of contents, picks a chapter, reads the relevant section, and backtracks if needed.

It achieved [98.7% accuracy on FinanceBench](https://www.linkedin.com/posts/avi-chawla_everyoneissleepingonthisnewragapproach-activity-7420401978121576448-dUcH), significantly outperforming traditional vector-based RAG.

- **GitHub**: [VectifyAI/PageIndex](https://github.com/VectifyAI/PageIndex)
- **Official Site**: [pageindex.ai](https://pageindex.ai/blog/pageindex-intro)

---

### Core Architecture

#### 1. Document Segmentation

Rather than splitting text into fixed-size chunks (which breaks context), PageIndex divides documents along natural boundaries — headings, subheadings, topic changes, and page breaks. Each resulting segment covers a coherent idea. The system uses OCR that [understands the entire document as a single structure](https://gaodalie.substack.com/p/rag-is-not-dead-no-chunking-no-vectors), preserving headings and tables.

#### 2. Tree Index Construction

After segmentation, PageIndex builds a JSON-based hierarchical "Table of Contents" tree. According to the [official documentation](https://pageindex.ai/blog/pageindex-intro), each node in this tree follows this schema:

```json
{
  "node_id": "string",       // Unique identifier
  "title": "string",         // Human-readable label
  "start_index": 21,         // Start page
  "end_index": 22,           // End page
  "summary": "string",       // LLM-generated summary of the section
  "sub_nodes": [...]          // Recursive child nodes
}
```

- The **root** represents the whole document
- **Middle nodes** represent sections and subsections
- **Leaf nodes** represent individual pages or paragraphs
- Each `node_id` maps to the corresponding **raw content** (text, images, tables)

The tree construction itself is LLM-assisted — the LLM reads page content, headings, and structure, then generates summaries per section and assembles the hierarchical tree. For a [50-page PDF, this typically takes 30–90 seconds](https://www.youtube.com/watch?v=nkbtOplq9jM).

#### 3. In-Context Index (Key Insight)

Unlike a vector database which stores an external, static embeddings index, the JSON tree resides **within the LLM's active reasoning context**. Vectify calls this an [in-context index](https://pageindex.ai/blog/pageindex-intro) — the model can directly reference, navigate, and reason over the structure during inference.

---

### Retrieval Algorithm (Step-by-Step)

The retrieval is an iterative reasoning loop, [inspired by AlphaGo's tree search](https://github.com/run-llama/llama_index/discussions/18360):

1. **Read the ToC** — The LLM receives the tree (titles + summaries only, not full text) and understands the document structure
2. **Select a Section** — The LLM reasons about which section most likely contains the answer (e.g., "Debt trends are usually in the financial summary or Appendix G")
3. **Extract Information** — The system retrieves the full text of the selected node by its `node_id`
4. **Evaluate Sufficiency** — If the answer is complete, proceed to generation. If not, return to step 1
5. **Follow Cross-References** — If the text says "see Appendix G," the LLM navigates the tree to that section
6. **Generate Answer** — Once enough context is assembled, the LLM generates the response

This is fundamentally different from vector search. As noted on [Hacker News](https://news.ycombinator.com/item?id=45036944), the entire process uses iterative and recursive LLM calls — it is technically vectorless, but heavily LLM-dependent.

---

### Implementation (Python SDK)

#### Key SDK Methods

| Method                            | Purpose                              |
| --------------------------------- | ------------------------------------ |
| `submit_document(file_path)`      | Upload PDF for indexing              |
| `is_retrieval_ready(doc_id)`      | Check if tree is built               |
| `get_tree(doc_id, node_summary=True)` | Get the hierarchical JSON tree   |
| `submit_query(doc_id, query)`     | Submit a retrieval query             |
| `get_retrieval(retrieval_id)`     | Poll for retrieval results           |
| `chat_completions(messages)`      | Direct streaming chat API            |

Source: [GeeksforGeeks PageIndex Tutorial](https://www.geeksforgeeks.org/artificial-intelligence/vectorless-rag-pageindex/)

#### Complete Working Example

```python
# Step 1: Install
# pip install pageindex langchain langchain-google-genai google-generativeai

# Step 2: Imports
import os, json, requests, time
from pageindex import PageIndexClient
import pageindex.utils as utils

# Step 3: Initialize client
PAGEINDEX_API_KEY = "your-api-key"
pi_client = PageIndexClient(api_key=PAGEINDEX_API_KEY)

# Step 4: Submit document
pdf_path = "your_document.pdf"
doc_info = pi_client.submit_document(pdf_path)
doc_id = doc_info["doc_id"]

# Step 5: Wait for indexing
max_retries = 30
retry_count = 0
while not pi_client.is_retrieval_ready(doc_id):
    if retry_count >= max_retries:
        print("Timeout: Document processing took too long.")
        break
    print(f"Still processing... (Attempt {retry_count + 1}/{max_retries})")
    time.sleep(5)
    retry_count += 1

# Step 6: Get tree structure
if pi_client.is_retrieval_ready(doc_id):
    tree = pi_client.get_tree(doc_id, node_summary=True)['result']
    utils.print_tree(tree)

# Step 7: Vectorless retrieval function
def retrieve_from_pageindex(query, doc_id, top_k=3):
    response = pi_client.submit_query(doc_id=doc_id, query=query)
    retrieval_id = response.get("retrieval_id")
    if not retrieval_id:
        return []

    while True:
        retrieval = pi_client.get_retrieval(retrieval_id)
        status = retrieval.get("status")
        if status == "completed":
            break
        elif status == "failed":
            return []
        time.sleep(1)

    nodes = retrieval.get("retrieved_nodes", [])
    contexts = []
    for node in nodes[:top_k]:
        relevant_contents = node.get("relevant_contents", [])
        for group in relevant_contents:
            for item in group:
                content = item.get("relevant_content")
                if content:
                    contexts.append(content)
    return contexts

# Step 8: Full RAG pipeline
def vectorless_rag(query, doc_id):
    contexts = retrieve_from_pageindex(query, doc_id)
    if not contexts:
        return "No relevant context found."

    combined_context = "\n\n".join(contexts)
    prompt = f"""
    You are a research assistant.
    Answer ONLY using the context below.
    If the answer is not found, say "Not found in document."

    Context:
    {combined_context}

    Question:
    {query}
    """
    response = llm.invoke(prompt)
    return response.content

# Step 9: Query
answer = vectorless_rag("What is the main contribution of this paper?", doc_id)
print(answer)
```

Source: [GeeksforGeeks](https://www.geeksforgeeks.org/artificial-intelligence/vectorless-rag-pageindex/) and [Dev.to Bob Implementation](https://dev.to/aairom/bob-strikes-again-pageindex-test-and-implementation-5ae)

#### Vision RAG Variant

PageIndex also supports a Vision RAG mode where:
- PDF pages are converted to images using PyMuPDF
- The tree structure maps nodes to physical page numbers
- A vision-language model (e.g., LLaVA) receives the page images as context
- Useful for chart-heavy or diagram-rich documents

Source: [VectifyAI Vision RAG Notebook](https://github.com/VectifyAI/PageIndex/blob/main/cookbook/vision_RAG_pageindex.ipynb)

---

### Comparison: Vector RAG vs PageIndex

| Feature                   | Traditional Vector RAG                          | PageIndex (Vectorless RAG)                        |
| ------------------------- | ----------------------------------------------- | ------------------------------------------------- |
| Retrieval Method          | Embedding similarity search                     | LLM reasoning + tree navigation                   |
| Document Representation   | High-dimensional vectors                        | Hierarchical JSON tree                             |
| Search Process            | One-shot top-k similarity                       | Iterative section-by-section reasoning             |
| Context Usage             | May include loosely related chunks               | Only logically relevant sections                   |
| Chunking                  | Fixed-size, breaks context                      | Natural section boundaries                         |
| Cross-References          | Cannot follow "see Appendix G"                  | Follows references via tree navigation             |
| Explainability            | Opaque similarity scores                        | Traceable reasoning path                           |
| Infrastructure            | Requires embedding model + vector DB            | No vector DB needed                                |
| Speed                     | Fast similarity lookup                          | Slower (multiple LLM calls)                        |
| Best For                  | Short docs, general-purpose                     | Long structured docs (financial, legal, technical) |

Source: [GeeksforGeeks](https://www.geeksforgeeks.org/artificial-intelligence/vectorless-rag-pageindex/)

---

### Limitations

- Heavily depends on document structure quality — poorly organized documents hurt accuracy
- Slower than vector search due to step-by-step LLM reasoning
- Less effective across many unrelated documents (best for single long documents)
- LLM may sometimes reason down the wrong branch
- The [Hacker News community noted](https://news.ycombinator.com/item?id=45036944) that claims of improved retrieval time are debatable — vector search with specialized hardware is highly efficient
- The entire system relies on iterative LLM calls, which adds cost and latency

---

---

## Part 2: TurboQuant — Near-Optimal KV Cache Compression

### What It Is

TurboQuant is a vector quantization algorithm [published by Google Research](https://research.google/blog/turboquant-redefining-ai-efficiency-with-extreme-compression/) (March 2026, to appear at ICLR 2026) that compresses the KV cache — the biggest memory bottleneck during LLM inference — down to 3–4 bits per element with negligible quality loss. It requires no training data, no calibration, and no model-specific tuning.

The [arxiv paper](https://arxiv.org/abs/2504.19874) demonstrates near-optimal distortion rates within a factor of ~2.7 of the information-theoretic lower bound.

- **Paper**: [arxiv.org/abs/2504.19874](https://arxiv.org/abs/2504.19874)
- **Google Blog**: [research.google/blog/turboquant](https://research.google/blog/turboquant-redefining-ai-efficiency-with-extreme-compression/)

---

### The Problem It Solves

During LLM inference, every token generates key-value (KV) pairs that must be stored for attention computation. At long context lengths (32K–128K tokens), this KV cache can consume more memory than the model weights themselves. TurboQuant provides a [4–6x reduction](https://dev.to/arshtechpro/turboquant-what-developers-need-to-know-about-googles-kv-cache-compression-eeg) in KV cache memory.

---

### Two-Stage Architecture

#### Stage 1: PolarQuant (b-1 bits) — MSE-Optimal Compression

##### Step 1: Random Rotation

The input KV vector **x** ∈ ℝᵈ is multiplied by a random orthogonal rotation matrix **Π**, generated via QR decomposition of a random Gaussian matrix. This rotation is computed once and reused.

According to the [arxiv paper](https://arxiv.org/html/2504.19874v1):

- After rotation, each coordinate follows a **Beta distribution**:

  ```
  f_X(x) = Γ(d/2) / (√π · Γ((d-1)/2)) · (1 - x²)^((d-3)/2),  x ∈ [-1, 1]
  ```

- In high dimensions, this converges to **N(0, 1/d)** by the Central Limit Theorem
- Coordinates become **nearly independent** — this is the key insight enabling per-coordinate scalar quantization

As the [Baseten deep-dive](https://www.baseten.co/blog/i-spent-31-hours-on-the-math-behind-turboquant-so-you-dont-have-to/) explains: "All the math was to get to a point where we can say: I know the exact distribution my data will follow. This means I know exactly where my optimal quantization buckets fall."

##### Step 2: Polar Coordinate Transformation

PolarQuant converts the rotated vector from Cartesian coordinates to polar coordinates using a [recursive algorithm](https://www.baseten.co/blog/i-spent-31-hours-on-the-math-behind-turboquant-so-you-dont-have-to/):

```python
r = y.clone()
angles = []

for level in range(n_levels):   # n_levels = log₂(d)
    a = r[0::2]                  # even indices
    b = r[1::2]                  # odd indices

    # Compute angles
    level_angles = torch.atan2(b, a)

    if level == 0:
        # Level 1: raw coordinates can be negative → [0, 2π)
        level_angles = level_angles % (2 * np.pi)
    # Level 2+: radii are always positive → angles in [0, π/2]

    # Compute new radii
    new_r = torch.sqrt(a**2 + b**2)

    angles.append(level_angles)
    r = new_r    # carry radii to next level

return angles, r   # final radius + all angle levels
```

This pairs coordinates, converts each pair to (radius, angle), then recursively pairs the radii. The result: a single final radius plus a hierarchy of angles. The angles at each level follow increasingly concentrated distributions centered around π/4.

##### Step 3: Lloyd-Max Codebook Construction

Since the angle distributions are known analytically (they depend only on the dimension, not the data), TurboQuant [precomputes optimal quantization codebooks](https://arxiv.org/html/2504.19874v1) using the Lloyd-Max algorithm — a 1D k-means that minimizes expected squared error for a known PDF.

```python
def build_codebook(n_bits, lo, hi, level):
    n_codes = 2 ** n_bits
    exponent = (1 << level) - 1    # 2^(level-1) - 1

    # Build PDF from known angle distribution
    sin2theta = torch.sin(2 * theta)
    angles_pdf = torch.pow(sin2theta.clamp(min=0), exponent)
    weights = weights / weights.sum()

    # Initialize centroids via CDF inversion
    cdf = torch.cumsum(weights, dim=0)
    for i in range(n_codes):
        target = (i + 0.5) / n_codes
        idx = torch.searchsorted(cdf, target)
        centroids[i] = grid[idx]

    # Lloyd's algorithm refinement
    for iteration in range(n_iters):
        boundaries = torch.zeros(n_codes + 1)
        boundaries[0] = lo
        boundaries[-1] = hi
        for i in range(1, n_codes):
            boundaries[i] = 0.5 * (centroids[i-1] + centroids[i])

        old_centroids = centroids.clone()
        for c in range(n_codes):
            mask = (grid >= boundaries[c]) & (grid < boundaries[c+1])
            w = weights[mask]
            if w.sum() > 1e-15:
                centroids[c] = (w * grid[mask]).sum() / w.sum()

        if (centroids - old_centroids).abs().max() < 1e-7:
            break

    return centroids
```

These codebooks are computed **once** and stored permanently. Quantization at runtime is just a lookup — find which bucket the angle falls into and store the index.

Source: [Baseten](https://www.baseten.co/blog/i-spent-31-hours-on-the-math-behind-turboquant-so-you-dont-have-to/)

##### Bit Allocation per Level (128-Dimensional Vector Example)

| Level | # Angles | Bits/Angle | Range     | Distribution                  | Total Bits |
| ----- | -------- | ---------- | --------- | ----------------------------- | ---------- |
| 1     | 64       | 4          | [0, 2π)   | Wider variance                | 256        |
| 2     | 32       | 2          | [0, π/2]  | Concentrated around π/4       | 64         |
| 3     | 16       | 2          | [0, π/2]  | Tighter around π/4            | 32         |
| 4     | 8        | 2          | [0, π/2]  | Even tighter                  | 16         |
| Radii | 8        | 16 (FP16)  | —         | —                             | 128        |
| **Total** |      |            |           |                               | **496 bits** |

- Original FP16 (128 × 16 bits): **2,048 bits**
- **Compression: 4.13×**

Source: [Baseten](https://www.baseten.co/blog/i-spent-31-hours-on-the-math-behind-turboquant-so-you-dont-have-to/)

---

#### Stage 2: QJL Residual Correction (1 bit)

After PolarQuant, there's a small residual error **ε = x - x̂_mse**. The critical insight from the [paper](https://arxiv.org/html/2504.19874v1) is that MSE-optimal quantizers are **biased** for inner product estimation — and attention scores are inner products.

TurboQuant applies the **Quantized Johnson-Lindenstrauss (QJL)** transform to this residual:

```
Q_qjl(r) = sign(S · r)
```

where **S** is a random Gaussian matrix (ℝᵈˣᵈ, i.i.d. N(0,1) entries).

This stores only the **sign bit** (+1 or -1) of each projected dimension — just 1 extra bit per coordinate.

**Why this works**: The [Vizuara analysis](https://vizuara.substack.com/p/turboquant-online-vector-quantization) explains that the sign bits recover the angle between vectors via Hamming agreement. Combined with the stored norm, you can reconstruct the full inner product. The result is a mathematically **unbiased** inner product estimator.

**Why 1 bit on the residual beats 1 more bit on the codebook**:

Adding an Nth codebook bit reduces MSE distortion by a factor of 3/4. But that extra bit operates in the same Cartesian MSE space the first N-1 bits already covered. The QJL bit operates in the **inner product space** where the codebook had zero coverage. Since these errors are in orthogonal subspaces relative to the attention objective, the marginal gain from QJL is much larger.

Source: [Vizuara Substack](https://vizuara.substack.com/p/turboquant-online-vector-quantization)

**Full quantization map**:

```
Q_prod(x) = [Q_mse(x), Q_qjl(r), ‖r‖₂]
```

**Reconstruction**:

```
x̃ = x̃_mse + ‖r‖₂ · Q_qjl⁻¹(Q_qjl(r / ‖r‖₂))
```

where `Q_qjl⁻¹(z) = (√(π/2) / d) · Sᵀ · z`

---

### Distortion Bounds (Theoretical Guarantees)

The [paper proves](https://arxiv.org/html/2504.19874v1) these guarantees for unit vectors:

#### MSE Distortion (Reconstruction Error)

| Bit-width | TurboQuant Upper Bound         | Lower Bound (any quantizer) | Gap Factor |
| --------- | ------------------------------ | --------------------------- | ---------- |
| Any b     | ≤ (√3·π/2) · 1/4ᵇ ≈ 2.7/4ᵇ  | ≥ 1/4ᵇ                     | ~2.7×      |
| b = 1     | ~0.36                          | —                           | ~1.45×     |
| b = 2     | ~0.117                         | —                           | —          |
| b = 3     | ~0.03                          | —                           | —          |
| b = 4     | ~0.009                         | —                           | —          |

#### Inner Product Distortion (Attention Score Error)

| Bit-width | TurboQuant Upper Bound                           |
| --------- | ------------------------------------------------ |
| Any b     | ≤ (√3·π²·‖y‖²) / (d · 4ᵇ)                      |
| b = 1     | ~1.57/d                                          |
| b = 2     | ~0.56/d                                          |
| b = 3     | ~0.18/d                                          |
| b = 4     | ~0.047/d                                         |

TurboQuant is within a factor of **~2.7** of the information-theoretic lower bound — meaning **no quantizer can do much better**.

---

### Practical Implementation Details

#### Basic Usage

```python
from transformers import AutoModelForCausalLM, AutoTokenizer
from turboquant import TurboQuantCache
import torch

model = AutoModelForCausalLM.from_pretrained(
    "Qwen/Qwen2.5-3B-Instruct",
    dtype=torch.float16,
    device_map="auto"
)
tokenizer = AutoTokenizer.from_pretrained("Qwen/Qwen2.5-3B-Instruct")

# Create compressed cache — that's it
cache = TurboQuantCache(bits=4)

inputs = tokenizer("Your prompt here", return_tensors="pt").to(model.device)
outputs = model(**inputs, past_key_values=cache, use_cache=True)
```

Source: [Dev.to TurboQuant Guide](https://dev.to/arshtechpro/turboquant-what-developers-need-to-know-about-googles-kv-cache-compression-eeg)

#### Outlier Handling

Channels are split into outlier/non-outlier groups with [independent bit allocations](https://arxiv.org/html/2504.19874v1):

- **2.5-bit config**: 32 outlier channels at 3 bits + 96 normal at 2 bits → (32×3 + 96×2)/128 = 2.5 bits/channel
- **3.5-bit config**: Higher precision ratio for better quality

#### Key Gotchas

From [community experiments](https://dev.to/arshtechpro/turboquant-what-developers-need-to-know-about-googles-kv-cache-compression-eeg):

- **4-bit is the sweet spot** — quality indistinguishable from FP16 on 3B+ models
- **3-bit works** but quality degrades on models smaller than 8B parameters
- **Values are more sensitive than keys** — 2-bit values degrade cosine similarity to ~0.94, while 4-bit maintains 0.997
- **Short contexts (<1K tokens) don't benefit** — overhead of rotation + quantization can be net negative
- **Residual window**: Most implementations keep the most recent 128–256 tokens in full FP16 and only compress older tokens
- **Pairs well with**: weight quantization (GPTQ, AWQ, GGUF), speculative decoding, and other serving optimizations

---

### Benchmark Results

From the [Google Research blog](https://research.google/blog/turboquant-redefining-ai-efficiency-with-extreme-compression/):

#### Quality Benchmarks (Llama-3.1-8B-Instruct, LongBench-E)

| Method       | Bits | SingleQA | MultiQA | Summarization | Few-shot | Synthetic | Code  | Average   |
| ------------ | ---- | -------- | ------- | ------------- | -------- | --------- | ----- | --------- |
| Full         | 16   | 45.29    | 45.16   | 26.55         | 68.38    | 59.54     | 46.28 | **50.06** |
| TurboQuant   | 3.5  | 45.01    | 45.31   | 26.00         | 68.63    | 59.95     | 46.17 | **50.06** |
| TurboQuant   | 2.5  | 44.16    | 44.96   | 24.80         | 68.01    | 59.65     | 45.76 | 49.44     |

Source: [arxiv paper](https://arxiv.org/html/2504.19874v1)

#### Performance Highlights

- **3.5 bits**: Absolute quality neutrality across all benchmarks
- **2.5 bits**: Marginal degradation only
- **Speed**: 4-bit TurboQuant achieves up to **8× speedup** in attention logit computation vs 32-bit on H100 GPUs
- **Compression**: At least **6× reduction** in KV memory
- **Nearest Neighbor Search**: Outperforms product quantization in recall while reducing indexing time to virtually zero

#### Kernel Performance

From [Baseten benchmarks](https://www.baseten.co/blog/i-spent-31-hours-on-the-math-behind-turboquant-so-you-dont-have-to/):

| Sequence Length | PolarQuant Kernel vs cuBLAS |
| --------------- | --------------------------- |
| < 8K            | No difference (kernel launch bound) |
| 65K             | ~75% of cuBLAS              |
| 512K            | ~75% of cuBLAS              |

The [Reddit community noted](https://www.reddit.com/r/LocalLLaMA/comments/1s2su28/google_research_turboquant_redefining_ai/) that end-to-end throughput can decrease 15–30× without optimized kernels.

---

---

## Sources

1. [PageIndex Official Introduction — Vectify AI](https://pageindex.ai/blog/pageindex-intro)
2. [PageIndex GitHub — VectifyAI/PageIndex](https://github.com/VectifyAI/PageIndex)
3. [Vectorless RAG: PageIndex — GeeksforGeeks](https://www.geeksforgeeks.org/artificial-intelligence/vectorless-rag-pageindex/)
4. [Bob Strikes Again: PageIndex Test and Implementation — Dev.to](https://dev.to/aairom/bob-strikes-again-pageindex-test-and-implementation-5ae)
5. [PageIndex Hacker News Discussion](https://news.ycombinator.com/item?id=45036944)
6. [PageIndex LlamaIndex Discussion — GitHub](https://github.com/run-llama/llama_index/discussions/18360)
7. [RAG is Not Dead — Gao Dalie Substack](https://gaodalie.substack.com/p/rag-is-not-dead-no-chunking-no-vectors)
8. [TurboQuant Paper — arxiv.org/abs/2504.19874](https://arxiv.org/abs/2504.19874)
9. [TurboQuant: Redefining AI Efficiency — Google Research Blog](https://research.google/blog/turboquant-redefining-ai-efficiency-with-extreme-compression/)
10. [TurboQuant Developer Guide — Dev.to](https://dev.to/arshtechpro/turboquant-what-developers-need-to-know-about-googles-kv-cache-compression-eeg)
11. [31 Hours on TurboQuant Math — Baseten Blog](https://www.baseten.co/blog/i-spent-31-hours-on-the-math-behind-turboquant-so-you-dont-have-to/)
12. [TurboQuant Explained — Vizuara Substack](https://vizuara.substack.com/p/turboquant-online-vector-quantization)
13. [TurboQuant Reddit Discussion — r/LocalLLaMA](https://www.reddit.com/r/LocalLLaMA/comments/1s2su28/google_research_turboquant_redefining_ai/)
14. [Krish Naik PageIndex Tutorial — YouTube](https://www.youtube.com/watch?v=nkbtOplq9jM)
