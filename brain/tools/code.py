"""Code and dev tools — code execution, shell, git, scaffold."""
from brain.tools.registry import tool


@tool(
    description="Execute code in any programming language and return the output. Use this whenever the user asks to run code, test something, calculate something with code, or when you write code that should be executed. Supported: python, javascript, bash, typescript, go, rust, ruby, r, swift, c, cpp, sql.",
    parameters={
        "language": {"type": "string", "description": "Programming language: python, javascript, bash, typescript, go, rust, ruby, r, swift, c, cpp, sql"},
        "code":     {"type": "string", "description": "The complete code to execute"},
        "timeout":  {"type": "integer", "description": "Max execution time in seconds (default 30)"},
        "cwd":      {"type": "string", "description": "Working directory path (optional)"},
    },
    risk="red",
)
def execute_code(language: str, code: str, timeout: int = 30, cwd: str = None) -> str:
    from control.code_executor import execute_code_with_healing, format_execution_result
    result = execute_code_with_healing(language=language, code=code, timeout=int(timeout), cwd=cwd)
    return format_execution_result(result, language)


@tool(
    description="Run any shell command on the Mac and return the output. Use for: installing packages, running scripts, git commands, checking system info, npm/pip/brew commands, starting/stopping processes.",
    parameters={
        "command": {"type": "string", "description": "Shell command to run"},
        "cwd":     {"type": "string", "description": "Working directory path (optional)"},
        "timeout": {"type": "integer", "description": "Max time in seconds (default 30)"},
    },
    risk="red",
)
def run_shell(command: str, cwd: str = None, timeout: int = 30) -> str:
    from control.code_executor import run_shell as _run
    result = _run(command=command, cwd=cwd, timeout=int(timeout))
    if result.get("error"):
        return f"Error: {result['error']}"
    out = []
    if result["stdout"]:
        out.append(result["stdout"])
    if result["stderr"]:
        out.append(f"stderr: {result['stderr']}")
    return "\n".join(out) if out else f"Done. Exit code: {result['exit_code']}"


@tool(
    description="Create a complete software project from scratch — folder structure, boilerplate code, dependencies installed, git initialized. Supported types: react, nextjs, vue, svelte, html, flask, fastapi, express, django, expo, python_cli.",
    parameters={
        "type":     {"type": "string", "description": "Project type: react | nextjs | vue | svelte | html | flask | fastapi | express | django | expo | python_cli"},
        "name":     {"type": "string", "description": "Project name (becomes the folder name)"},
        "path":     {"type": "string", "description": "Parent directory to create the project in (default: ~/Desktop)"},
        "features": {"type": "array",  "description": "Optional feature flags e.g. ['typescript', 'tailwind', 'auth']"},
    }
)
def scaffold_project(type: str, name: str, path: str = "~/Desktop", features=None) -> str:
    from control.scaffold import scaffold_project as _scaffold
    return _scaffold(type=type, name=name, path=path, features=features)


@tool(
    description="Show git status of a project — staged, unstaged, untracked files.",
    parameters={
        "path": {"type": "string", "description": "Project directory path (default: current dir)"},
    }
)
def git_status(path: str = ".") -> str:
    from control.git_ops import git_status as _run
    return _run(path)


@tool(
    description="Stage files for commit. Use 'files': '.' to stage everything.",
    parameters={
        "path":  {"type": "string", "description": "Project directory path"},
        "files": {"type": "string", "description": "Files to stage: '.' for all, or specific file paths"},
    }
)
def git_add(path: str, files: str = ".") -> str:
    from control.git_ops import git_add as _run
    return _run(path, files)


@tool(
    description="Commit staged changes with a message.",
    parameters={
        "path":    {"type": "string", "description": "Project directory path"},
        "message": {"type": "string", "description": "Commit message"},
    }
)
def git_commit(path: str, message: str = "update") -> str:
    from control.git_ops import git_commit as _run
    return _run(path, message)


@tool(
    description="Push commits to a remote repository.",
    parameters={
        "path":   {"type": "string", "description": "Project directory path"},
        "remote": {"type": "string", "description": "Remote name (default: origin)"},
        "branch": {"type": "string", "description": "Branch to push (default: current branch)"},
    },
    risk="red",
)
def git_push(path: str, remote: str = "origin", branch: str = "") -> str:
    from control.git_ops import git_push as _run
    return _run(path, remote, branch)


@tool(
    description="Manage git branches — list, create, switch, or delete.",
    parameters={
        "path":   {"type": "string", "description": "Project directory path"},
        "action": {"type": "string", "description": "Action: list, create, switch, or delete"},
        "name":   {"type": "string", "description": "Branch name (required for create/switch/delete)"},
    }
)
def git_branch(path: str, action: str = "list", name: str = "") -> str:
    from control.git_ops import git_branch as _run
    return _run(path, name, action)


@tool(
    description="Show recent commit history for a project.",
    parameters={
        "path": {"type": "string", "description": "Project directory path"},
        "n":    {"type": "integer", "description": "Number of commits to show (default: 10)"},
    }
)
def git_log(path: str, n: int = 10) -> str:
    from control.git_ops import git_log as _run
    return _run(path, n)


@tool(
    description="Show what changed in a project — unstaged by default, or staged if specified.",
    parameters={
        "path":   {"type": "string", "description": "Project directory path"},
        "staged": {"type": "boolean", "description": "Show staged diff instead of unstaged"},
    }
)
def git_diff(path: str, staged: bool = False) -> str:
    from control.git_ops import git_diff as _run
    return _run(path, staged)


@tool(
    description="Clone a git repository to a local directory.",
    parameters={
        "url":  {"type": "string", "description": "Repository URL to clone"},
        "path": {"type": "string", "description": "Directory to clone into (default: ~/Desktop)"},
        "name": {"type": "string", "description": "Local folder name (optional)"},
    }
)
def git_clone(url: str, path: str = "~/Desktop", name: str = "") -> str:
    from control.git_ops import git_clone as _run
    return _run(url, path, name)


@tool(
    description="Initialize a new git repository in a directory.",
    parameters={
        "path": {"type": "string", "description": "Directory to initialize as a git repo"},
    }
)
def git_init(path: str = ".") -> str:
    from control.git_ops import git_init as _run
    return _run(path)


@tool(
    description="Create a GitHub repository and push the local project to it. Requires gh CLI to be authenticated.",
    parameters={
        "name":    {"type": "string", "description": "GitHub repo name"},
        "path":    {"type": "string", "description": "Local project directory to push"},
        "private": {"type": "boolean", "description": "Make repo private (default: true)"},
    }
)
def git_create_github_repo(name: str, path: str = ".", private: bool = True) -> str:
    from control.git_ops import git_create_github_repo as _run
    return _run(name, private, path)
