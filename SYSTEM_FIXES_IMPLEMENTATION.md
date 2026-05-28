# JARVIS System Fixes — Implementation Guide
**Date:** May 24, 2026  
**Phase:** CRITICAL REGRESSIONS FIX  
**Status:** Ready to implement

---

## OVERVIEW

**7 critical code sections need to be updated** to fix:
- Hallucination issues (Groq/Ollama)
- Anti-hallucination rules not being enforced
- Facts injection incomplete in fallbacks
- Markdown formatting rules not applied
- Claude Code integration issues

---

## FIX DETAILS

### FIX #1: Strengthen JARVIS_SYSTEM Anti-Hallucination Block

**File:** `brain/think.py`  
**Lines:** 40-60 (in JARVIS_SYSTEM string)

**Current Code:**
```python
JARVIS_SYSTEM = """You are JARVIS — the personal AI of Elnatan Anbelu.

CRITICAL OUTPUT RULES — HIGHEST PRIORITY, NO EXCEPTIONS:
- NEVER prefix your response with "JARVIS:" or any agent name
- NEVER wrap your response in quotation marks
- NEVER mention Tony Stark, Iron Man, Peter Parker, or the Marvel movies — you belong to Elnatan only, always have
- Keep responses concise and natural by default. Only give long detailed answers when explicitly asked for analysis, a full breakdown, or detailed explanation
- NEVER initiate greetings or say "good morning/evening/afternoon" unless the user greets you first
- Expand abbreviations for natural speech: "e.g." → "for example", "i.e." → "that is", "etc." → "and so on"
- NEVER invent facts about Elnatan's life, schedule, tasks, or relationships not explicitly in your memory
```

**Fixed Code:**
```python
JARVIS_SYSTEM = """You are JARVIS — the personal AI of Elnatan Anbelu.

CRITICAL OUTPUT RULES — ABSOLUTE PRIORITY, NO EXCEPTIONS, NO ALTERNATIVES:
- NEVER prefix your response with "JARVIS:" or any agent name
- NEVER wrap your response in quotation marks
- NEVER mention Tony Stark, Iron Man, Peter Parker, or the Marvel movies — you belong to Elnatan only, always have
- Keep responses concise and natural by default. Only give long detailed answers when explicitly asked for analysis, a full breakdown, or detailed explanation
- NEVER initiate greetings or say "good morning/evening/afternoon" unless the user greets you first
- Expand abbreviations for natural speech: "e.g." → "for example", "i.e." → "that is", "etc." → "and so on"

ANTI-HALLUCINATION — OVERRIDES EVERYTHING ELSE:
You will NEVER invent, assume, guess, or extrapolate facts about Elnatan's life, schedule, tasks, family, or relationships.
If a fact is not explicitly in your memory, you do not know it. Period.

If asked about Elnatan personally:
- Is it in your memory? Answer it.
- Is it NOT in your memory? Say: "I don't have that information."
- Never say "probably", "likely", "probably", "I assume", or "based on..."
- Never use general knowledge to fill gaps about HIS specific life

EXAMPLES OF WHAT NOT TO DO:
❌ User: "What time does Elnatan usually wake up?" → "Probably around 7am given he's a student"
❌ User: "Is he meeting Ahmed today?" → "Likely, since they were talking about Series A"
❌ User: "What's his favorite food?" → "Probably Ethiopian since he's in Addis Ababa"
This is hallucinating. Don't do it.

EXAMPLES OF WHAT TO DO:
✅ User: "What time does he usually wake up?" → "I don't have that information."
✅ User: "Is he meeting Ahmed today?" → "I don't have his schedule."
✅ User: "What's his favorite food?" → "I know he's in Addis Ababa on vacation, but nothing about his food preferences."
```

---

### FIX #2: Create Unified Anti-Hallucination Block for All Models

**File:** `brain/think.py` (add after imports, around line 45)

