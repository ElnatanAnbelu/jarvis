# Phase 2 Rendering Strategy — Home Zone & Agent Orbs

**Status:** Active decision record  
**Date:** 2026-05-29  
**Relates to:** `app/hud.html` Home Zone IIFE (`<script>` block 2)

---

## Current Approach (Milestones 1–3): Canvas 2D

The Home Zone bubble, cloud expansion, and session start ritual are implemented
using the browser's 2D Canvas API (`CanvasRenderingContext2D`). A full-viewport
`<canvas id="hz-canvas">` element sits at z-index 50, above all existing HUD
DOM elements.

**Why Canvas 2D was chosen for this phase:**

| Criterion | Canvas 2D verdict |
|---|---|
| Dependency footprint | Zero — no Three.js, no GLSL compiler |
| Integration with existing hud.html | Trivial — same pattern as `ring-canvas` |
| 60 fps at Milestone 1–3 load (1 bubble, 4 motes, 1 expansion cloud) | Measured safe — existing ring-canvas renders 200 teeth + 5 circuit rings + 3 nodes + waveform at 60 fps |
| Volumetric depth | Faked well via layered `createRadialGradient()` calls |
| Bloom | CSS `drop-shadow` filter on canvas element + in-canvas bloom gradients |
| Organic motion | Custom 3-octave value noise function (~20 lines, no dep) |
| Spring easing for orb arrivals | `cubic-bezier(0.16, 1, 0.3, 1)` applied via manual interpolation in the rAF loop |

**What Canvas 2D cannot do well (the WebGL threshold):**

| Feature | Why Canvas 2D breaks down |
|---|---|
| 4 corner orbs × 200 particles each = 800 simultaneous particles | Canvas 2D loops are CPU-bound; instanced GPU draw calls needed |
| True Kawase / dual-filter bloom | Requires ping-pong framebuffers; CSS drop-shadow is a pale substitute at large scales |
| 3D depth parallax (orb rotation as you move the window) | No perspective transform in 2D canvas |
| Energy arcs between collaborating agents | Bezier trails with real-time thickness taper need geometry shaders |
| "Really Active" directed particle streams (spec §5.3) | High-density directed bursts at 60 fps require GPU instancing |

The threshold is roughly: **any state that requires all 4 agents simultaneously outside the Home Zone**. That is Phase 2's agent lifecycle (spec roadmap Phase 2), not Phase 1.

---

## Planned Upgrade: Custom WebGL (no Three.js)

The spec states (§8.1): *"WebGL (Three.js or custom GLSL) or Metal/SceneKit on native. This is non-negotiable for the 'real JARVIS' feel."*

**Decision: custom GLSL shaders, not Three.js.**

Rationale: Three.js adds ~600 KB, imposes a scene-graph abstraction that fights our flat Canvas/DOM hybrid, and provides abstractions we don't need (cameras, loaders, scene hierarchy). The orb shader is a bounded problem (~150 lines GLSL + ~200 lines JS scaffolding) that we can own completely.

### Upgrade boundary

The sole code change required is inside `drawBubble()` and `drawMinimizedBubble()` in the HomeZone IIFE. The state machine (`hz.*`), drag system, hitbox sync, public API (`window._hz*`), and ritual sequence are all WebGL-agnostic. The render path is cleanly separated from the interaction and state layers.

**Upgrade checklist (when Phase 2 agent lifecycle begins):**

- [ ] Create `app/hz-shader.vert` and `app/hz-shader.frag` — orb layer construction matching spec §2.6 exactly (7 layers, agent personality noise, Kawase bloom)
- [ ] Create `app/hz-webgl.js` — thin WebGL scaffolding: context init, buffer/attribute setup, uniform update per frame
- [ ] Replace `drawBubble()` in the HomeZone IIFE with a call to `hzWebGL.drawOrb(cx, cy, agentName, stateParams)`
- [ ] Replace CSS `drop-shadow` filter on `#hz-canvas` with WebGL's own bloom pass (ping-pong FBO)
- [ ] Profile on target hardware: 2019 MacBook Pro Intel + 2020 M1 Air
- [ ] Graceful degradation path: if `getContext('webgl2')` fails, fall back to Canvas 2D (current code)

### SwiftUI parity notes

`JARVISApp/JARVIS/HUDRingView.swift` currently uses SwiftUI `Circle().stroke()` layers.
The Phase 2 native upgrade should use **Metal + SceneKit** (or a custom `CAMetalLayer`
inside a `UIViewRepresentable`) to match the web WebGL aesthetic. The same orb layer
construction (7 layers) applies. The agent color constants are already aligned:

| Agent | Hex | Swift `Color(hex:)` |
|---|---|---|
| JARVIS | `#00E5FF` | `Color(hex: "00E5FF")` |
| FRIDAY | `#FF6A00` | `Color(hex: "FF6A00")` |
| VERONICA | `#00FF9F` | `Color(hex: "00FF9F")` |
| KAREN | `#FFB450` | `Color(hex: "FFB450")` |

---

## Performance Targets (from spec §8.2, for reference)

- 60 fps sustained: 4 orbs + 3 content windows + full particle sets on 2019+ MacBook Pro
- 48–60 fps on M1/M2 base Air
- Graceful degradation: particle count and bloom quality drop before frame rate
- "Really Active" animations must begin within 60 ms of trigger decision

---

*This document is the authoritative record of the Canvas 2D → WebGL transition plan.*  
*Update it when the upgrade begins; do not delete the Canvas 2D rationale section.*
