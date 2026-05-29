# Multi-Agent Communication Model

**Status:** Chosen Architecture (as of current conversation)  
**Date:** 2026-05-28  
**Owner:** Elnatan Anbelu  
**Primary Interface (Current):** HUD

---

## Chosen Model

**Name:** Smart Visibility Group Chat with Human Participation

### Core Principles

- All agents (JARVIS, FRIDAY, VERONICA, KAREN) + Elnatan exist in one shared communication space ("group chat").
- Agents are allowed to talk to each other.
- Elnatan has **full visibility** by default but with smart handling to avoid noise.
- Elnatan can be **passive** (watch the end result) or **active** (interrupt and correct in real time).
- Safety and control are prioritized, especially around the Personal Second Brain.

### Visibility Rules (Option B - Smart Visibility)

- Agents can have internal/low-stakes coordination.
- Low-value or purely internal agent chatter can be **auto-collapsed** or marked as low priority.
- Anything involving the **Second Brain**, personal information, decisions, relationships, business, or recurring patterns must be marked as **Important** and surfaced clearly.
- Elnatan sees the full transcript but is not overwhelmed by noise.

### Notification Rules

- Elnatan wants to be **notified** when agents discuss:
  - Anything from or about the Second Brain
  - Personal topics, decisions, relationships, or patterns about him
  - High-stakes or sensitive subjects
- Notifications should work even if he is not actively looking at the HUD at that moment.
- Goal: He can stay in control without needing to constantly monitor the chat.

### Participation Model

- **Passive mode**: Elnatan can observe the group chat and only see the final output or summary when agents are done.
- **Active mode**: At any point, Elnatan can jump in, correct agents, give new instructions, or redirect behavior.
- This hybrid approach gives both efficiency (agents can work together) and control (Elnatan can intervene).

---

## Current State (2026-05-28)

- **Primary Interface**: HUD (desktop)
- **Phone / Mobile Access**: Deferred for now
- **Agent-to-Agent Communication**: Allowed, but must follow Smart Visibility rules
- **Second Brain Access**: JARVIS is the primary gatekeeper. Other agents should generally route Second Brain requests through JARVIS (see earlier architectural discussions).

---

## Deferred Requirement: Phone / Mobile Access

**Status**: Explicitly deferred, but **must not be forgotten**.

### Why This Matters

Elnatan wants to be able to participate in the agent group chat (and receive notifications) from his phone. This is considered important for real daily usage and staying in control of the system.

### Detailed Requirements (to be implemented later)

- Full or near-full access to the group chat from a mobile device.
- Ability to see agent conversations (with smart visibility applied).
- Receive notifications for important / Second Brain related messages.
- Ability to reply and correct agents from the phone.
- Reasonable mobile experience (not just a raw desktop HUD ported to phone).
- Support for the same participation model (passive watching vs active interruption).

### Suggested Future Interfaces

- Dedicated mobile app (preferred long-term)
- Enhanced Telegram integration (faster to ship)
- Web-based mobile view (fallback)

### Notes

- This requirement should be referenced in any future planning for the HUD, notification system, or proactive features.
- When designing the observer, proactive surfacing, or Second Brain-related features, mobile access should be considered as a first-class requirement rather than an afterthought.

**Do not deprioritize this indefinitely.** It is a core part of the desired user experience.

---

## Open Questions (as of now)

- How will notifications actually be delivered on desktop when using the HUD?
- Will there be a dedicated "Agent Chat" view vs the normal JARVIS conversation view?
- How strictly do we enforce that other agents route Second Brain requests through JARVIS?
- What is the long-term primary interface once phone access is added?

---

## Related Decisions

- JARVIS remains the primary owner and gatekeeper of the Personal Second Brain.
- High-risk writing to the brain should continue to go through proposals.
- The overall goal is a transparent, controllable, multi-agent system where Elnatan feels like he is "in the group chat" rather than just a user being served by agents.

---

**Last Updated**: 2026-05-28  
**Next Review**: When phone/mobile access work begins or when the communication system is implemented.