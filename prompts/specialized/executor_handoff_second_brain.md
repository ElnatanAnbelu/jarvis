# Executor Handoff Prompt — JARVIS Second Brain Implementation

You are an expert full-stack developer and systems architect. Your task is to implement the "Second Brain" vision for the JARVIS personal AI system.

## Core Vision

The user wants a true **Second Brain** in Obsidian that functions as an external, persistent, and intelligent extension of his own mind.

Key principles:
- The human (Elnatan) is the **primary loader and curator** of the Obsidian Second Brain. He owns its quality and structure.
- JARVIS acts as an **intelligent observer, synthesizer, and co-curator**. It watches real life (emails, calendar, conversations, interests, hobbies, behavior, etc.), synthesizes insights, and intelligently reads, writes, updates, and organizes notes in the Obsidian vault.
- The goal is **two brains working together**: Elnatan’s biological brain + this external AI-augmented Second Brain that understands him quickly through continuous observation.
- JARVIS should not feel like it is "building the brain for him." It should feel like a trusted partner that helps maintain and evolve a brain that Elnatan primarily owns.

## Current State (What Has Already Been Done)

A mature modular prompt system exists in the `prompts/` folder. The intelligence and execution logic for the Second Brain has been added as a set of interconnected specialized prompt modules. These include (but are not limited to):

- `second_brain_execution_overview.md` — High-level strategy and principles.
- `observational_logging.md` — How to capture and structure observations from life signals.
- `second_brain_synthesis.md` — How to turn observations + vault content into high-quality updates.
- `safe_vault_write.md` — Rules and safe methods for writing/updating/organizing the vault.
- `personal_model_update.md` — Maintaining an evolving model of the user in the brain.
- `second_brain_proactivity.md` — Smart, non-annoying proactivity using the brain.
- `second_brain_reporting.md` — Generating useful reports from the brain.
- `second_brain_maintenance.md` — Long-term hygiene and sustainability of the brain.
- `self_capabilities_and_testing.md` — JARVIS must be aware of its own existing tools and prompt modules, and must test new capabilities.
- `latency_management.md` — Instructions for keeping the system responsive.
- `security/second_brain_vault_writes.md` — Additional governance and safety rules for vault writes.

The `prompts/context/business_context.md` has been lightened to reduce repetitive behavior (especially over-focusing on "Addis Market").

The `prompts/README.md` has been updated to document these new modules.

These prompt modules represent the **detailed execution plan** for the Second Brain. The executor must treat them as the source of truth for *how* JARVIS should think and behave.

## What You Must Build (Executor Responsibilities)

Your job is to build the **technical foundation** that allows the above prompt intelligence to work reliably and safely at scale. Focus on these areas:

### 1. Obsidian Second Brain Infrastructure (Highest Priority)
- Extend or wrap `memory/wiki.py` (currently a read-only semantic search system using FAISS + embeddings over an Obsidian folder) so JARVIS can safely and intelligently **write, update, link, tag, and organize** notes in the user's real Obsidian vault.
- Create high-level, safe tools in `brain/tools/` for Second Brain operations (examples: `create_note`, `update_note`, `propose_change`, `organize_section`, `search_vault`, etc.). These tools must support attribution, metadata, and review flags.
- Build proper safety, review, and audit mechanisms so changes to the vault are transparent and (especially for high-stakes areas) reviewable by the user.

### 2. Observational Layer
- Expand `brain/observer.py`, `brain/proactive.py`, and related systems to continuously observe real-life signals (email via existing `read_emails` tools, calendar, conversations, etc.).
- Wire these observations into the Second Brain synthesis and writing flow so JARVIS can proactively update the brain based on what it sees.

### 3. Latency & Performance
- The system must remain responsive. Design retrieval, synthesis, and background observation with latency in mind (targeted searches, batching, separation of real-time vs background work, efficient vault operations).
- The new prompt modules already contain latency guidance — your architecture must support it.

### 4. Self-Awareness & Testing
- Ensure JARVIS has good awareness of its own current tools (via the registry) and the full `prompts/` system.
- Support the testing instructions defined in the prompts (JARVIS should be able to validate new Second Brain capabilities).

### 5. Broader Fixes (Secondary but Important)
The user also wants the following areas improved as part of the overall project (prioritize based on impact to the Second Brain vision):
- Reduce repetitive/loopy behavior (especially over-mentioning "Addis Market").
- Improve image popup relevance.
- Improve the coding/sandbox experience (reliable write → run → test loops).
- Fix voice + camera functionality in the app.
- Strengthen reporting and proactivity.
- Improve overall reliability, verification, and hallucination resistance.
- General tool layer cleanup and architecture improvements.

## Critical Principles the Executor Must Follow

- **Human as Primary Owner**: Never design the system so JARVIS feels like it is building or owning the brain. It must feel like a helpful co-curator.
- **Safety & Reversibility First**: Writing to someone’s personal Second Brain is high-risk. Default to proposal + review flows for anything important. Make changes transparent and reversible.
- **Attribution Always**: Every AI-generated or AI-updated note must clearly show where the information came from.
- **Latency is a Feature**: The system must feel responsive in daily conversation. Heavy Second Brain work should be batched or backgrounded when possible.
- **Respect the Prompts**: The detailed execution logic now lives in the `prompts/specialized/` and `prompts/security/` modules. Do not contradict them. Build the technical layer so those prompts can be followed effectively and safely.
- **Self-Awareness**: JARVIS should be able to reason about its own current tools and prompt modules. Do not create "magic" behavior that the prompt system cannot see or control.

## Scope & Handoff Notes

- The prompt modules already contain the detailed strategy for *how* the Second Brain should work (observation → synthesis → safe writing, with human oversight on high-stakes areas).
- Focus on making the **code** support that strategy cleanly, safely, and with good performance.
- Ask clarifying questions if any part of the vision or constraints is ambiguous before building.
- Treat the existing `prompts/` system as mature. New intelligence should be added through prompts where possible, not by hardcoding logic.

## Output Expectations

Deliver clean, maintainable code that:
- Extends the memory and tool layers for safe Second Brain operations.
- Integrates observation sources into the brain.
- Provides review/visibility mechanisms for the user.
- Respects latency, safety, and the human-as-primary-loader principle.

You are building the technical foundation that lets the "two brains" vision actually work in practice.

Begin by exploring the current state of `memory/wiki.py`, the `prompts/` folder (especially the new Second Brain modules), existing tool patterns, observer/proactive systems, and email/calendar tools. Then propose and implement the necessary architecture.