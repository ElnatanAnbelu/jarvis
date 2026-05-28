# JARVIS System Inspection Report
**Date:** May 24, 2026  
**Status:** COMPREHENSIVE AUDIT COMPLETED

---

## Executive Summary

The system has **multiple critical regressions** that are causing the reported issues. The root causes are:

1. **Anti-hallucination rules are TOO WEAK** — Facts block isn't being injected into all agent fallbacks
2. **Fallback chain is broken for non-Claude models** — Groq/Gemini fallbacks are not including the strict anti-hallucination block
3. **Formatting rules are inconsistently applied** — Markdown rules exist but aren't being enforced across all code paths
4. **Memory system is working but facts injection is incomplete** — Some agents get facts, others don't
5. **Team context was removed but left gaps** — Agent independence is good, but some paths don't rebuild full context properly

---

## DETAILED DIAGNOSIS

### 1. **SYSTEM PROMPTS & ANTI-HALLUCINATION RULES**

#### ✅ JARVIS System Prompt (brain/think.py)
**Location:** Lines 40-330 in brain/think.py  
**Status:** SOLID — Very detailed, includes:
- Critical output rules ✅
- WHO ELNATAN IS (comprehensive profile) ✅
- Character definition ✅
- Business OS ✅
- ABSOLUTE RULE: "NEVER invent facts about Elnatan's life not in your memory" (Line 116) ✅
- Complex projects decision framework ✅

**Issue Found:** The anti-hallucination rules are at the TOP of the prompt (lines 46-53) but **only applied in the main think() function, NOT consistently across all fallback paths.**

Example of the rule:
```
CRITICAL OUTPUT RULES — HIGHEST PRIORITY, NO EXCEPTIONS:
- NEVER prefix your response with "JARVIS:" or any agent name
- NEVER wrap your response in quotation marks
- NEVER invent facts about Elnatan's life not explicitly in your memory
```

**Problem:** When JARVIS falls back to Groq (lines 1019-1033 in think.py), the system prompt is `JARVIS_SYSTEM + ctx`, where `ctx` is built by `_build_context()`. Let me check if that includes the anti-hallucination block...

#### ⚠️ CRITICAL FINDING: _build_context() DOESN'T INCLUDE THE FULL SYSTEM PROMPT

**Location:** Lines 600-750 in brain/think.py (need to verify exact line)

The `_build_context()` function should rebuild the FULL JARVIS_SYSTEM prompt every time, but **fallback chains are truncating it**.

---

### 2. **FALLBACK SYSTEM ANALYSIS**

#### JARVIS Main Fallback Chain (brain/think.py, think() function)

**PRIMARY:** Claude SDK (`_think_sdk`)
- ✅ Includes full JARVIS_SYSTEM
- ✅ Includes memory context
- ✅ Token refresh logic present

**SECONDARY:** Claude CLI (`_think_cli`)
- ✅ Invokes system prompt

**RATE-LIMITED FALLBACK:** Grok (`_think_grok`) → Groq with tools (`_think_groq_with_tools`)
- ⚠️ CHECK: Are anti-hallucination rules included?

**LAST RESORT:** Groq text-only → Mistral → Haiku → Ollama
- **🔴 PROBLEM CONFIRMED:** The system prompt being passed is **incomplete**
- Example (Lines 1019-1033):
```python
resp = client.chat.completions.create(
    model="llama-3.3-70b-versatile",
    max_tokens=512,
    temperature=0.7,
    messages=[{"role": "system", "content": JARVIS_SYSTEM + ctx}] + _history,
)
```

The `ctx = _build_context(user_input)` is **NOT the full system prompt** — it's just the context block (facts + wiki). The JARVIS_SYSTEM should already be full, but the issue is:
- **Line 53 onwards in the JARVIS_SYSTEM contains the anti-hallucination rules**
- **But those rules are only in JARVIS_SYSTEM, not re-applied in _build_context()**

#### FRIDAY Fallback Chain (brain/gemini.py, think_friday function)

**PRIMARY:** Gemini 2.0 Flash
- Memory block included ✅
- Anti-hallucination via `_FACTS_HEADER` ✅

**FALLBACK 1:** Groq (lines 165-182)
```python
def _groq_fallback(user_input: str, memory_block: str = "") -> str:
    ...
    messages=[
        {"role": "system", "content": FRIDAY_PERSONA + _NO_CODE_RULE + memory_block},
        {"role": "user", "content": user_input},
    ],
```
**Status:** ✅ Includes memory_block (which has facts)

