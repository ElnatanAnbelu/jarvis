# Alfred — The Living Environment (BUILD SPEC, locked from interrogation)

> Status: awaiting one "go ahead". Not a control room, not a chatbot — a fullscreen,
> always-running holographic environment Elnatan **lives inside**, with a proactive
> companion at its center who sees, hears, talks, advises, and does anything.

## The concept (from the interrogation)
Alfred is the **one and only surface** — the orb, the old control room, and the old HUD
are retired. He runs **fullscreen, always on**; Elnatan boots into Alfred and works *inside*
him. In the **middle** is Alfred's living body — the **holo-schematic hologram** — that reacts
as he listens / thinks / speaks. He is **always listening** and **jumps in on his own** with
advice and observations, but **reads the room** (saves non-urgent things for a natural break;
interrupts instantly only when it matters). He is **always watching** through the camera
(face recognition, presence/mood) with an **always-on awareness HUD** (your face framed, a
live voice waveform, presence status).

When you ask him to do or show something, the **hologram docks to a corner** and Alfred
**auto-arranges** the content himself (no window management). You work **fluidly** — sometimes
hands-on in his panels, sometimes you just tell him and watch him do it.

## Visual + sensory (defaulted from what's decided — veto if wrong)
- **Aesthetic:** holo-schematic cyan (the boot direction he loved), applied to the whole
  environment. **Mood shifts with context:** calm/warmer when idle or talking, sharp/bright/busy
  when working.
- **Sound:** full cinematic — a boot sound, subtle holographic UI sounds (panels, alerts), and
  his voice.
- **Persona (already locked in `brain/agent.py`):** refined British butler — dry wit, calls him
  "sir", warm — but **brutally honest, pushes back, never a yes-man** (Pennyworth with teeth).
- **Boot:** the random holo boot screen → dissolves into the environment.

## Surfaces inside the environment (all v1 — "the whole vision")
1. **Alfred core (center):** the holo hologram avatar — idle breathing, listening ripple,
   thinking assembly, speaking pulse. Docks to a corner when content is up.
2. **Awareness HUD:** live camera feed w/ face-detection + recognition, voice waveform on
   speech, presence/mood readout. Always visible.
3. **Code + terminal panel:** write/run code inside Alfred (owner-frictionless via the gate).
4. **Web browser panel:** browse/research in-environment.
5. **Second Brain panel:** notes, memories, life data (the vault).
6. **Operator dashboards:** the old control-room content becomes panels Alfred summons —
   pending approvals, activity feed + per-action undo, system health, mode, **panic** — plus
   calendar, comms, business. (Real action needs live credentials — see gated items.)
7. **Auto-layout engine:** Alfred decides what panel(s) to show and how to arrange them from
   what you asked.

## Non-negotiables carried over
- **One local Alfred brain** (`brain/agent.py`), fully offline by default. No 4 agents.
- **Safety gate on every action:** owner code/screen frictionless; money / send / delete /
  external still confirm; **panic** always available (gesture/command + panel).
- **Always local** — voice in/out, brain, vision all on-device.

## Build order (delivered as one environment; built in this internal sequence)
- **A — The soul:** the fullscreen shell + holo core avatar + awareness HUD + always-listening
  voice loop, wired to the one brain, proactive + reads-the-room. (This alone is "Alfred is here.")
- **B — The panels:** code+terminal, browser, Second Brain, operator dashboards + the dock-to-corner
  + auto-layout.
- **C — Sensory + polish:** sound design, mood-shift, camera face-recognition, transitions.
- **D — Cutover:** retire the old orb/control/HUD pages; delete the stale `JARVIS.app`; build a
  fresh **Alfred.app** that boots straight into the environment.

## Still needs Elnatan (can't be built; for the operator panels to truly act)
- Mic test (hands-free wake/listen on his hardware) · camera/face enrollment · live credentials
  (Gmail/Notion/WhatsApp → vault) · a Caine/Alfred voice sample for the clone.

## Tech approach
Fullscreen frameless `pywebview` app loading a new SPA (`app/alfred.html` + assets), replacing
the current windows; camera/mic via `getUserMedia` in the webview; panels are in-environment
components; code/terminal/web/vault/operator wired to the existing tool registry + gate + the
local brain. Holo rendered with Canvas/CSS (from the boot design).