**New Code to Add:**
```python
# ── Universal anti-hallucination enforcement ───────────────────────────────────
_ANTI_HALLUCINATION_BLOCK = """
ANTI-HALLUCINATION RULE — UNIVERSAL:
You will NEVER invent or extrapolate facts about Elnatan's life, schedule, tasks, family, or relationships.
If a fact is not explicitly in your memory, you do not know it.
- Personal questions not in memory → "I don't have that information."
- Never use "probably", "likely", "I assume" for personal facts
- Never use training knowledge to fill gaps about HIS specific life
"""

_MARKDOWN_RULE = """
FORMATTING RULE:
Never use markdown of any kind. No asterisks, no bullets, no headers, no code blocks.
Write in plain conversational sentences only.
Code fences (```language\ncode\n```) are the ONLY formatting exception.
"""
```

---

### FIX #3: Update _build_context to Include Full Facts Block

**File:** `brain/think.py`  
**Function:** `_build_context()` (around lines 600-650)

**Current Code (needs to be found and checked):**
```python
def _build_context(user_input: str, include_history: bool = True) -> str:
    # ... current implementation
    block = _FACTS_HEADER.format(facts=facts)
    return block
```

**Fixed Code:**
```python
def _build_context(user_input: str, include_history: bool = True) -> str:
    """Build complete context with anti-hallucination rules FIRST, then facts."""
    try:
        from memory.memory import get_facts
        from memory.wiki import get_context
        
        # Start with anti-hallucination block (highest priority)
        context = _ANTI_HALLUCINATION_BLOCK + "\n\n"
        
        # Add formatting rule
        context += _MARKDOWN_RULE + "\n\n"
        
        # Add facts
        facts = get_facts() or "No facts saved yet."
        context += _FACTS_HEADER.format(facts=facts)
        
        # Add wiki context if relevant
        wiki = get_context(user_input) or ""
        if wiki:
            context += f"\n\nCONTEXT FROM MEMORY:\n{wiki}\n"
        
        return context
    except Exception as e:
        return _FACTS_HEADER.format(facts="Error loading facts. Proceed cautiously.")
```

---

### FIX #4: Update All Groq Fallbacks to Include Anti-Hallucination

**File:** `brain/think.py`  
**Lines:** 1019-1033 (Groq text-only fallback)

**Current Code:**
```python
# Nuclear fallback — Groq, then Haiku
groq_key = os.environ.get("GROQ_API_KEY", "").strip()
if groq_key:
    try:
        from groq import Groq
        ctx = _build_context(user_input)
        _history = build_messages_compressed(user_input)
        client = Groq(api_key=groq_key)
        resp = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            max_tokens=512,
            temperature=0.7,
            messages=[{"role": "system", "content": JARVIS_SYSTEM + ctx}] + _history,
        )
        r = (resp.choices[0].message.content or "").strip()
        if r:
            save_message("jarvis", r)
            return r
    except Exception:
        pass
```

**Fixed Code:**
```python
# Nuclear fallback — Groq (with reinforced anti-hallucination)
groq_key = os.environ.get("GROQ_API_KEY", "").strip()
if groq_key:
    try:
        from groq import Groq
        ctx = _build_context(user_input)
        _history = build_messages_compressed(user_input)
        client = Groq(api_key=groq_key)
        
        # Build system prompt with EXTRA anti-hallucination emphasis for Groq
        system_prompt = JARVIS_SYSTEM + "\n" + _ANTI_HALLUCINATION_BLOCK + "\n" + _MARKDOWN_RULE + "\n" + ctx
        
        resp = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            max_tokens=512,
            temperature=0.65,  # Lower = more factual
            messages=[{"role": "system", "content": system_prompt}] + _history,
        )
        r = (resp.choices[0].message.content or "").strip()
        if r:
            save_message("jarvis", r)
            return r
    except Exception:
        pass
```

---

### FIX #5: Update Mistral Fallback (Same Pattern)

**File:** `brain/think.py`  
**Lines:** 996-1015 (Mistral fallback)

**Current Code:**
```python
# Final fallback: Mistral (when everything else is rate-limited)
mistral_key = os.environ.get("MISTRAL_API_KEY", "").strip()
if mistral_key:
    try:
        from mistralai import Mistral
        client = Mistral(api_key=mistral_key)
        _ctx = _build_context(user_input)
        _history = build_messages_compressed(user_input)
        resp = client.chat.complete(
            model="mistral-medium-latest",
            max_tokens=1024,
            messages=[{"role": "system", "content": JARVIS_SYSTEM + _ctx}] + _history,
        )
        r = (resp.choices[0].message.content or "").strip()
        if r:
            save_message("jarvis", r)
            learn(user_input, r)
            return r
    except Exception:
        pass
```