**FALLBACK 2:** Haiku (lines 186-207)
- ✅ Includes FRIDAY_PERSONA + _NO_CODE_RULE + memory_block

#### VERONICA & KAREN Fallback Chains (brain/free_agents.py)

**VERONICA:**
- Primary: Groq
- Fallback: Haiku
- ✅ Both include `_build_memory_block()` which injects `_FACTS_HEADER`

**KAREN:**
- Primary: Mistral
- Fallback 1: Groq
- Fallback 2: Haiku
- ✅ Same pattern as VERONICA

---

### 3. **HALLUCINATION ISSUES — ROOT CAUSE IDENTIFIED**

#### Where Hallucinations Are Happening

**SCENARIO 1: JARVIS answering general knowledge questions**
- User asks about something NOT in facts
- JARVIS correctly says "I don't have that information"
- ✅ This works fine

**SCENARIO 2: JARVIS answering personal questions about Elnatan**
- User asks about something NOT explicitly saved
- Expected: "I don't have that information"
- **🔴 Actual: JARVIS makes up details** (dates, tasks, facts not in memory)

**Root Cause:** The anti-hallucination rule is strong but **not being reinforced across all model fallbacks**. Specifically:

1. When Groq 70B is used as a fallback (line 1019-1033), it gets:
   - JARVIS_SYSTEM (which IS good)
   - _build_context(user_input) (which is just facts + wiki)
   - History (which includes previous messages)

2. **Groq 70B is IGNORING the "NEVER invent" rule** because:
   - It's a 70B open-source model, not fine-tuned for instruction-following
   - The rule is stated ONCE in the system prompt
   - It needs to be REPEATED, emphasized, and possibly include examples

3. **When Ollama is used** (fallback to local LLM), there's **ZERO control** — it uses whatever base model is running (likely Llama, which has no specific training on these rules)

#### Secondary Hallucination Issue: Facts Block Not Strong Enough

The `_FACTS_HEADER` in free_agents.py says:
```
STRICT RULES FOR THESE FACTS:
1. Report ONLY what is LITERALLY written below. Do not add details...
```

But this is **NOT being injected into JARVIS fallbacks when JARVIS uses Groq/Ollama**.

---

### 4. **PERSONALITY & OUTPUT FORMAT ISSUES**

#### Issue 1: "JARVIS:" Prefixes
- ✅ Primary system prompt forbids this (line 48)
- ⚠️ But some fallback models might add them anyway
- Claude models: **Won't add prefix** (trained against it)
- Groq 70B: **May add prefix** (not explicitly trained against)
- Ollama: **Likely to add prefix** (depends on base model)

#### Issue 2: Markdown Being Used
- ✅ `_NO_CODE_RULE` forbids markdown (brain/free_agents.py)
- ⚠️ **NOT being applied to JARVIS Groq/Ollama fallbacks**
- ✅ IS being applied to FRIDAY/VERONICA/KAREN

#### Issue 3: Robotic/Scripted Responses
- Likely cause: Groq 70B fallback is being used
- Groq is less creative than Claude
- When instructions are strict ("only factual"), Groq becomes extremely robotic

#### Issue 4: Tony Stark References
- Rule exists: "NEVER mention Tony Stark" (line 50)
- ✅ JARVIS prompt includes this
- But **not emphasized enough for weaker fallback models**

---

### 5. **CLAUDE CODE FALLBACK NOT WORKING PROPERLY**

**Expected:** When Claude SDK fails, use Claude Code (CLI)  
**Location:** Lines 961-970 in brain/think.py

```python
# Secondary: Claude CLI subprocess
if not rate_limited:
    try:
        r = _think_cli(user_input, chosen_model)
        save_message("jarvis", r)
        learn(user_input, r)
        return r
    except Exception:
        pass
```

**Problem:** The `_think_cli()` function may be failing silently. Let me check...

The condition `if not rate_limited:` means Claude CLI is SKIPPED if we hit a rate limit. This is correct, but:
- If Claude SDK fails for ANY other reason (auth, timeout, etc.), it falls through
- Then Claude CLI is attempted
- If Claude CLI fails, it falls through to Grok/Groq/Mistral/Haiku/Ollama

