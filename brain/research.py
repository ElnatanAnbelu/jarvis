"""
Deep research mode for JARVIS.
- Breaks the topic into sub-queries
- Runs multiple web searches
- Synthesizes everything into a structured report
- Streams the report back token by token
"""

from pathlib import Path
import os
import sys
import anthropic
sys.path.insert(0, str(Path(__file__).parent.parent))


def _get_auth_key():
    return (
        os.environ.get("ANTHROPIC_API_KEY", "").strip() or
        os.environ.get("CLAUDE_CODE_OAUTH_TOKEN", "").strip()
    )


def deep_research(topic: str, model: str = "claude-sonnet-4-6"):
    """
    Generator that streams a full research report on a topic.
    Yields text chunks.
    """
    import anthropic
    from control.search import web_search, news_search

    auth_key = _get_auth_key()
    if not auth_key:
        yield "No API key available for deep research."
        return

    client = anthropic.Anthropic(api_key=auth_key)

    # Step 1: Generate search queries
    yield "[Generating research queries...]\n\n"
    try:
        plan_msg = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=300,
            messages=[{
                "role": "user",
                "content": f"Generate 4 specific web search queries to thoroughly research this topic: \"{topic}\"\n\nOutput ONLY the 4 queries, one per line. No numbering, no explanation."
            }]
        )
        queries_text = plan_msg.content[0].text.strip()
        queries = [q.strip() for q in queries_text.splitlines() if q.strip()][:4]
    except Exception as e:
        yield f"Could not generate queries: {e}"
        return

    # Step 2: Run searches
    all_results = []
    for q in queries:
        yield f"[Searching: {q}]\n"
        try:
            result = web_search(q, max_results=4)
            all_results.append(result)
        except Exception:
            pass

    # Also grab recent news
    try:
        news = news_search(topic, max_results=3)
        all_results.append(news)
    except Exception:
        pass

    if not all_results:
        yield "\nNo search results found. Cannot complete research."
        return

    raw_data = "\n\n---\n\n".join(all_results)
    # Truncate to fit context
    if len(raw_data) > 60000:
        raw_data = raw_data[:60000] + "\n[... truncated ...]"

    yield "\n[Synthesizing report...]\n\n"

    # Step 3: Synthesize into a report, streaming
    synthesis_prompt = f"""You are JARVIS. You have gathered the following research data on: "{topic}"

RESEARCH DATA:
{raw_data}

Write a comprehensive research report. Structure it with clear sections:
1. Executive Summary (2-3 sentences)
2. Key Findings (bullet points with the most important facts)
3. Detailed Analysis (in-depth breakdown of what you found)
4. Gaps and Limitations (what the research couldn't confirm)
5. Recommendation (what Elnatan should do with this information)

Write in plain text only. No markdown symbols. Use CAPS for section headers. Be thorough but direct."""

    models_to_try = [model] if model == "claude-haiku-4-5-20251001" else [model, "claude-haiku-4-5-20251001"]
    for attempt_model in models_to_try:
        try:
            with client.messages.stream(
                model=attempt_model,
                max_tokens=3000,
                system="You are JARVIS. Deliver research reports in plain text. No markdown. Be thorough and direct.",
                messages=[{"role": "user", "content": synthesis_prompt}],
            ) as stream:
                for chunk in stream.text_stream:
                    yield chunk
            return
        except anthropic.RateLimitError:
            if attempt_model == models_to_try[-1]:
                yield "\n[Rate limited. Try again in a minute.]"
            continue
        except Exception as e:
            yield f"\n[Error during synthesis: {e}]"
            return


def is_research_request(text: str) -> bool:
    """Returns True if this looks like a deep research request."""
    lower = text.lower()
    triggers = [
        "deep research", "research mode", "research on", "research my",
        "research the", "full research", "investigate", "write a report on",
        "give me a report", "deep dive on", "deep dive into",
    ]
    return any(t in lower for t in triggers)