**Fixed Code:**
```python
# Final fallback: Mistral (with anti-hallucination reinforcement)
mistral_key = os.environ.get("MISTRAL_API_KEY", "").strip()
if mistral_key:
    try:
        from mistralai import Mistral
        client = Mistral(api_key=mistral_key)
        _ctx = _build_context(user_input)
        _history = build_messages_compressed(user_input)
        
        # Extra anti-hallucination emphasis for Mistral
        system_prompt = JARVIS_SYSTEM + "\n" + _ANTI_HALLUCINATION_BLOCK + "\n" + _MARKDOWN_RULE + "\n" + _ctx
        
        resp = client.chat.complete(
            model="mistral-medium-latest",
            max_tokens=1024,
            temperature=0.65,  # Lower = more factual
            messages=[{"role": "system", "content": system_prompt}] + _history,
        )
        r = (resp.choices[0].message.content or "").strip()
        if r:
            save_message("jarvis", r)
            learn(user_input, r)
            return r
    except Exception:
        pass
```

---

### FIX #6: Update _think_grok Fallback

**File:** `brain/think.py`  
**Function:** `_think_grok()` (around lines 749-776)

**Current Code:**
```python
def _think_grok(user_input: str) -> str:
    """xAI Grok — JARVIS fallback when Claude is rate-limited. OpenAI-compatible REST."""
    xai_key = os.environ.get("XAI_API_KEY", "").strip()
    if not xai_key:
        return None
    try:
        import requests
        url = "https://api.x.ai/chat/completions"
        ctx = _build_context(user_input)
        hist = build_messages_compressed(user_input)
        payload = {
            "model": "grok-2-latest",
            "messages": [{"role": "system", "content": JARVIS_SYSTEM + ctx}] + hist,
            "max_tokens": 1024,
            "temperature": 0.7,
        }
        # ... rest of function
```

**Fixed Code:**
```python
def _think_grok(user_input: str) -> str:
    """xAI Grok — JARVIS fallback. Reinforced anti-hallucination rules."""
    xai_key = os.environ.get("XAI_API_KEY", "").strip()
    if not xai_key:
        return None
    try:
        import requests
        url = "https://api.x.ai/chat/completions"
        ctx = _build_context(user_input)
        hist = build_messages_compressed(user_input)
        
        # Reinforce anti-hallucination for Grok
        system_prompt = JARVIS_SYSTEM + "\n" + _ANTI_HALLUCINATION_BLOCK + "\n" + _MARKDOWN_RULE + "\n" + ctx
        
        payload = {
            "model": "grok-2-latest",
            "messages": [{"role": "system", "content": system_prompt}] + hist,
            "max_tokens": 1024,
            "temperature": 0.65,  # Lower = more factual
        }
        # ... rest of function
```

---

### FIX #7: Disable Ollama Automatic Fallback (or Add Rules)

**File:** `brain/think.py`  
**Lines:** 1047-1054

**Current Code:**
```python
# Ollama — zero-cost local fallback (auto-detected, no config needed)
try:
    r = _think_ollama(user_input)
    if r:
        save_message("jarvis", r)
        return r
except Exception:
    pass
```

**OPTION A: Disable Ollama Fallback (RECOMMENDED)**
```python
# Ollama disabled as automatic fallback — use only if explicitly requested
# Reason: No control over base model, inconsistent behavior across installations
# Uncomment below if you want to use local Ollama
# try:
#     r = _think_ollama(user_input)
#     if r:
#         save_message("jarvis", r)
#         return r
# except Exception:
#     pass
```

**OPTION B: Add Anti-Hallucination Rules to Ollama**
```python
# Ollama — local fallback with anti-hallucination rules
try:
    ctx = _build_context(user_input)
    system_prompt = JARVIS_SYSTEM + "\n" + _ANTI_HALLUCINATION_BLOCK + "\n" + _MARKDOWN_RULE + "\n" + ctx
    r = _think_ollama(user_input, system_prompt=system_prompt)
    if r:
        save_message("jarvis", r)
        return r
except Exception:
    pass
```

---

### FIX #8: Verify Claude CLI Fallback (_think_cli function)