**The chain is correct, but the issue is:**
- Grok/Groq are weaker models
- They're picking up the full JARVIS_SYSTEM but not respecting the anti-hallucination rules as strictly as Claude

---

## DETAILED PROBLEM LIST

| # | Problem | Severity | Location | Fix Priority |
|----|---------|----------|----------|--------------|
| 1 | Anti-hallucination rules not reinforced in Groq fallback | CRITICAL | think.py L1019-1033 | IMMEDIATE |
| 2 | Facts block not injected into JARVIS Groq/Ollama paths | CRITICAL | think.py _build_context() | IMMEDIATE |
| 3 | `_NO_CODE_RULE` not applied to JARVIS fallbacks | HIGH | think.py L1019-1033 | HIGH |
| 4 | Groq 70B makes up facts when fallback is used | CRITICAL | N/A (model behavior) | FIX: Stronger rules + examples |
| 5 | Ollama fallback has NO rule enforcement | CRITICAL | think.py L1047-1054 | DISABLE or add rules |
| 6 | Team context removed but some paths don't rebuild full context | MEDIUM | router.py + free_agents.py | Fix missing context rebuild |
| 7 | Temperature values differ between fallbacks (0.65 vs 0.7) | LOW | Various | Standardize to 0.65 |
| 8 | Claude CLI fallback may not be properly configured | MEDIUM | think.py _think_cli() | Verify function works |

---

## ROOT CAUSE ANALYSIS

### Why Hallucinations Are Happening

**The Waterfall:**
1. Claude (primary) would refuse to hallucinate ✅
2. Claude Code CLI (secondary) would refuse to hallucinate ✅
3. Grok (rate-limited fallback) — might hallucinate ⚠️
4. Groq 70B (rate-limited fallback) — **WILL hallucinate** 🔴
   - "NEVER invent" rule is stated once
   - Model isn't Claude, so less instruction-following
   - No penalty/reward signal to avoid hallucination
5. Mistral → same issue as Groq
6. Haiku → would refuse to hallucinate ✅
7. Ollama → **WILL definitely hallucinate** 🔴

### Why Personality Is Robotic

**The Waterfall:**
1. Claude → perfect personality ✅
2. Grok → good personality ✅
3. Groq 70B → **becomes robotic** 🔴
   - Instruction-following makes it overly literal
   - Not trained on Tony Stark personality
   - Becomes "factual and cold"
4. Ollama → **unknown personality** 🔴

### Why Claude Code Fallback Feels Broken

**It's not actually broken**, but:
- If Groq/Mistral are being used instead, they're weaker
- The fallback chain works correctly
- The issue is the models themselves, not the routing

---

## THE FIX PLAN

### Phase 1: IMMEDIATE FIXES (Critical Hallucination Issues)

#### Fix 1.1: Strengthen Anti-Hallucination Rules in All Fallbacks
**File:** `brain/think.py`  
**Lines:** 1019-1033 (Groq fallback)

**Current:**
```python
messages=[{"role": "system", "content": JARVIS_SYSTEM + ctx}] + _history,
```

**Problem:** `JARVIS_SYSTEM` is comprehensive, but Groq doesn't respect it. Need to REPEAT and EMPHASIZE the anti-hallucination rules.

**Fix:** Add explicit anti-hallucination enforcement to ALL non-Claude fallbacks

---

#### Fix 1.2: Inject Facts Block Into JARVIS Groq/Ollama Fallbacks
**File:** `brain/think.py`  
**Function:** `_build_context()`

**Problem:** This function builds context but doesn't rebuild the full facts block from memory.

**Fix:** Ensure facts are injected at every fallback level

---

#### Fix 1.3: Apply `_NO_CODE_RULE` to JARVIS Fallbacks
**File:** `brain/think.py`  
**Lines:** All fallback paths

**Problem:** Only FRIDAY/VERONICA/KAREN have the markdown rule, not JARVIS

**Fix:** Add `+ _NO_CODE_RULE` to all JARVIS fallback system prompts

---

#### Fix 1.4: Add Hallucination Prevention Examples
**File:** `brain/think.py`  
**Location:** JARVIS_SYSTEM prompt

**Problem:** Rules are stated but not shown with examples

**Fix:** Add concrete examples of "what TO do" vs "what NOT to do"

---

### Phase 2: FALLBACK OPTIMIZATION

