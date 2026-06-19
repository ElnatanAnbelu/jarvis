"""
Document reading and vision for JARVIS.
- read_file(path) → extracts text from PDF, DOCX, TXT, MD, or any plain-text file
- read_image(path) → base64-encodes an image for Claude's vision API
- ask_about_file(path, question) → streams Claude's response about the file
- ask_about_image(path, question) → streams Claude's response about the image
"""

import os
import base64
import mimetypes
import anthropic
from pathlib import Path


def read_file(path: str) -> str:
    """Extract text content from a file. Supports PDF, DOCX, TXT, MD, and common code/text files."""
    p = Path(path).expanduser()
    if not p.exists():
        return f"File not found: {path}"

    suffix = p.suffix.lower()

    if suffix == ".pdf":
        try:
            from pypdf import PdfReader
            reader = PdfReader(str(p))
            pages = []
            for i, page in enumerate(reader.pages):
                text = page.extract_text() or ""
                if text.strip():
                    pages.append(f"[Page {i+1}]\n{text.strip()}")
            return "\n\n".join(pages) if pages else "PDF appears to contain no extractable text (may be scanned images)."
        except Exception as e:
            return f"Error reading PDF: {e}"

    if suffix in (".docx", ".doc"):
        try:
            from docx import Document
            doc = Document(str(p))
            paragraphs = [p.text for p in doc.paragraphs if p.text.strip()]
            return "\n".join(paragraphs) if paragraphs else "Document appears to be empty."
        except Exception as e:
            return f"Error reading Word document: {e}"

    # Plain text fallback (txt, md, py, js, json, csv, etc.)
    try:
        return p.read_text(encoding="utf-8", errors="replace")
    except Exception as e:
        return f"Error reading file: {e}"


def read_image(path: str) -> tuple[str, str]:
    """Returns (base64_data, media_type) for an image file."""
    p = Path(path).expanduser()
    if not p.exists():
        raise FileNotFoundError(f"Image not found: {path}")

    media_type, _ = mimetypes.guess_type(str(p))
    if not media_type or not media_type.startswith("image/"):
        # Try by extension
        ext_map = {".jpg": "image/jpeg", ".jpeg": "image/jpeg",
                   ".png": "image/png", ".gif": "image/gif",
                   ".webp": "image/webp"}
        media_type = ext_map.get(p.suffix.lower(), "image/jpeg")

    data = base64.standard_b64encode(p.read_bytes()).decode("utf-8")
    return data, media_type


def ask_about_file(file_path: str, question: str, model: str = "claude-sonnet-4-6"):
    """Generator that streams Claude's answer about a document."""
    from brain.auth import make_client
    import anthropic

    text = read_file(file_path)
    if text.startswith("File not found") or text.startswith("Error"):
        yield text
        return

    name = Path(file_path).name
    # Truncate to ~80k chars to stay within context safely
    if len(text) > 80000:
        text = text[:80000] + "\n\n[... document truncated for length ...]"

    client = make_client()
    if client is None:
        yield "No API key available."
        return

    prompt = f"Here is the content of the file \"{name}\":\n\n{text}\n\n---\n\n{question}"

    models_to_try = [model] if model == "claude-haiku-4-5-20251001" else [model, "claude-haiku-4-5-20251001"]
    for attempt_model in models_to_try:
        try:
            with client.messages.stream(
                model=attempt_model,
                max_tokens=2048,
                system="You are Alfred. Answer clearly and directly about the document provided. No markdown. Plain sentences.",
                messages=[{"role": "user", "content": prompt}],
            ) as stream:
                for chunk in stream.text_stream:
                    yield chunk
            return
        except anthropic.RateLimitError:
            if attempt_model == models_to_try[-1]:
                yield "Rate limited on all models. Try again in a minute."
            continue
        except Exception as e:
            yield f"Error reading document: {e}"
            return


