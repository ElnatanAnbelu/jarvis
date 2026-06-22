"""
Semantic long-term memory backed by FAISS + sentence-transformers.
Replaces the old keyword count() search with vector similarity.
The index is built lazily from Obsidian markdown notes and rebuilt
when notes change on disk.
"""

import os
import re
import threading
from pathlib import Path
from datetime import datetime

WIKI_PATH = Path("/Users/elnatananbelu/Desktop/graphify-out/obsidian/_Memory")
_INDEX_CACHE_PATH = WIKI_PATH / ".faiss_cache"

# ── Env ────────────────────────────────────────────────────────────────────────

def _load_env():
    env = Path(__file__).parent.parent / ".env"
    try:
        for line in env.read_text().splitlines():
            if "=" in line and not line.startswith("#"):
                k, v = line.split("=", 1)
                if v.strip() and k.strip() not in os.environ:
                    os.environ[k.strip()] = v.strip()
    except Exception:
        pass

_load_env()

# ── FAISS index state ──────────────────────────────────────────────────────────

_index = None          # faiss.IndexFlatIP
_chunks: list[str] = []   # raw text chunks (parallel to index vectors)
_titles: list[str] = []   # note titles (parallel to index vectors)
_model = None          # SentenceTransformer instance
_index_lock = threading.Lock()
_last_build: float = 0.0
_REBUILD_INTERVAL = 300  # rebuild if notes changed and >5 min since last build
_building = False       # guard: prevent concurrent background builds


def _get_model():
    global _model
    if _model is None:
        from sentence_transformers import SentenceTransformer
        # all-MiniLM-L6-v2: 80MB, fast, good quality — perfect for local use
        _model = SentenceTransformer("all-MiniLM-L6-v2")
    return _model


def _notes_mtime() -> float:
    """Return the most recent modification time across all notes."""
    WIKI_PATH.mkdir(parents=True, exist_ok=True)
    try:
        return max((p.stat().st_mtime for p in WIKI_PATH.glob("*.md")), default=0.0)
    except Exception:
        return 0.0


def _build_index():
    """Build FAISS index from all Obsidian notes. Called when stale."""
    global _index, _chunks, _titles, _last_build
    import numpy as np
    import faiss

    WIKI_PATH.mkdir(parents=True, exist_ok=True)
    notes = sorted(WIKI_PATH.glob("*.md"))
    if not notes:
        return

    model = _get_model()
    new_chunks, new_titles = [], []

    for note in notes:
        try:
            raw = note.read_text(encoding="utf-8")
            # Strip YAML frontmatter
            body = re.sub(r'^---.*?---\s*', '', raw, flags=re.DOTALL).strip()
            if not body:
                continue
            # Chunk into ~400-char segments so long notes get multiple vectors
            words = body.split()
            chunk_size = 80  # ~400 chars
            for i in range(0, len(words), chunk_size):
                chunk = " ".join(words[i:i + chunk_size])
                new_chunks.append(chunk)
                new_titles.append(note.stem)
        except Exception:
            continue

    if not new_chunks:
        return

    embeddings = model.encode(new_chunks, normalize_embeddings=True, show_progress_bar=False)
    embeddings = np.array(embeddings, dtype="float32")

    dim = embeddings.shape[1]
    index = faiss.IndexFlatIP(dim)  # inner product on normalized vectors = cosine similarity
    index.add(embeddings)

    with _index_lock:
        _index = index
        _chunks = new_chunks
        _titles = new_titles
        _last_build = datetime.now().timestamp()


def invalidate_index():
    """Force the next search to rebuild the index from disk. Used after notes are
    removed (e.g. right-to-be-forgotten) so the in-RAM FAISS index can't keep
    returning a purged subject's chunks."""
    global _last_build
    with _index_lock:
        _last_build = 0.0