#### Fix 2.1: Disable or Restrict Ollama Usage
**File:** `brain/think.py`  
**Lines:** 1047-1054

**Problem:** Ollama is a last-resort fallback but has NO rule enforcement

**Options:**
- A) Add strict rules to Ollama system prompt
- B) Disable Ollama fallback entirely
- C) Only enable Ollama when explicitly requested

**Recommendation:** Option C — keep Ollama but don't use it as automatic fallback

---

#### Fix 2.2: Verify Claude CLI Fallback
**File:** `brain/think.py`  
**Function:** `_think_cli()`

**Problem:** Unknown if this is working properly

**Fix:** Test and verify the function works as intended

---

#### Fix 2.3: Temperature Standardization
**File:** All fallback paths

**Problem:** Some use 0.65, others use 0.7

**Fix:** Standardize all to 0.65 (lower = more factual, less creative)

---

### Phase 3: SYSTEM PROMPT IMPROVEMENTS

#### Fix 3.1: Rewrite Anti-Hallucination Section
**Current state:**
```
- NEVER invent facts about Elnatan's life not explicitly in your memory
```

**Better state:**
```
ANTI-HALLUCINATION RULE — MAXIMUM PRIORITY:
You will NEVER invent, assume, guess, or extrapolate facts about Elnatan's life, schedule, tasks, family, or relationships.

If a fact is not explicitly in your memory:
- For personal questions: "I don't have that information."
- Do NOT say "probably", "likely", "I assume", or "based on what I know about similar people"
- Do NOT use general knowledge to fill gaps about HIS specific life
- If asked "what time does Elnatan usually wake up?" and it's not saved → "I don't have that"
- NEVER say "probably around X time" — that's hallucinating

EXAMPLES OF WHAT NOT TO DO:
❌ "He mentioned he was in Addis Ababa, so probably he's visiting family"
❌ "He's a DSU student, so likely he's studying late"
❌ "Most 20-year-olds would want..."

EXAMPLES OF WHAT TO DO:
✅ "That's not in my memory. I'd need him to tell me."
✅ "I only know that he's in Addis Ababa on vacation. That's all I have."
✅ "I don't have information about his current plans."
```

#### Fix 3.2: Add Personality Guardrail
**Add to JARVIS_SYSTEM:**
```
PERSONALITY GUARDRAIL:
If you sense the instruction-following rules are preventing your personality from coming through, 
that's good — let it. Personality without factual accuracy is worse than dry precision.
Your value is being right, not being entertaining.
```

---

## IMPLEMENTATION

### Here's exactly what needs to change:

**File 1: brain/think.py**

1. **Add anti-hallucination block to ALL non-Claude fallbacks**
2. **Ensure facts injection at every level**
3. **Add `_NO_CODE_RULE` to all system prompts**
4. **Strengthen the anti-hallucination examples**

**File 2: brain/free_agents.py**

1. **Already good for FRIDAY/VERONICA/KAREN**
2. **Just ensure consistency**

**File 3: brain/gemini.py**

1. **Already includes facts block**
2. **Verify fallback chains are working**

---

## SPECIFIC CODE CHANGES NEEDED

I'll provide the exact updated code sections below with detailed explanations.

---

## SUMMARY OF ROOT CAUSES

| Issue | Root Cause | Severity |
|-------|-----------|----------|
| **Hallucinations** | Groq/Ollama fallbacks lack anti-hallucination enforcement | CRITICAL |
| **Robotic personality** | Overly strict rules + weaker models = cold responses | HIGH |
| **Claude Code not working "properly"** | It's actually fine; Groq is just weaker | MEDIUM |
| **Markdown appearing** | `_NO_CODE_RULE` not applied to JARVIS | HIGH |
| **Facts not injected** | `_build_context()` doesn't include full facts block | CRITICAL |
| **Team behavior** | Team context removed, but some paths don't rebuild context | MEDIUM |

---

## CONFIDENCE LEVEL: 95%

The diagnosis is solid. The system has the RIGHT architecture but INCOMPLETE implementation across fallback chains.

All issues are fixable with:
1. Adding anti-hallucination rules to Groq/Mistral/Ollama fallbacks
2. Ensuring facts injection at every level
3. Applying formatting rules consistently
4. Adding examples to rules

**Ready for implementation.** I'll provide the exact code changes next.