def ask_about_image(image_path: str, question: str, model: str = "claude-sonnet-4-6"):
    """Generator that streams Claude's vision analysis of an image."""
    from brain.auth import make_client
    import anthropic

    try:
        b64, media_type = read_image(image_path)
    except FileNotFoundError as e:
        yield str(e)
        return

    client = make_client()
    if client is None:
        yield "No API key available."
        return


    models_to_try = [model] if model == "claude-haiku-4-5-20251001" else [model, "claude-haiku-4-5-20251001"]
    for attempt_model in models_to_try:
      try:
        with client.messages.stream(
            model=attempt_model,
            max_tokens=1024,
            system="You are Alfred. Analyze the image directly and answer the question. No markdown. Plain sentences.",
            messages=[{
                "role": "user",
                "content": [
                    {"type": "image", "source": {"type": "base64", "media_type": media_type, "data": b64}},
                    {"type": "text", "text": question or "What do you see in this image?"},
                ],
            }],
        ) as stream:
            for chunk in stream.text_stream:
                yield chunk
        return
      except anthropic.RateLimitError:
        if attempt_model == models_to_try[-1]:
            yield "Rate limited on all models. Try again in a minute."
        continue
      except Exception as e:
        yield f"Error analyzing image: {e}"
        return


# ── Document Generation ────────────────────────────────────────────────────────

_DESKTOP = Path.home() / "Desktop"

_DOC_TRIGGERS = [
    "write a", "generate a", "create a", "draft a",
    "make a", "produce a", "put together a",
]
_DOC_TYPES = [
    "report", "brief", "document", "doc", "plan", "proposal",
    "strategy", "summary", "outline", "memo", "contract", "letter",
    "business plan", "pitch deck", "one pager", "deck",
]


def is_doc_gen_request(text: str) -> tuple[bool, str]:
    """Returns (True, doc_type) if this is a document generation request."""
    lower = text.lower()
    has_trigger = any(t in lower for t in _DOC_TRIGGERS)
    found_type = next((t for t in _DOC_TYPES if t in lower), None)
    if has_trigger and found_type:
        return True, found_type
    return False, ""


def generate_document(request: str, model: str = "claude-sonnet-4-6"):
    """
    Generator. Streams the document content, then saves it to Desktop.
    Yields text chunks, then a final '[Saved to Desktop as ...]' line.
    """
    from brain.auth import make_client
    import anthropic
    from datetime import datetime

    client = make_client()
    if client is None:
        yield "No API key available."
        return


    prompt = f"""{request}

Write the full document. Use CAPS for section headers. Plain text only, no markdown symbols.
Be thorough. This will be saved as a real file on the desktop."""

    chunks = []
    models_to_try = [model] if model == "claude-haiku-4-5-20251001" else [model, "claude-haiku-4-5-20251001"]
    generated = False
    for attempt_model in models_to_try:
        try:
            with client.messages.stream(
                model=attempt_model,
                max_tokens=4000,
                system="You are Alfred. Generate high-quality professional documents in plain text. No markdown. Use CAPS for headers.",
                messages=[{"role": "user", "content": prompt}],
            ) as stream:
                for chunk in stream.text_stream:
                    chunks.append(chunk)
                    yield chunk
            generated = True
            break
        except anthropic.RateLimitError:
            chunks = []  # reset in case partial chunks came through
            if attempt_model == models_to_try[-1]:
                yield "Rate limited on all models. Try again in a minute."
                return
            continue
        except Exception as e:
            yield f"Error generating document: {e}"
            return
    if not generated:
        return

    full_text = "".join(chunks).strip()
    if not full_text:
        return

    # Save to Desktop
    try:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        # Extract a short title from first line
        first_line = full_text.splitlines()[0][:40].strip().replace("/", "-").replace("\\", "-")
        filename = f"JARVIS_{timestamp}_{first_line}.txt"
        filepath = _DESKTOP / filename
        filepath.write_text(full_text, encoding="utf-8")
        yield f"\n\n[Saved to Desktop as: {filename}]"
    except Exception as e:
        yield f"\n\n[Could not save file: {e}]"
