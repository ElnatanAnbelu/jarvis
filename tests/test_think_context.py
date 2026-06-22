"""P2d + P6: sharper personal-context retrieval and context dedup in brain.think.

These are model-free unit tests. They monkeypatch the vault search and memory
accessors so no FAISS index is built, no model is loaded, and nothing touches
the real Second Brain on disk.
"""
import brain.think as think


# ── P2d: _should_query_personal uses the embedding search to decide ──────────

def _no_vault(monkeypatch):
    """Vault returns nothing — i.e. no semantically relevant note."""
    monkeypatch.setattr(think, "_vault_search", lambda u, max_results=5: "")


def _vault_hits(monkeypatch, payload="### Personal/Routine\nElnatan lifts at 6am."):
    """Vault returns a relevant note for any non-trivial query."""
    monkeypatch.setattr(think, "_vault_search", lambda u, max_results=5: payload)


def test_short_and_status_turns_skip_without_touching_vault(monkeypatch):
    calls = {"n": 0}

    def spy(u, max_results=5):
        calls["n"] += 1
        return "### x\nsomething"

    monkeypatch.setattr(think, "_vault_search", spy)

    assert think._should_query_personal("") is False
    assert think._should_query_personal("hi") is False          # < 6 chars
    assert think._should_query_personal("are you there") is False
    assert think._should_query_personal("you online?") is False
    # None of those should have consulted the (expensive) embedding search.
    assert calls["n"] == 0


def test_pure_technical_turn_skips_embedding(monkeypatch):
    calls = {"n": 0}

    def spy(u, max_results=5):
        calls["n"] += 1
        return "### x\nsomething"

    monkeypatch.setattr(think, "_vault_search", spy)

    # Strong project signal, zero personal signal → fast technical skip.
    assert think._should_query_personal("fix the python import error in this module") is False
    assert calls["n"] == 0


def test_personal_turn_fires_only_when_vault_has_a_relevant_note(monkeypatch):
    # A genuinely owner-about turn: when the vault surfaces a relevant note we
    # treat it as personal; when it surfaces nothing we don't.
    _vault_hits(monkeypatch)
    assert think._should_query_personal("how has my sleep been lately") is True

    _no_vault(monkeypatch)
    assert think._should_query_personal("how has my sleep been lately") is False


def test_openended_turn_grounded_when_note_exists(monkeypatch):
    # No project signal, no obvious personal keyword, but a relevant note exists
    # → embeddings decide it's personal (the keyword heuristic would have missed).
    _vault_hits(monkeypatch, payload="### Personal/Bio\nHe is building Acme.")
    assert think._should_query_personal("what am I working towards again") is True


def test_get_personal_context_reuses_same_search(monkeypatch):
    _vault_hits(monkeypatch, payload="### Personal/Routine\nElnatan lifts at 6am.")
    ctx = think._get_personal_context("tell me about my routine")
    assert "Elnatan lifts at 6am." in ctx
    assert "STORED FACTS" in ctx

    _no_vault(monkeypatch)
    assert think._get_personal_context("tell me about my routine") == ""


def test_vault_search_caches_per_turn(monkeypatch):
    calls = {"n": 0}

    class _Inst:
        def search_vault(self, q, max_results=5):
            calls["n"] += 1
            return "### Personal/X\nfact one here"

    import memory.vault as _vm
    monkeypatch.setattr(_vm, "_second_brain_instance", _Inst(), raising=False)
    # reset the module-level cache
    think._vault_search._cache = None

    a = think._vault_search("same query about my life")
    b = think._vault_search("same query about my life")
    assert a == b
    assert calls["n"] == 1  # second call served from cache


# ── P6: _dedup_context collapses repeated fact lines ─────────────────────────

def test_dedup_collapses_repeated_fact_lines():
    ctx = (
        "\nSTORED FACTS ABOUT ELNATAN:\n"
        "Elnatan is the founder of Acme.\n"
        "Elnatan trains at 6am every morning.\n"
        "\nSTORED FACTS (your Second Brain notes):\n"
        "### Personal/Bio\n"
        "Elnatan is the founder of Acme.\n"      # duplicate of the fact above
        "He reads one book a week.\n"
    )
    out = think._dedup_context(ctx)
    # The duplicated long fact appears exactly once now.
    assert out.count("Elnatan is the founder of Acme.") == 1
    # Distinct facts all survive.
    assert "Elnatan trains at 6am every morning." in out
    assert "He reads one book a week." in out
    # Section headers (end with ':') are preserved even though they repeat-ish.
    assert "STORED FACTS ABOUT ELNATAN:" in out
    assert "STORED FACTS (your Second Brain notes):" in out


def test_dedup_preserves_headers_blanks_and_code():
    ctx = (
        "### A\n"
        "### A\n"            # markdown header — kept (structural)
        "```python\n"
        "x = 1\n"
        "x = 1\n"            # inside code fence — kept verbatim
        "```\n"
    )
    out = think._dedup_context(ctx)
    assert out.count("### A") == 2
    assert out.count("x = 1") == 2


def test_dedup_noop_on_empty():
    assert think._dedup_context("") == ""
    assert think._dedup_context(None) is None


def test_build_context_dedups_grounding(monkeypatch):
    from memory import memory as _mem
    # Facts and a vault note that share an identical fact line.
    monkeypatch.setattr(think, "get_facts", lambda: "Elnatan founded Acme in 2024.")
    monkeypatch.setattr(think, "get_context", lambda u: "")
    monkeypatch.setattr(_mem, "get_last_session_summary", lambda: "")
    monkeypatch.setattr(_mem, "get_history_summary", lambda: "")
    monkeypatch.setattr(think, "_is_business_query", lambda u: False)
    monkeypatch.setattr(think, "_should_query_personal", lambda u: True)
    monkeypatch.setattr(
        think, "_get_personal_context",
        lambda u: "\nSTORED FACTS (notes):\nElnatan founded Acme in 2024.\n",
    )

    ctx = think._build_context("tell me about my company", include_history=False)
    assert ctx.count("Elnatan founded Acme in 2024.") == 1
