import os
import re
import threading
from pathlib import Path
from datetime import datetime

WIKI_PATH = Path("/Users/elnatananbelu/Desktop/graphify-out/obsidian/_Memory")

def _load_env():
    env = Path(__file__).parent.parent / ".env"
    for line in env.read_text().splitlines():
        if "=" in line and not line.startswith("#"):
            k, v = line.split("=", 1)
            if v.strip() and k.strip() not in os.environ:
                os.environ[k.strip()] = v.strip()

_load_env()


def search_relevant(query: str, max_notes: int = 3) -> str:
    """Return content of notes most relevant to the query. Keyword match — no full scan."""
    WIKI_PATH.mkdir(parents=True, exist_ok=True)
    notes = list(WIKI_PATH.glob("*.md"))
    if not notes:
        return ""

    query_words = set(re.findall(r'\w+', query.lower())) - {
        "the", "a", "an", "is", "it", "to", "of", "and", "or", "in", "on", "for", "what", "how", "can", "do", "my", "me", "i"
    }
    if not query_words:
        return ""

    scored = []
    for note in notes:
        try:
            text = note.read_text(encoding="utf-8")
            text_lower = text.lower()
            name_lower = note.stem.lower()
            score = sum(
                (3 if w in name_lower else 0) + text_lower.count(w)
                for w in query_words
            )
            if score > 0:
                scored.append((score, note.stem, text))
        except Exception:
            continue

    scored.sort(reverse=True)
    top = scored[:max_notes]
    if not top:
        return ""

    parts = []
    for _, title, content in top:
        # Strip YAML frontmatter, keep body only
        body = re.sub(r'^---.*?---\s*', '', content, flags=re.DOTALL).strip()
        parts.append(f"### {title}\n{body[:600]}")

    return "\n\n".join(parts)


def update_note(title: str, new_facts: str):
    """Append new facts to a note, creating it if it doesn't exist."""
    WIKI_PATH.mkdir(parents=True, exist_ok=True)
    safe_title = re.sub(r'[<>:"/\\|?*]', '', title).strip()
    path = WIKI_PATH / f"{safe_title}.md"
    now = datetime.now().strftime("%Y-%m-%d")

    if path.exists():
        content = path.read_text(encoding="utf-8")
        # Update the `updated:` date in frontmatter
        content = re.sub(r'(updated:\s*)[\d-]+', f'\\g<1>{now}', content)
        content = content.rstrip() + f"\n\n{new_facts}\n"
    else:
        content = f"---\ntags: [auto]\nupdated: {now}\n---\n\n# {safe_title}\n\n{new_facts}\n"

    path.write_text(content, encoding="utf-8")


def _extract_and_update_bg(user_msg: str, jarvis_msg: str):
    """Background: use Groq to extract facts and write to wiki."""
    groq_key = os.environ.get("GROQ_API_KEY", "").strip()
    if not groq_key:
        return

    prompt = f"""You are a memory extractor for a personal AI. Read this conversation and extract ONLY concrete, lasting facts worth remembering long-term (ignore small talk, questions with no new info, or things already obvious).

For each fact, output exactly:
NOTE: <note title>
FACT: <one-line fact>

Use simple note titles like: Addis Market, Goals, Family, Elnatan, or create a new topic if needed.
Output nothing if there's nothing worth saving.

USER: {user_msg}
JARVIS: {jarvis_msg}
"""
    try:
        from groq import Groq
        client = Groq(api_key=groq_key)
        resp = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            max_tokens=300,
            temperature=0,
            messages=[{"role": "user", "content": prompt}],
        )
        text = (resp.choices[0].message.content or "").strip()

        current_note = None
        for line in text.splitlines():
            line = line.strip()
            if line.startswith("NOTE:"):
                current_note = line[5:].strip()
            elif line.startswith("FACT:") and current_note:
                fact = line[5:].strip()
                if fact:
                    ts = datetime.now().strftime("%Y-%m-%d")
                    update_note(current_note, f"- {fact} *(learned {ts})*")
    except Exception:
        pass


def learn(user_msg: str, jarvis_msg: str):
    """Non-blocking: extract facts from conversation and save to wiki."""
    threading.Thread(
        target=_extract_and_update_bg,
        args=(user_msg, jarvis_msg),
        daemon=True
    ).start()


def get_context(query: str) -> str:
    """Return relevant wiki notes as context string for the prompt."""
    notes = search_relevant(query)
    if not notes:
        return ""
    return f"\nRELEVANT MEMORY:\n{notes}\n"
