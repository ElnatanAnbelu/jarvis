"""File tools — read, write, create, delete, move, list, mkdir."""
from brain.tools.registry import tool


@tool(
    description="Read the contents of any file on the Mac. Use to read source code, text files, config files, logs, anything.",
    parameters={
        "path": {"type": "string", "description": "File path (supports ~ for home directory)"},
    }
)
def read_file(path: str) -> str:
    from control.files import read_file as _read
    return _read(path)


@tool(
    description="Write content to an existing file (overwrites completely). Use to update source code, config files, documents.",
    parameters={
        "path":    {"type": "string", "description": "File path to write to"},
        "content": {"type": "string", "description": "Complete file content"},
    }
)
def write_file(path: str, content: str) -> str:
    from control.files import write_file as _write
    return _write(path, content)


@tool(
    description="Create a new file with content. Creates any missing parent directories automatically.",
    parameters={
        "path":    {"type": "string", "description": "File path to create"},
        "content": {"type": "string", "description": "File content (can be empty string)"},
    }
)
def create_file(path: str, content: str = "") -> str:
    from control.files import create_file as _create
    return _create(path, content)


@tool(
    description="Delete a file or directory. Only use when the user explicitly asks to delete something.",
    parameters={
        "path": {"type": "string", "description": "File or directory path to delete"},
    }
)
def delete_file(path: str) -> str:
    from control.files import delete_file as _delete
    return _delete(path)


@tool(
    description="Move or rename a file or directory.",
    parameters={
        "src": {"type": "string", "description": "Source path"},
        "dst": {"type": "string", "description": "Destination path"},
    }
)
def move_file(src: str, dst: str) -> str:
    from control.files import move_file as _move
    return _move(src, dst)


@tool(
    description="List files and folders in a directory.",
    parameters={
        "path": {"type": "string", "description": "Directory path (default: home directory)"},
    }
)
def list_directory(path: str = ".") -> str:
    from control.files import list_directory as _list
    return _list(path)


@tool(
    description="Create a new directory (and all parent directories needed).",
    parameters={
        "path": {"type": "string", "description": "Directory path to create"},
    }
)
def make_directory(path: str) -> str:
    from control.files import make_directory as _mkdir
    return _mkdir(path)