def _ensure_index():
    """Kick off a background index build if stale. Never blocks the caller."""
    global _building
    with _index_lock:
        already_built = _index is not None
        mtime = _notes_mtime()
        needs_rebuild = not already_built or (mtime > _last_build and
                        (datetime.now().timestamp() - _last_build) > _REBUILD_INTERVAL)

    if needs_rebuild and not _building:
        _building = True
        def _bg():
            global _building
            try:
                _build_index()
            except Exception:
                pass
            finally:
                _building = False
        threading.Thread(target=_bg, daemon=True).start()


# ── Public API ─────────────────────────────────────────────────────────────────

def search_relevant(query: str, max_results: int = 3, threshold: float = 0.25) -> str:
    """
    Semantic search: return the most relevant note chunks for a query.
    Falls back to keyword search if FAISS/sentence-transformers unavailable.
    """
    _ensure_index()

    with _index_lock:
        if _index is None or not _chunks:
            return _keyword_fallback(query, max_results)

    try:
        import numpy as np
        model = _get_model()
        q_vec = model.encode([query], normalize_embeddings=True, show_progress_bar=False)
        q_vec = np.array(q_vec, dtype="float32")

        # Snapshot index + arrays together under the lock so a concurrent rebuild
        # can't shrink them between search and dereference (stale IndexError).
        with _index_lock:
            index, chunks, titles = _index, _chunks, _titles
            k = min(max_results * 3, len(chunks))  # fetch extras then dedupe by title
            scores, indices = index.search(q_vec, k)

        seen_titles: set[str] = set()
        results: list[tuple[str, str, float]] = []

        for score, idx in zip(scores[0], indices[0]):
            if idx < 0 or score < threshold:
                continue
            title = titles[idx]
            chunk = chunks[idx]
            if title in seen_titles:
                continue
            seen_titles.add(title)
            results.append((title, chunk, float(score)))
            if len(results) >= max_results:
                break

        if not results:
            return ""

        parts = [f"### {title}\n{chunk}" for title, chunk, _ in results]
        return "\n\n".join(parts)

    except Exception:
        return _keyword_fallback(query, max_results)


def _keyword_fallback(query: str, max_notes: int = 3) -> str:
    """Original keyword count search — used when FAISS is unavailable."""
    WIKI_PATH.mkdir(parents=True, exist_ok=True)
    notes = list(WIKI_PATH.glob("*.md"))
    if not notes:
        return ""

    stop = {"the","a","an","is","it","to","of","and","or","in","on","for",
            "what","how","can","do","my","me","i"}
    query_words = set(re.findall(r'\w+', query.lower())) - stop
    if not query_words:
        return ""

    scored = []
    for note in notes:
        try:
            text = note.read_text(encoding="utf-8")
            tl = text.lower()
            nl = note.stem.lower()
            score = sum((3 if w in nl else 0) + tl.count(w) for w in query_words)
            if score > 0:
                body = re.sub(r'^---.*?---\s*', '', text, flags=re.DOTALL).strip()
                scored.append((score, note.stem, body))
        except Exception:
            continue

    scored.sort(reverse=True)
    parts = [f"### {title}\n{body[:600]}" for _, title, body in scored[:max_notes]]
    return "\n\n".join(parts)


def update_note(title: str, new_facts: str):
    """Append new facts to a note, creating it if it doesn't exist."""
    WIKI_PATH.mkdir(parents=True, exist_ok=True)
    safe_title = re.sub(r'[<>:"/\\|?*]', '', title).strip()
    path = WIKI_PATH / f"{safe_title}.md"
    now = datetime.now().strftime("%Y-%m-%d")

    if path.exists():
        content = path.read_text(encoding="utf-8")
        content = re.sub(r'(updated:\s*)[\d-]+', f'\\g<1>{now}', content)
        content = content.rstrip() + f"\n\n{new_facts}\n"
    else:
        content = f"---\ntags: [auto]\nupdated: {now}\n---\n\n# {safe_title}\n\n{new_facts}\n"

    path.write_text(content, encoding="utf-8")
    # Invalidate index so next query triggers a rebuild
    global _last_build
    with _index_lock:
        _last_build = 0.0


