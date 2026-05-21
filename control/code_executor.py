"""
Code execution engine — runs any language in a sandboxed subprocess.
Supports: Python, JavaScript/Node, Bash, TypeScript, Go, Rust, Ruby, SQL, R, Swift, Kotlin, C, C++
"""
import os
import subprocess
import tempfile
import shutil
from pathlib import Path

LANGUAGE_CONFIG = {
    "python":     {"ext": ".py",    "cmd": ["python3"],           "compile": False},
    "python3":    {"ext": ".py",    "cmd": ["python3"],           "compile": False},
    "py":         {"ext": ".py",    "cmd": ["python3"],           "compile": False},
    "javascript": {"ext": ".js",    "cmd": ["node"],              "compile": False},
    "js":         {"ext": ".js",    "cmd": ["node"],              "compile": False},
    "node":       {"ext": ".js",    "cmd": ["node"],              "compile": False},
    "typescript": {"ext": ".ts",    "cmd": ["npx", "--yes", "ts-node"], "compile": False},
    "ts":         {"ext": ".ts",    "cmd": ["npx", "--yes", "ts-node"], "compile": False},
    "bash":       {"ext": ".sh",    "cmd": ["bash"],              "compile": False},
    "sh":         {"ext": ".sh",    "cmd": ["bash"],              "compile": False},
    "shell":      {"ext": ".sh",    "cmd": ["bash"],              "compile": False},
    "ruby":       {"ext": ".rb",    "cmd": ["ruby"],              "compile": False},
    "rb":         {"ext": ".rb",    "cmd": ["ruby"],              "compile": False},
    "r":          {"ext": ".R",     "cmd": ["Rscript"],           "compile": False},
    "swift":      {"ext": ".swift", "cmd": ["swift"],             "compile": False},
    "go":         {"ext": ".go",    "cmd": ["go", "run"],         "compile": False},
    "sql":        {"ext": ".sql",   "cmd": None,                  "compile": False, "special": "sqlite"},
    "rust":       {"ext": ".rs",    "cmd": None,                  "compile": True,  "special": "rust"},
    "rs":         {"ext": ".rs",    "cmd": None,                  "compile": True,  "special": "rust"},
    "c":          {"ext": ".c",     "cmd": None,                  "compile": True,  "special": "c"},
    "cpp":        {"ext": ".cpp",   "cmd": None,                  "compile": True,  "special": "cpp"},
    "c++":        {"ext": ".cpp",   "cmd": None,                  "compile": True,  "special": "cpp"},
}


def _check_runtime(lang_key: str) -> tuple[bool, str]:
    """Check if the required runtime is installed."""
    cfg = LANGUAGE_CONFIG.get(lang_key)
    if not cfg:
        return False, f"Language '{lang_key}' not supported."
    special = cfg.get("special")
    if special == "sqlite":
        return True, ""
    if special == "rust":
        return bool(shutil.which("rustc")), "rustc not found. Install Rust: https://rustup.rs"
    if special == "c":
        return bool(shutil.which("gcc")), "gcc not found."
    if special == "cpp":
        ok = bool(shutil.which("g++")) or bool(shutil.which("clang++"))
        return ok, "g++ or clang++ not found."
    cmd = cfg["cmd"][0]
    if cmd == "npx":
        return bool(shutil.which("node")), "Node.js not found."
    return bool(shutil.which(cmd)), f"{cmd} not found."


