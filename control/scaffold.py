"""
Project scaffolding engine — creates full project structures from a single call.
Supports: React, Next.js, Vue, Svelte, plain HTML, Flask, FastAPI, Express, Django, Expo, Python CLI
"""
import os
import subprocess
import shutil
from pathlib import Path


def _run(cmd: str, cwd: str, timeout: int = 120) -> tuple[bool, str]:
    """Run a shell command, return (success, output)."""
    try:
        result = subprocess.run(
            cmd, shell=True, capture_output=True, text=True,
            timeout=timeout, cwd=cwd, env=os.environ.copy()
        )
        out = (result.stdout + result.stderr).strip()
        return result.returncode == 0, out
    except subprocess.TimeoutExpired:
        return False, f"Command timed out after {timeout}s: {cmd}"
    except Exception as e:
        return False, str(e)


def _expand(path: str) -> str:
    return str(Path(os.path.expanduser(path)).resolve())


def _write(path: str, content: str):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)


# ── TEMPLATE GENERATORS ──────────────────────────────────────────────────────

def _scaffold_plain_html(root: str, name: str) -> list[str]:
    _write(f"{root}/index.html", f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>{name}</title>
  <link rel="stylesheet" href="style.css" />
</head>
<body>
  <div id="app">
    <h1>{name}</h1>
  </div>
  <script src="script.js"></script>
</body>
</html>
""")
    _write(f"{root}/style.css", """* { box-sizing: border-box; margin: 0; padding: 0; }
body { font-family: system-ui, sans-serif; background: #0a0a0a; color: #e0e0e0; min-height: 100vh; display: flex; align-items: center; justify-content: center; }
h1 { font-size: 2rem; font-weight: 600; }
""")
    _write(f"{root}/script.js", "// main\nconsole.log('ready');\n")
    return []  # no install needed


def _scaffold_flask(root: str, name: str) -> list[str]:
    _write(f"{root}/app.py", f"""from flask import Flask, render_template, jsonify

app = Flask(__name__)

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/api/hello")
def hello():
    return jsonify({{"message": "Hello from {name}"}})

if __name__ == "__main__":
    app.run(debug=True, port=5000)
""")
    _write(f"{root}/requirements.txt", "flask\nflask-cors\n")
    _write(f"{root}/templates/index.html", f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <title>{name}</title>
  <style>
    body {{ font-family: system-ui, sans-serif; background: #0a0a0a; color: #e0e0e0; display: flex; align-items: center; justify-content: center; min-height: 100vh; margin: 0; }}
    h1 {{ font-size: 2rem; }}
  </style>
</head>
<body>
  <h1>{name}</h1>
  <script>fetch('/api/hello').then(r=>r.json()).then(d=>console.log(d))</script>
</body>
</html>
""")
    _write(f"{root}/static/.gitkeep", "")
    return ["pip3 install -r requirements.txt"]


def _scaffold_fastapi(root: str, name: str) -> list[str]:
    _write(f"{root}/main.py", f"""from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="{name}")

app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

@app.get("/")
def root():
    return {{"message": "Welcome to {name}", "status": "ok"}}

@app.get("/health")
def health():
    return {{"status": "healthy"}}
""")
    _write(f"{root}/requirements.txt", "fastapi\nuvicorn[standard]\nhttpx\n")
    return ["pip3 install -r requirements.txt"]


def _scaffold_express(root: str, name: str) -> list[str]:
    import json
    pkg = {
        "name": name.lower().replace(" ", "-"),
        "version": "1.0.0",
        "main": "index.js",
        "scripts": {"start": "node index.js", "dev": "nodemon index.js"},
        "dependencies": {"express": "^4.18.0", "cors": "^2.8.5"},
        "devDependencies": {"nodemon": "^3.0.0"}
    }
    _write(f"{root}/package.json", json.dumps(pkg, indent=2) + "\n")
    _write(f"{root}/index.js", f"""const express = require('express');
const cors = require('cors');

const app = express();
const PORT = process.env.PORT || 3000;

app.use(cors());
app.use(express.json());

app.get('/', (req, res) => {{
  res.json({{ message: 'Welcome to {name}', status: 'ok' }});
}});

app.listen(PORT, () => console.log(`{name} running on http://localhost:${{PORT}}`));
""")
    _write(f"{root}/.env", "PORT=3000\n")
    _write(f"{root}/.gitignore", "node_modules/\n.env\n")
    return ["npm install"]


def _scaffold_django(root: str, name: str) -> list[str]:
    safe = name.lower().replace(" ", "_").replace("-", "_")
    _write(f"{root}/requirements.txt", "django\ndjango-cors-headers\n")
    return [
        "pip3 install -r requirements.txt",
        f"django-admin startproject {safe} .",
        f"python manage.py startapp core",
    ]


def _scaffold_python_cli(root: str, name: str) -> list[str]:
    safe = name.lower().replace(" ", "_").replace("-", "_")
    _write(f"{root}/main.py", f"""#!/usr/bin/env python3
\"\"\"
{name} — command line tool
\"\"\"
import argparse


def main():
    parser = argparse.ArgumentParser(description="{name}")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")
    args = parser.parse_args()

    if args.verbose:
        print(f"[{name}] starting")

    print("Hello from {name}")


if __name__ == "__main__":
    main()
""")
    _write(f"{root}/requirements.txt", "# add dependencies here\n")
    _write(f"{root}/.gitignore", "__pycache__/\n*.pyc\n.env\nvenv/\n")
    return []


# ── CLI-BASED SCAFFOLDERS ────────────────────────────────────────────────────

CLI_SCAFFOLDERS = {
    "react":   "npm create vite@latest {name} -- --template react",
    "vue":     "npm create vite@latest {name} -- --template vue",
    "svelte":  "npm create vite@latest {name} -- --template svelte",
    "nextjs":  "npx create-next-app@latest {name} --ts --tailwind --no-eslint --app --no-src-dir --import-alias \"@/*\" --no-git",
    "expo":    "npx create-expo-app@latest {name}",
    "react_native": "npx create-expo-app@latest {name}",
}

MANUAL_SCAFFOLDERS = {
    "html":       _scaffold_plain_html,
    "plain_html": _scaffold_plain_html,
    "static":     _scaffold_plain_html,
    "flask":      _scaffold_flask,
    "fastapi":    _scaffold_fastapi,
    "express":    _scaffold_express,
    "django":     _scaffold_django,
    "python_cli": _scaffold_python_cli,
    "cli":        _scaffold_python_cli,
    "script":     _scaffold_python_cli,
}

DEV_COMMANDS = {
    "react":    "npm run dev",
    "vue":      "npm run dev",
    "svelte":   "npm run dev",
    "nextjs":   "npm run dev",
    "flask":    "python app.py",
    "fastapi":  "uvicorn main:app --reload",
    "express":  "npm run dev",
    "django":   "python manage.py runserver",
    "expo":     "npx expo start",
    "react_native": "npx expo start",
    "html":     None,  # just open in browser
    "plain_html": None,
    "python_cli": "python main.py",
}

DEFAULT_PORTS = {
    "react":    5173,
    "vue":      5173,
    "svelte":   5173,
    "nextjs":   3000,
    "flask":    5000,
    "fastapi":  8000,
    "express":  3000,
    "django":   8000,
    "expo":     None,
}


def scaffold_project(type: str, name: str, path: str = "~/Desktop", features: list = None) -> str:
    """
    Create a full project. Returns a status report with next steps.
    type: react | nextjs | vue | svelte | html | flask | fastapi | express | django | expo | python_cli
    name: project name
    path: parent directory (project folder created inside)
    features: optional list of extras (e.g. ['typescript', 'tailwind'])
    """
    t = type.lower().strip().replace("-", "_").replace(".", "")
    if t == "next":
        t = "nextjs"
    if t in ("node", "nodejs"):
        t = "express"
    if t in ("py", "python"):
        t = "python_cli"
    if t in ("rn",):
        t = "react_native"

    parent = _expand(path)
    if not os.path.isdir(parent):
        try:
            os.makedirs(parent, exist_ok=True)
        except Exception as e:
            return f"Cannot create parent directory {parent}: {e}"

    safe_name = name.replace(" ", "-")
    root = os.path.join(parent, safe_name)

    if os.path.exists(root):
        return f"Directory already exists: {root}. Choose a different name or path."

    steps = []
    errors = []

    # ── CLI-based scaffold (React, Next, Vue, Svelte, Expo) ──────────────────
    if t in CLI_SCAFFOLDERS:
        cmd_template = CLI_SCAFFOLDERS[t]
        cmd = cmd_template.format(name=safe_name)
        steps.append(f"Running: {cmd}")
        ok, out = _run(cmd, cwd=parent, timeout=180)
        if not ok:
            return f"Scaffold failed.\n{out}"
        if not os.path.isdir(root):
            return f"Scaffold command ran but project directory not created at {root}.\n{out}"
        steps.append(f"Project created at {root}")

        # Install dependencies
        steps.append("Installing dependencies...")
        ok, out = _run("npm install", cwd=root, timeout=120)
        if not ok:
            errors.append(f"npm install warning: {out[:300]}")
        else:
            steps.append("Dependencies installed.")

    # ── Manual scaffold ──────────────────────────────────────────────────────
    elif t in MANUAL_SCAFFOLDERS:
        try:
            os.makedirs(root, exist_ok=True)
        except Exception as e:
            return f"Cannot create project directory: {e}"

        fn = MANUAL_SCAFFOLDERS[t]
        install_cmds = fn(root, name)
        steps.append(f"Project files created at {root}")

        for cmd in install_cmds:
            steps.append(f"Running: {cmd}")
            ok, out = _run(cmd, cwd=root, timeout=120)
            if not ok:
                errors.append(f"{cmd} failed: {out[:300]}")
            else:
                steps.append(f"  ✓ {cmd}")

    else:
        supported = sorted(set(list(CLI_SCAFFOLDERS.keys()) + list(MANUAL_SCAFFOLDERS.keys())))
        return f"Unknown project type '{type}'. Supported: {', '.join(supported)}"

    # ── Git init ─────────────────────────────────────────────────────────────
    if shutil.which("git"):
        _run("git init", cwd=root)
        _write(f"{root}/.gitignore", _default_gitignore(t))
        _run("git add -A && git commit -m 'initial scaffold'", cwd=root)
        steps.append("Git repo initialized with initial commit.")

    # ── Summary ──────────────────────────────────────────────────────────────
    dev_cmd = DEV_COMMANDS.get(t)
    port = DEFAULT_PORTS.get(t)
    url = f"http://localhost:{port}" if port else None

    summary = [f"Project '{name}' ({type}) created at {root}"]
    summary.extend(steps)
    if errors:
        summary.append("Warnings:")
        summary.extend(f"  - {e}" for e in errors)
    if dev_cmd:
        summary.append(f"Start with: cd {root} && {dev_cmd}")
    if url:
        summary.append(f"URL: {url}")
    if t in ("html", "plain_html", "static"):
        summary.append(f"Open: {root}/index.html")

    return "\n".join(summary)


def _default_gitignore(t: str) -> str:
    if t in ("react", "vue", "svelte", "nextjs", "express"):
        return "node_modules/\ndist/\n.next/\n.env\n.env.local\n"
    if t in ("flask", "fastapi", "django", "python_cli", "cli"):
        return "__pycache__/\n*.pyc\n.env\nvenv/\n*.egg-info/\ndist/\n"
    return ".env\n"
