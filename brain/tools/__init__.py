from brain.tools.registry import get_tools, execute_tool, TOOL_REGISTRY

# Import all domain modules so their tools self-register on package load
import brain.tools.messaging
import brain.tools.system
import brain.tools.web
import brain.tools.calendar
import brain.tools.files
import brain.tools.code
import brain.tools.data
import brain.tools.memory
import brain.tools.business
import brain.tools.personal
import brain.tools.strategy
import brain.tools.second_brain

# TOOLS in OpenAI/Groq format — compatible with the original brain/tools.py API
TOOLS = [
    {
        "type": "function",
        "function": {
            "name": entry["schema"]["name"],
            "description": entry["schema"]["description"],
            "parameters": entry["schema"]["input_schema"],
        },
    }
    for entry in TOOL_REGISTRY.values()
]

__all__ = ["get_tools", "execute_tool", "TOOL_REGISTRY", "TOOLS"]
