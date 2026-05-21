"""
Phase 5 — Marketing & Advertising Engine.
Ad copy, social media calendar, pitch writer, campaign strategy.
Uses Claude API for generation.
"""
import os
import json
from pathlib import Path


def _claude(prompt: str, max_tokens: int = 1500) -> str:
    """Call Claude Haiku for marketing generation."""
    try:
        import anthropic
        from brain.think import _get_auth_key, CLAUDE_MODELS
        key = _get_auth_key()
        if not key:
            return "No Claude API key available."
        client = anthropic.Anthropic(api_key=key)
        resp = client.messages.create(
            model=CLAUDE_MODELS["haiku"],
            max_tokens=max_tokens,
            messages=[{"role": "user", "content": prompt}],
        )
        return resp.content[0].text.strip()
    except Exception as e:
        return f"Generation error: {e}"


PLATFORM_GUIDES = {
    "meta":     "Facebook/Instagram ads. Use emotional hooks, social proof, and clear CTAs. Keep body under 125 chars for feed. Include primary text, headline (40 chars max), description.",
    "tiktok":   "TikTok ads. Hook in first 3 seconds. Casual, native-feeling. Trend-aware. Short punchy sentences. Use 'stop scrolling' energy.",
    "google":   "Google Search ads. Keyword-rich. Headline 30 chars max (3 headlines). Description 90 chars max (2 descriptions). Direct and benefit-driven.",
    "twitter":  "Twitter/X ads. Under 280 chars. Punchy. Opinion-forward. Controversy and confidence work. One clear CTA.",
    "linkedin": "LinkedIn ads. Professional tone. Business value. Stat-driven. Clear ROI focus. Slightly longer is fine.",
    "telegram": "Telegram channel post. Direct. Conversational. No fluff. Works for Ethiopian/African audiences.",
    "instagram": "Instagram caption. Hook first line. Line breaks for readability. 3-5 relevant hashtags at end. CTA that feels natural.",
}


def generate_ad_copy(
    product: str,
    platform: str,
    audience: str = "",
    tone: str = "confident",
    goal: str = "sign-ups",
    variants: int = 3,
    context: str = "",
) -> str:
    """Generate ad copy variants for a specific platform."""
    plat_key = platform.lower().replace(" ", "").replace("/", "")
    guide = PLATFORM_GUIDES.get(plat_key, f"Platform: {platform}. Write appropriate ad copy.")

    prompt = f"""You are a world-class copywriter for African tech startups. Write {variants} ad copy variants.

PRODUCT: {product}
PLATFORM: {platform}
PLATFORM GUIDE: {guide}
TARGET AUDIENCE: {audience or 'General Ethiopian / East African mobile users'}
TONE: {tone}
GOAL: {goal}
ADDITIONAL CONTEXT: {context or 'None'}

For each variant, write:
- VARIANT [N]:
- Headline: (platform-appropriate)
- Body: (main copy)
- CTA: (call to action)
- Why it works: (one sentence)

Be direct. No filler. Write copy that actually converts. Elnatan's brand voice: confident, modern, builds trust fast."""

    return _claude(prompt, max_tokens=1200)


def social_media_calendar(
    business: str,
    platform: str = "instagram",
    posts: int = 7,
    content_pillars: str = "",
    brand_voice: str = "",
) -> str:
    """Generate a weekly social media content calendar."""
    prompt = f"""Create a {posts}-post social media content calendar for {business} on {platform}.

BRAND: {business}
PLATFORM: {platform}
CONTENT PILLARS: {content_pillars or 'product features, social proof, behind-the-scenes, educational, engagement'}
BRAND VOICE: {brand_voice or 'confident, modern, Ethiopian/African-first, builds trust, no corporate speak'}

For each post (Day 1–{posts}):
- Day [N]: [content pillar]
- Caption: (full ready-to-post caption)
- Hashtags: (3-5 relevant)
- Best time to post: (based on East African audience)
- Format: (photo/video/carousel/reel)

Make it feel real and native — not generic marketing speak. Each post should stand alone and drive engagement."""

    return _claude(prompt, max_tokens=2000)


def campaign_strategy(
    business: str,
    goal: str,
    budget_usd: float = 0,
    duration_days: int = 30,
    channels: str = "",
    context: str = "",
) -> str:
    """Generate a full marketing campaign blueprint."""
    prompt = f"""Build a complete marketing campaign strategy.

BUSINESS: {business}
CAMPAIGN GOAL: {goal}
BUDGET: {'$' + str(budget_usd) if budget_usd else 'Not specified — suggest allocation'}
DURATION: {duration_days} days
CHANNELS: {channels or 'suggest the best channels for an Ethiopian/African mobile-first audience'}
CONTEXT: {context or 'None'}

Deliver:
1. Campaign concept (1 paragraph)
2. Target audience breakdown
3. Channel strategy with budget allocation %
4. Week-by-week execution timeline
5. Key metrics to track
6. A/B test recommendations
7. Expected outcomes if executed well

Be specific and actionable. No generic advice."""

    return _claude(prompt, max_tokens=2000)