def execute_code(language: str, code: str, timeout: int = 30, cwd: str = None) -> dict:
    """
    Execute code in the given language.
    Returns: {"stdout": str, "stderr": str, "exit_code": int, "success": bool, "error": str}
    """
    lang_key = language.lower().strip()
    cfg = LANGUAGE_CONFIG.get(lang_key)
    if not cfg:
        supported = sorted({k for k in LANGUAGE_CONFIG if len(k) > 2})
        return {"stdout": "", "stderr": "", "exit_code": -1, "success": False,
                "error": f"Language '{language}' not supported. Supported: {', '.join(supported)}"}

    ok, msg = _check_runtime(lang_key)
    if not ok:
        return {"stdout": "", "stderr": "", "exit_code": -1, "success": False, "error": msg}

    work_dir = cwd or tempfile.mkdtemp(prefix="jarvis_code_")
    cleanup = cwd is None

    try:
        special = cfg.get("special")
        ext = cfg["ext"]
        code_file = os.path.join(work_dir, f"code{ext}")
        with open(code_file, "w", encoding="utf-8") as f:
            f.write(code)

        env = os.environ.copy()
        env["PYTHONDONTWRITEBYTECODE"] = "1"

        if special == "sqlite":
            result = subprocess.run(
                ["sqlite3", ":memory:"],
                input=code, capture_output=True, text=True, timeout=timeout, env=env
            )
        elif special == "rust":
            bin_path = os.path.join(work_dir, "code_bin")
            compile_result = subprocess.run(
                ["rustc", code_file, "-o", bin_path],
                capture_output=True, text=True, timeout=30, env=env
            )
            if compile_result.returncode != 0:
                return {"stdout": "", "stderr": compile_result.stderr, "exit_code": compile_result.returncode,
                        "success": False, "error": "Compilation failed"}
            result = subprocess.run([bin_path], capture_output=True, text=True, timeout=timeout, env=env)
        elif special == "c":
            bin_path = os.path.join(work_dir, "code_bin")
            compile_result = subprocess.run(
                ["gcc", code_file, "-o", bin_path, "-lm"],
                capture_output=True, text=True, timeout=30, env=env
            )
            if compile_result.returncode != 0:
                return {"stdout": "", "stderr": compile_result.stderr, "exit_code": compile_result.returncode,
                        "success": False, "error": "Compilation failed"}
            result = subprocess.run([bin_path], capture_output=True, text=True, timeout=timeout, env=env)
        elif special == "cpp":
            bin_path = os.path.join(work_dir, "code_bin")
            compiler = shutil.which("g++") or shutil.which("clang++")
            compile_result = subprocess.run(
                [compiler, code_file, "-o", bin_path, "-std=c++17"],
                capture_output=True, text=True, timeout=30, env=env
            )
            if compile_result.returncode != 0:
                return {"stdout": "", "stderr": compile_result.stderr, "exit_code": compile_result.returncode,
                        "success": False, "error": "Compilation failed"}
            result = subprocess.run([bin_path], capture_output=True, text=True, timeout=timeout, env=env)
        else:
            cmd = cfg["cmd"] + [code_file]
            result = subprocess.run(
                cmd, capture_output=True, text=True, timeout=timeout,
                env=env, cwd=work_dir
            )

        return {
            "stdout": result.stdout.strip(),
            "stderr": result.stderr.strip(),
            "exit_code": result.returncode,
            "success": result.returncode == 0,
            "error": "",
        }

    except subprocess.TimeoutExpired:
        return {"stdout": "", "stderr": "", "exit_code": -1, "success": False,
                "error": f"Execution timed out after {timeout}s."}
    except Exception as e:
        return {"stdout": "", "stderr": "", "exit_code": -1, "success": False, "error": str(e)}
    finally:
        if cleanup:
            try:
                shutil.rmtree(work_dir, ignore_errors=True)
            except Exception:
                pass


def run_shell(command: str, cwd: str = None, timeout: int = 30) -> dict:
    """Run a shell command and return output."""
    try:
        work_dir = cwd or os.path.expanduser("~")
        result = subprocess.run(
            command, shell=True, capture_output=True, text=True,
            timeout=timeout, cwd=work_dir, env=os.environ.copy()
        )
        return {
            "stdout": result.stdout.strip(),
            "stderr": result.stderr.strip(),
            "exit_code": result.returncode,
            "success": result.returncode == 0,
            "error": "",
        }
    except subprocess.TimeoutExpired:
        return {"stdout": "", "stderr": "", "exit_code": -1, "success": False,
                "error": f"Command timed out after {timeout}s."}
    except Exception as e:
        return {"stdout": "", "stderr": "", "exit_code": -1, "success": False, "error": str(e)}


def format_execution_result(result: dict, language: str = "") -> str:
    """Format execution result into a clean string for JARVIS to return."""
    if result.get("error"):
        return f"Error: {result['error']}"
    parts = []
    if result["stdout"]:
        parts.append(result["stdout"])
    if result["stderr"]:
        label = "Warnings" if result["success"] else "Errors"
        parts.append(f"{label}:\n{result['stderr']}")
    if not parts:
        exit_code = result.get("exit_code", 0)
        return "Code ran successfully. No output." if exit_code == 0 else f"Exited with code {exit_code}."
    return "\n".join(parts)
