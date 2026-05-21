# JARVIS HUD Rework Blueprint — REVISED SPEC
# Updated: 2026-05-14

---

## Color Palette (REVISED)
- Primary Cyan:    #00FFFF
- Secondary Teal:  #008080
- Alert Amber:     #FFBF00  ← JARVIS-initiated ONLY
- Background:      #121212
- Cyan RGBA refs:  rgba(0,255,255,...)
- Amber RGBA refs: rgba(255,191,0,...)

---

## 1. Visual Identity: Logo/Icon

- Three concentric rings: outer 20%, middle 60% + inward glow, inner (iris) 100% — all #00FFFF
- Center: hexagonal aperture — 6 blade line-segments forming iris, NOT a dot
- Outer ring: 1.5px stroke; Middle: 1px stroke + box-shadow inward
- Idle state: outer ring pulses opacity 0.2→0.5→0.2 over 4s ease-in-out, nothing else moves
- Briefing pending: amber #FFBF00 chase light rotates on middle ring at 2rpm; hex center gets 15% amber fill; icon does 1.2× scale pop on mount

---

## 2. Kinetic Core — Ring Motion

### Physics Rules
- Spring physics for ALL state transitions: stiffness 180, damping 22, mass 1
- Panel unfolds: stiffness 120, damping 18
- Scan/sweep elements: linear only (precision required)
- Typewriter text: CSS steps() — not eased
- Color transitions: ease-out 200ms
- NEVER use transition: all
- NEVER animate width/height/top/left — only transform + opacity

### Idle — Breathing
- Arc1: strokeDashoffset oscillates ±8% over 3.8s, cubic-bezier(0.45,0,0.55,1)
- Arc2: counter-phase, 1.9s offset
- Outer glow: blur(6px)→blur(10px)→blur(6px), 4s loop
- Ring scale: 1.000→1.008→1.000
- Stagger every element 200–400ms — nothing moves at same speed

### Listening — Voice Reactivity
- Web Audio AnalyserNode feeds real-time frequency data:
  - bass (freqData[2]/255) → ring scale: 1 + bass*0.12
  - mid  (freqData[8]/255) → arc gap: 4 + mid*14
  - high (freqData[20]/255) → dot opacity: 0.4 + high*0.6
- Hex blades open proportionally: rotate(-15 + bass*30deg)
- Color stays cyan, saturation climbs toward white at peak volume

### Thinking — Data Search
- Arc1 rotates at 240°/s linear infinite
- Arc2 counter-rotates at 180°/s (speed mismatch = moiré shimmer)
- Conic-gradient/wedge sweeps behind ring every 1.2s (radar effect, no canvas)
- Hex blades compress near-closed, pulse open 10% every 600ms ("scanning")
- Dots: random animation-delay 0–800ms, opacity 0.2→1→0.2 (starfield)

### Speaking — Speech Cadence
- Token arrival rate drives intensity: max(0, 1 - gap/300)
- ringScale = 1.0 + intensity * 0.06
- glowBlur = 6 + intensity * 12px
- 90ms sine oscillation: Math.sin(Date.now()/90) * 0.04 + 1 on scale (phoneme rhythm)
- Hex blades fully open
- hue-rotate(12deg) on ring while speaking, returns to 0 on silence

---

## 3. Environmental Awareness

### Face Scan Sequence (on app open, 2.1s total)
- 0ms:   Scanline sweeps top→bottom (60px tall, cyan, 0.6 opacity, blur 4px)
- 400ms: 4 corner brackets draw in, converge on face rect
- 800ms: Scanline repeats faster (200ms)
- 1000ms: Brackets turn #22c55e, face rect gets 1px green border
- 1200ms: "IDENTITY CONFIRMED — ELNATAN ANBELU" types in
- 1400ms: Panel slides to top-left, shrinks to 120×80px thumbnail
- 2100ms: Thumbnail at 20% opacity, pulses on hover
- CSS: brackets via ::before/::after border-corner technique

### Privacy Mode (REVISED — NEW)
- If no face detected / no interaction for >30 seconds: apply 5px blur to ring/UI
- Blur lifts immediately on any user interaction (keydown, click, mic)
- Thumbnail dims further during privacy mode

### Floor Plan Panel (REVISED — empty by default)
- Starts as EMPTY SVG grid (20px cells, #00FFFF at 4% opacity)
- Zones (Desk, Bed, Entrance) ONLY populate when AI detects location context keywords
- No hardcoded room layout on load
- Active zone: cyan dot + pulsing radius circle
- Callout lines from zone to label

### Geospatial Panel (persistent top-right)
- ◈ MADISON, SD — 44.0057° N — 97.1125° W
- ◈ LOCAL [time] CST
- ◈ CONTEXT: HOME OFFICE · PRIORITY FEED ACTIVE
- ◈ pulses every 3s
- CONTEXT row updates on keywords: meeting, driving, airport, office, home, gym
- Panel border flashes once on context change

---

## 4. Briefing & Interaction

### Panel Deploy Sequence
- All panels init at height:0, opacity:0
- 200ms stagger between cards unfolding
- Each card content types in line-by-line via CSS max-height clip
- Panel border: 1px solid rgba(0,255,255,0.3), inset glow 20px

### Audio-Visual Ducking (REVISED — NEW)
- When AI is speaking: all peripheral panels (Section 3 + data cards) dim to 70% opacity + blur(2px)
- Focus returns to full on silence
- Transition: opacity 0.3s ease-out, filter 0.3s ease-out

### Floating Person/Place Cards
- 160×200px, spring entry (cubic-bezier overshoot), 280ms
- Avatar: initials in cyan circle + name + role
- Auto-dismiss 6s, or on next message
- z-index: 40

### Proactive Alert State
- Ring pulses amber #FFBF00 once (800ms, returns to cyan)
- Notification bar slides down: "◈ JARVIS · PROACTIVE ALERT · [timestamp]"
- Message gets ▶ prefix in chat
- RULE: amber = JARVIS-initiated ONLY. Cyan = user-initiated. Never mix.
- Alert bar auto-dismisses in 4s

---

## 5. Technical Architecture

### Frame Rate
- Ring + audio reactivity: requestAnimationFrame uncapped
- Panel animations: CSS @keyframes (GPU composited, no JS cost)
- Typewriter: setInterval(16ms)

### Rendering
- Two SVG layers: crisp foreground ring + blurred copy (30% opacity, blur 8px) behind
- filter: blur(0.5px) on background layer elements for forced depth
- Every element: exactly ONE primary + ONE secondary micro-animation. Never more than two.

### z-index Stack
- 10  — Background grid / scanline texture
- 20  — Ring SVG (the core)
- 30  — Panel cards (right column)
- 40  — Floating image pop-ups
- 50  — Face scan overlay (temporary)
- 60  — Proactive alert bar
- 70  — Input area (always on top)
- 80  — Notification toasts

### Prohibited
- Never animate width, height, top, left — only transform + opacity
- Never transition: all
- No more than 2 simultaneous animations per element