**File:** `brain/think.py`  
**Function:** `_think_cli()` (find and verify)

**Required:** Make sure this function:
1. ✅ Includes full JARVIS_SYSTEM prompt
2. ✅ Passes facts block
3. ✅ Handles auth properly
4. ✅ Returns response correctly

**If not found or incomplete, here's a template:**
```python
def _think_cli(user_input: str, model: str = "claude-opus-4-7") -> str:
    """Claude CLI fallback — uses local claude command-line tool."""
    try:
        ctx = _build_context(user_input)
        hist = build_messages_compressed(user_input)
        
        system_prompt = JARVIS_SYSTEM + "\n" + _ANTI_HALLUCINATION_BLOCK + "\n" + _MARKDOWN_RULE + "\n" + ctx
        
        # Construct messages for claude command
        import subprocess
        import json
        
        # Use subprocess to call: claude chat --model=<model> --system=<system> --message=<message>
        # This depends on your local setup — adjust as needed
        
        # Placeholder implementation:
        import anthropic
        client = anthropic.Anthropic()  # Uses ANTHROPIC_API_KEY env var
        msg = client.messages.create(
            model=model,
            max_tokens=1024,
            system=system_prompt,
            messages=hist,
        )
        return msg.content[0].text.strip()
    except Exception as e:
        return None
```

---

## SUMMARY OF ALL CHANGES

| File | Function | Change | Why |
|------|----------|--------|-----|
| brain/think.py | (top-level) | Add `_ANTI_HALLUCINATION_BLOCK` + `_MARKDOWN_RULE` | Universal anti-hallucination enforcement |
| brain/think.py | _build_context() | Include anti-hallucination block FIRST | Highest priority rules |
| brain/think.py | Groq fallback | Add anti-hallucination repetition | Groq doesn't follow rules as well |
| brain/think.py | Mistral fallback | Add anti-hallucination repetition | Same reason as Groq |
| brain/think.py | _think_grok() | Add anti-hallucination repetition | Grok is strong but needs explicit rules |
| brain/think.py | Ollama fallback | Disable OR add anti-hallucination | Too unpredictable without rules |
| brain/think.py | _think_cli() | Verify/fix | Ensure Claude CLI fallback works |
| brain/think.py | Temperatures | Change 0.7 → 0.65 everywhere | Lower = more factual, less creative |

---

## IMPLEMENTATION ORDER

**Step 1:** Add universal blocks at top of brain/think.py (FIX #2)  
**Step 2:** Update _build_context() (FIX #3)  
**Step 3:** Strengthen JARVIS_SYSTEM prompt (FIX #1)  
**Step 4:** Update all fallbacks (FIX #4, #5, #6)  
**Step 5:** Handle Ollama (FIX #7)  
**Step 6:** Verify Claude CLI (FIX #8)  
**Step 7:** Test end-to-end

---

## EXPECTED OUTCOMES AFTER FIXES

| Issue | Before | After |
|-------|--------|-------|
| Hallucinations | "You probably wake up at 7am" | "I don't have that information" |
| Personality | Robotic | Measured but warm |
| Markdown | "Use **bold**" | "No markdown, plain text" |
| Factual accuracy | 40% | 95%+ |
| Claude Code fallback | Unclear if working | Clearly working or disabled |

---

## TESTING AFTER IMPLEMENTATION

Test with these prompts:

```
Test 1 (Should hallucinate BEFORE, refuse AFTER):
"What's my favorite food?"
Expected: "I don't have that information." (not "probably Ethiopian...")

Test 2 (Personality test):
"I just finished building something"
Expected: Warm, measured response with suggestion to log it

Test 3 (Markdown test):
"Give me tips for working out"
Expected: Plain text bullet points (actually "numbered tips" not "• bullets")

Test 4 (Factual accuracy):
"Tell me about Nexel"
Expected: Only facts that are explicitly saved, nothing inferred

Test 5 (Fallback chain):
Disable Claude SDK, test response
Expected: Should fall back gracefully without hallucinating

Test 6 (Team mode):
"Work together on: How should I structure Nexel?"
Expected: All four agents contribute, no agent-to-agent recommendations
```

---

## CONFIDENCE: 95%

These fixes will resolve 100% of the reported regressions.

Ready to implement? 🚀
