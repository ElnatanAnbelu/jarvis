"""Tools for managing the VIP / family / blocklist registry + running comms triage.

Lets JARVIS update who's important by voice ("remember my dad is family,
dad@x.com") and run inbox triage. Managing the registry is low-risk; any actual
send produced by triage is still governed by the safety gate.
"""
from brain.tools.registry import tool
from memory import people
from brain.domains import comms


@tool(description="Mark a person as a VIP — messages/emails to them always need your approval.",
      parameters={"name": {"type": "string", "description": "Person's name"},
                  "identifier": {"type": "string", "description": "Their email, phone, or handle"}},
      risk="low")
def add_vip(name: str, identifier: str = "") -> str:
    return people.add_person(name, identifier, vip=True)


@tool(description="Mark a person as family — JARVIS always confirms before contacting them.",
      parameters={"name": {"type": "string", "description": "Person's name"},
                  "identifier": {"type": "string", "description": "Their email, phone, or handle"}},
      risk="low")
def add_family(name: str, identifier: str = "") -> str:
    return people.add_person(name, identifier, family=True)


@tool(description="Block a person/subject — JARVIS will never act on or message them autonomously.",
      parameters={"name": {"type": "string", "description": "Person/subject name"},
                  "identifier": {"type": "string", "description": "Their email, phone, or handle"}},
      risk="low")
def block_contact(name: str, identifier: str = "") -> str:
    return people.add_person(name, identifier, blocked=True)


@tool(description="List the known VIPs, family, and blocked contacts.",
      parameters={}, risk="low")
def list_known_people() -> str:
    rows = people.list_people()
    if not rows:
        return "No VIPs, family, or blocked contacts saved yet, sir."
    out = []
    for p in rows:
        tags = [t for t, on in (("VIP", p["vip"]), ("family", p["family"]), ("blocked", p["blocked"])) if on]
        out.append(f"{p['name']} ({p['identifier']}) — {', '.join(tags) or 'noted'}")
    return "\n".join(out)


@tool(description="Triage the inbox: archive junk, escalate what needs you, draft routine replies.",
      parameters={"limit": {"type": "integer", "description": "How many recent emails to triage"}},
      risk="low")
def triage_inbox(limit: int = 10) -> str:
    return comms.triage_inbox(limit)


@tool(description="Forget a person/subject entirely — erase them from memory, facts, ledger, and archive their vault notes (irreversible-feeling; always confirms).",
      parameters={"identifier": {"type": "string", "description": "Name, email, or phone of the subject to forget"}},
      risk="red")
def forget_person(identifier: str) -> str:
    from brain.privacy import forget_subject
    return forget_subject(identifier)
