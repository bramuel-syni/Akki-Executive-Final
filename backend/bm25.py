"""Light-weight BM25 scorer for in-process chunk ranking.

We deliberately keep this module dependency-free (no `rank_bm25`, no sklearn).
At the scale of a single context (< 200 documents, < 2,000 chunks) a pure-
Python BM25 is fast enough and avoids another wheel on the critical path.

Usage:
    chunks = chunk_documents(docs)            # [{doc_id, name, trust, text}, …]
    ranked = score_bm25(query, chunks, k=12)  # top-k chunks
"""
from __future__ import annotations

import math
import re
from collections import Counter, defaultdict
from typing import Dict, List, Optional, Tuple

_TOKEN_RE = re.compile(r"[A-Za-z][A-Za-z0-9]+")

# Compact stop list — standard English only. We don't lemmatise.
_STOP = {
    "the", "a", "an", "is", "are", "was", "were", "be", "been", "being",
    "of", "in", "on", "at", "to", "for", "by", "with", "from", "as", "and",
    "or", "but", "if", "then", "that", "this", "these", "those", "it", "its",
    "which", "who", "whom", "what", "when", "where", "why", "how", "not",
    "no", "do", "does", "did", "have", "has", "had", "will", "would", "should",
    "could", "may", "might", "can", "shall", "there", "here", "than",
}


def tokenize(text: str) -> List[str]:
    return [t.lower() for t in _TOKEN_RE.findall(text or "") if t.lower() not in _STOP and len(t) > 2]


def chunk_documents(
    docs: List[Dict], *, chunk_size: int = 1200, overlap: int = 150,
) -> List[Dict]:
    """Break each document's extracted_text into ~chunk_size-char windows."""
    out: List[Dict] = []
    for d in docs:
        text = (d.get("extracted_text") or "").strip()
        if not text:
            continue
        step = max(400, chunk_size - overlap)
        i = 0
        idx = 0
        while i < len(text):
            end = min(i + chunk_size, len(text))
            out.append({
                "doc_id": d["id"],
                "name": d.get("name", ""),
                "trust": d.get("data_trust", "mixed"),
                "chunk_idx": idx,
                "text": text[i:end],
            })
            idx += 1
            if end == len(text):
                break
            i += step
    return out


def score_bm25(
    query: str, chunks: List[Dict], *, k: int = 12, k1: float = 1.5, b: float = 0.75,
) -> List[Tuple[float, Dict]]:
    """Return top-k (score, chunk) sorted by BM25. Returns [] if no chunks."""
    if not chunks:
        return []
    q_tokens = tokenize(query)
    if not q_tokens:
        # Degenerate query — return first N chunks unordered so Ask still grounds.
        return [(0.0, c) for c in chunks[:k]]

    # Build doc-frequency tables
    doc_tokens: List[List[str]] = [tokenize(c["text"]) for c in chunks]
    N = len(doc_tokens)
    if N == 0:
        return []
    avgdl = sum(len(t) for t in doc_tokens) / N

    df: Dict[str, int] = defaultdict(int)
    for dt in doc_tokens:
        for tok in set(dt):
            df[tok] += 1

    # IDF with BM25's +0.5 smoothing
    idf = {tok: math.log((N - f + 0.5) / (f + 0.5) + 1) for tok, f in df.items()}

    scored: List[Tuple[float, Dict]] = []
    for chunk, dt in zip(chunks, doc_tokens):
        if not dt:
            scored.append((0.0, chunk))
            continue
        dl = len(dt)
        tf = Counter(dt)
        score = 0.0
        for tok in q_tokens:
            if tok not in tf:
                continue
            num = tf[tok] * (k1 + 1)
            denom = tf[tok] + k1 * (1 - b + b * (dl / avgdl))
            score += idf.get(tok, 0.0) * (num / denom)
        scored.append((score, chunk))

    scored.sort(key=lambda x: x[0], reverse=True)
    # If everything scored 0, fall back to first k to preserve the grounding floor
    if all(s == 0 for s, _ in scored[:k]):
        return [(0.0, c) for c in chunks[:k]]
    return [(s, c) for s, c in scored[:k] if s > 0] or [(0.0, c) for c in chunks[:k]]


def ranked_chunks_as_grounding_block(
    ranked: List[Tuple[float, Dict]], *, max_chars: int = 40_000,
) -> Tuple[str, List[str]]:
    """Render ranked chunks into an Ask grounding block. Returns (block_text,
    used_doc_ids). Caller can short-circuit if ranked is empty."""
    if not ranked:
        return "[No extracted documents in this context yet.]", []
    parts: List[str] = []
    used_ids: List[str] = []
    budget = max_chars
    for score, ch in ranked:
        if budget <= 400:
            break
        header = f"----\n[doc:{ch['doc_id']}] name: {ch['name']} · trust: {ch['trust']} · chunk #{ch['chunk_idx']} · score {score:.2f}\n"
        body = ch["text"][:budget - len(header) - 20]
        parts.append(header + body)
        budget -= len(header) + len(body) + 20
        if ch["doc_id"] not in used_ids:
            used_ids.append(ch["doc_id"])
    return "\n".join(parts), used_ids