# Topics whose facts belong in the personal Second Brain, not the project wiki.
_PERSONAL_NOTE_TOPICS = frozenset({
    "elnatan", "family", "goals", "health", "relationships", "interests",
    "decisions", "habits", "sleep", "gym", "fitness", "reading", "books",
    "hobbies", "personal", "life", "feelings", "emotions", "motivation",
    "friends", "contacts", "dates", "birthdays",
})


def _is_personal_topic(note_title: str) -> bool:
    """Return True if this note title belongs in the personal Second Brain."""
    lower = note_title.lower().strip()
    return any(topic in lower for topic in _PERSONAL_NOTE_TOPICS)


def _extract_prompt(user_msg: str, jarvis_msg: str) -> str:
    return f"""You are a memory extractor for a personal AI. Read this conversation and extract ONLY concrete, lasting facts worth remembering long-term (ignore small talk, questions with no new info, or things already obvious).

For each fact, output exactly:
NOTE: <note title>
FACT: <one-line fact>

Use simple note titles like: Goals, Family, Health, Interests, Decisions, You (for personal facts about the user), or technical topics like: Alfred, Tools, Architecture, Projects (for project/code facts).
Output nothing if there's nothing worth saving.

USER: {user_msg}
ALFRED: {jarvis_msg}
"""


def _run_extractor(prompt: str) -> str:
    """Run the memory-extraction prompt LOCALLY by default (offline purity). Falls
    back to cloud Groq only when the local model is unavailable AND the cloud escape
    hatch is opted-in (JARVIS_ALLOW_CLOUD_BRAIN=1 + a GROQ key)."""
    # Local-first.
    try:
        from brain import llm
        if llm.any_model_available():
            out = llm.chat([{"role": "user", "content": prompt}], temperature=0)
            return (out.get("content") or "").strip()
    except Exception:
        pass
    # Opt-in cloud fallback.
    try:
        from brain.agent import cloud_reasoning_allowed
        if not cloud_reasoning_allowed():
            return ""
        groq_key = os.environ.get("GROQ_API_KEY", "").strip()
        if not groq_key:
            return ""
        from groq import Groq
        client = Groq(api_key=groq_key)
        resp = client.chat.completions.create(
            model="llama-3.1-8b-instant", max_tokens=300, temperature=0,
            messages=[{"role": "user", "content": prompt}],
        )
        return (resp.choices[0].message.content or "").strip()
    except Exception:
        return ""


def _extract_and_update_bg(user_msg: str, jarvis_msg: str):
    """Background: extract facts (LOCAL model), route to personal brain or project wiki."""
    text = _run_extractor(_extract_prompt(user_msg, jarvis_msg))
    if not text:
        return
    try:
        current_note = None
        for line in text.splitlines():
            line = line.strip()
            if line.startswith("NOTE:"):
                current_note = line[5:].strip()
            elif line.startswith("FACT:") and current_note:
                fact = line[5:].strip()
                if not fact:
                    continue
                ts = datetime.now().strftime("%Y-%m-%d")
                if _is_personal_topic(current_note):
                    # Route personal facts to the Second Brain observation staging layer
                    try:
                        from memory.observations import add_observation
                        add_observation(
                            source="conversation",
                            source_detail=f"auto-extracted, {ts}",
                            content=fact,
                            relevance_hint=current_note,
                        )
                    except Exception:
                        # Fall back to project wiki if observations unavailable
                        update_note(current_note, f"- {fact} *(learned {ts})*")
                else:
                    # Technical/project facts stay in the project wiki (graphify vault)
                    update_note(current_note, f"- {fact} *(learned {ts})*")
    except Exception:
        pass


def learn(user_msg: str, jarvis_msg: str):
    """Non-blocking: extract facts from conversation and save to wiki."""
    threading.Thread(
        target=_extract_and_update_bg,
        args=(user_msg, jarvis_msg),
        daemon=True,
    ).start()


def get_context(query: str) -> str:
    """Return relevant wiki notes as context string for the prompt."""
    notes = search_relevant(query)
    if not notes:
        return ""
    return f"\nSTORED FACTS (relay exactly what is written; add no place, date, number, or status not present here):\n{notes}\n"
