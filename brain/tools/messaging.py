"""Messaging tools — email, iMessage, WhatsApp."""
from brain.tools.registry import tool


@tool(
    description="Send an email to someone",
    parameters={
        "to":      {"type": "string", "description": "Recipient email address"},
        "subject": {"type": "string", "description": "Email subject line"},
        "body":    {"type": "string", "description": "Email body content"},
    },
    risk="red",
)
def send_email(to: str, subject: str, body: str) -> str:
    from control.email import send_email as _send
    return _send(to, subject, body)


@tool(
    description=(
        "Send an iMessage or SMS to someone. CRITICAL: The 'message' field MUST be "
        "exactly what the user said to send. NEVER pull message content from conversation "
        "history, briefings, news, or any other context. If the user did not explicitly "
        "say what to send, do NOT call this tool — ask them first."
    ),
    parameters={
        "contact": {"type": "string", "description": "Contact's real name as it appears in Contacts (e.g. 'Mom', 'Dad'). Never guess a phone number."},
        "message": {"type": "string", "description": "The exact message the user told you to send. Must come directly from the user's words, nothing else."},
    },
    risk="red",
)
def send_imessage(contact: str, message: str) -> str:
    from control.messages import send_imessage as _send
    return _send(contact, message)


@tool(
    description="Read recent unread emails from inbox",
    parameters={
        "count": {"type": "integer", "description": "Number of emails to read (default 5)"},
    }
)
def read_emails(count: int = 5) -> str:
    from control.email import read_emails as _read
    return _read(count)


@tool(
    description="Send a WhatsApp message to a phone number or contact",
    parameters={
        "to":      {"type": "string", "description": "Phone number with country code e.g. +251911202059"},
        "message": {"type": "string", "description": "Message to send"},
    },
    risk="red",
)
def send_whatsapp(to: str, message: str) -> str:
    from control.whatsapp import send_whatsapp as _send
    return _send(to, message)