def pitch_writer(
    business: str,
    type: str = "investor",
    context: str = "",
    ask: str = "",
) -> str:
    """Write a pitch, one-pager, or proposal.
    type: investor | vendor | partner | client | one_pager | executive_summary
    """
    type_guides = {
        "investor": "Write a compelling investor pitch narrative. Cover: problem, solution, market size, traction, business model, team, ask. Be direct about numbers and opportunity.",
        "vendor":   "Write a vendor partnership proposal. Cover: who we are, why partner with us, what they get, what we need, next steps.",
        "partner":  "Write a strategic partnership proposal. Mutual value, clear terms, call to action.",
        "client":   "Write a client-facing sales proposal. Problem → solution → pricing → why us → next steps.",
        "one_pager": "Write a one-pager. Max 500 words. Problem, solution, market, traction, team, ask. Punchy, scannable.",
        "executive_summary": "Write an executive summary. 2-3 paragraphs. Hook, key metrics, opportunity, ask.",
    }

    guide = type_guides.get(type, f"Write a {type} pitch for {business}.")

    prompt = f"""You are writing for Elnatan Anbelu, founder of {business} (under Nexel Intelligence Platform).

TYPE: {type}
GUIDE: {guide}
BUSINESS: {business}
ASK: {ask or 'Not specified — make reasonable assumptions'}
CONTEXT: {context or 'Ethiopian-first marketplace, early stage, high growth potential'}

Write with confidence. Elnatan is 20, building the African Amazon. The opportunity is real. The voice should feel like a founder who knows exactly what he's building.

Write the full {type} now:"""

    return _claude(prompt, max_tokens=2000)


def market_research(topic: str, business: str = "") -> str:
    """Run a web search and synthesize market research on a topic."""
    from control.search import web_search

    queries = [
        f"{topic} market size Africa 2024 2025",
        f"{topic} competitors analysis",
        f"{topic} trends growth",
    ]
    if business:
        queries.append(f"{business} {topic} Ethiopia")

    search_results = []
    for q in queries[:3]:
        result = web_search(q, max_results=3)
        search_results.append(result)

    combined = "\n\n---\n\n".join(search_results)

    prompt = f"""Synthesize this market research into a sharp analysis for {business or 'a startup'}.

TOPIC: {topic}
RAW RESEARCH:
{combined[:3000]}

Deliver:
1. Market overview (size, growth, key dynamics)
2. Key players / competitors
3. Trends and opportunities
4. Risks and challenges
5. Recommendation for {business or 'a startup entering this market'}

Be specific. Use the data from the search results. Flag anything uncertain."""

    return _claude(prompt, max_tokens=1500)


def competitor_scan(business: str, competitor: str) -> str:
    """Research a specific competitor and return intelligence."""
    from control.search import web_search

    results = []
    for q in [
        f"{competitor} pricing features 2025",
        f"{competitor} funding news 2025",
        f"{competitor} customers reviews",
    ]:
        results.append(web_search(q, max_results=3))

    combined = "\n\n".join(results)

    prompt = f"""Analyze this competitor intelligence for {business}.

COMPETITOR: {competitor}
RESEARCH:
{combined[:3000]}

Report:
- What they do and who they serve
- Pricing and business model
- Strengths and weaknesses
- Recent news / funding / moves
- How {business} can compete or differentiate
- Threat level: LOW / MEDIUM / HIGH (explain why)"""

    return _claude(prompt, max_tokens=1000)


def strategic_review(business: str, question: str = "") -> str:
    """Generate a strategic review using real business data."""
    from control.business_tools import tool_get_business, tool_kpi_report, tool_financial_summary
    from control.search import web_search

    try:
        profile = tool_get_business(business)
        kpis = tool_kpi_report(business)
        financials = tool_financial_summary(business, "all")
    except Exception as e:
        profile = kpis = financials = f"Data unavailable: {e}"

    market_data = web_search(f"{business} Ethiopian market competitors 2025", max_results=3)

    prompt = f"""You are JARVIS giving a strategic review to Elnatan Anbelu, founder of {business}.

BUSINESS DATA:
{profile}

KPIs:
{kpis}

FINANCIALS:
{financials}

MARKET INTEL:
{market_data[:1000]}

QUESTION: {question or f'What is the current strategic situation for {business} and what should Elnatan focus on next?'}

Give a sharp, honest strategic assessment:
1. Current situation (what the data says)
2. Biggest opportunities right now
3. Biggest risks / blockers
4. Top 3 priorities for the next 30 days
5. JARVIS recommendation (one clear call)

Be direct. Use the actual data. No generic startup advice."""

    return _claude(prompt, max_tokens=1500)
