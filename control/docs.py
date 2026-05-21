import sys
import os
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))


def read_pdf(file_path: str) -> str:
    """Extract text from a PDF file."""
    try:
        import fitz  # PyMuPDF
        doc = fitz.open(file_path)
        pages = []
        for i, page in enumerate(doc):
            text = page.get_text().strip()
            if text:
                pages.append(f"[Page {i+1}]\n{text}")
        doc.close()
        if not pages:
            return "PDF has no readable text."
        full = "\n\n".join(pages)
        # Truncate if very long
        if len(full) > 8000:
            full = full[:8000] + "\n\n[...truncated]"
        return full
    except Exception as e:
        return f"PDF read failed: {e}"


def read_text(file_path: str) -> str:
    """Read a plain text file."""
    try:
        with open(file_path, "r", encoding="utf-8", errors="replace") as f:
            content = f.read()
        if len(content) > 8000:
            content = content[:8000] + "\n[...truncated]"
        return content
    except Exception as e:
        return f"File read failed: {e}"


def summarize_document(file_path: str) -> str:
    """Read a document and return a summary via JARVIS brain."""
    path = Path(file_path).expanduser()
    if not path.exists():
        return f"File not found: {file_path}"

    ext = path.suffix.lower()
    if ext == ".pdf":
        content = read_pdf(str(path))
    elif ext in (".txt", ".md", ".py", ".js", ".csv", ".json", ".html"):
        content = read_text(str(path))
    else:
        return f"Unsupported file type: {ext}"

    # Ask JARVIS to summarize
    import subprocess
    prompt = (
        f"Summarize this document in 3-5 bullet points. Be concise.\n\n"
        f"File: {path.name}\n\n{content}"
    )
    result = subprocess.run(
        ["claude", "-p", prompt, "--model", "claude-haiku-4-5-20251001"],
        capture_output=True, text=True, timeout=60
    )
    summary = result.stdout.strip() or result.stderr.strip()
    return summary or "Could not summarize the document."


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        print(summarize_document(sys.argv[1]))
    else:
        print("Usage: python docs.py <file_path>")
