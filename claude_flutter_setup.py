#!/usr/bin/env python3
"""
claude-flutter-setup
====================
Sets up Claude Code + Ollama as a full Flutter/Dart mobile development team.

Creates per-project:
  .claude/agents/         — architect, implementer, reviewer, qa_tester
  .claude/commands/       — /sdlc full-loop command
  .claude/CLAUDE.md       — project coding standards
  .claude/CHEATSHEET.md   — quick reference
  flutter_claude.sh       — launch script (sets context length, starts Ollama + Claude)

Usage:
  cd your_flutter_project
  python3 claude_flutter_setup.py

Requirements:
  - Ollama installed and running (https://ollama.com)
  - Claude Code installed (https://claude.ai/code)
  - Python 3.7+

GitHub: https://github.com/yourusername/claude-flutter-setup
"""

import os
import re
import subprocess
import sys
from pathlib import Path

# ── Constants ─────────────────────────────────────────────────────────────────
VERSION = "1.0.0"
DART_MCP_MIN = (3, 9)
DEFAULT_CONTEXT_LENGTH = 20000

ROLE_DESCRIPTIONS = {
    "architect":   "Creates IMPLEMENTATION_PLAN.md before any code is written. Always runs first.",
    "implementer": "Writes production Flutter/Dart code. Only runs after architect approval.",
    "reviewer":    "Read-only code reviewer. Writes findings to REVIEW_REPORT.md. Never edits source.",
    "qa_tester":   "Writes and runs Flutter/Dart tests. Validates implementation against the plan.",
}

ROLE_TOOLS = {
    "architect":   "Read, Glob, Grep, WebSearch",
    "implementer": "Read, Write, Edit, Bash, Glob, Grep",
    "reviewer":    "Read, Glob, Grep, Write",
    "qa_tester":   "Read, Write, Edit, Bash, Glob, Grep",
}

ROLE_DEFAULTS = {
    "architect":   ["qwen2.5-coder", "qwen3", "llama3"],
    "implementer": ["qwen2.5-coder", "qwen3", "granite"],
    "reviewer":    ["qwen2.5-coder", "qwen3", "llama3"],
    "qa_tester":   ["qwen2.5-coder", "qwen3", "llama3"],
}

# Models known to NOT support tool calling via Ollama API
NO_TOOL_SUPPORT = ["deepseek-r1", "deepseek-v", "phi3", "mistral:7b"]

# ── Agent Prompts ─────────────────────────────────────────────────────────────

AGENT_PROMPTS = {
"architect": """You are the Lead Mobile Architect on a Flutter development team.

## Your Role
You run FIRST before any code is written. Produce IMPLEMENTATION_PLAN.md and
wait for explicit human approval before any implementation begins.

## On Every Task
1. Read relevant files (Read, Glob, Grep) to understand the current codebase
2. Read pubspec.yaml to detect state management (BLoC, Riverpod, Provider, GetX, setState)
3. Check for .fvm/ folder — if present, note that `fvm flutter` / `fvm dart` must be used
4. Write IMPLEMENTATION_PLAN.md with:
   - Feature summary
   - Files to create or modify (with reasons)
   - Detected state management pattern
   - ASCII data flow diagram
   - Edge cases and risks
   - Test strategy
5. End every response with: "⏸ Awaiting human approval before implementation begins."

## Hard Rules
- NEVER write implementation code
- NEVER assume state management — always read pubspec.yaml first
- Flag anything touching ios/, android/, pubspec.lock, or *.g.dart as HIGH RISK
- Follow Clean Architecture: separate data, domain, and presentation layers
""",

"implementer": """You are the Senior Flutter Developer on a mobile development team.

## Your Role
Implement features ONLY after IMPLEMENTATION_PLAN.md exists and is approved.

## Before Writing Any Code
1. Confirm IMPLEMENTATION_PLAN.md exists — if missing, STOP and ask for architect first
2. Read pubspec.yaml to detect state management pattern
3. Read files in the affected feature folder to match existing code style

## Coding Standards (Non-negotiable)
- Dart null safety — no `!` force-unwrap without an inline comment explaining why
- No `dynamic` types — always use explicit types
- `const` constructors wherever possible
- All async functions: try/catch with typed errors — never silently swallow exceptions
- Widgets over 50 lines: extract into a separate file
- No business logic inside widget build() methods
- Proper dispose() for all controllers, streams, and AnimationControllers
- File names: snake_case. Classes: PascalCase. Variables/methods: camelCase.
- Add /// doc comments to all public classes and methods

## Folder Structure (if none exists, use feature-first)
lib/features/<feature_name>/
  data/         (repositories, models, data sources)
  domain/       (use cases, entities, repository interfaces)
  presentation/ (widgets, screens, state management)

## FVM Detection
If .fvm/ exists in the project root: use `fvm flutter` and `fvm dart` for all shell commands.

## After Implementation
1. Run: dart format <changed files>  (or fvm dart format)
2. List every file created or modified with a one-line summary
3. Flag anything requiring manual device testing
4. Signal: "✅ Implementation complete. Ready for review."
""",

"reviewer": """You are the Senior Code Reviewer on a mobile development team.
You are STRICTLY READ-ONLY — never edit source files. You may only write to REVIEW_REPORT.md.

## Review Checklist (check every changed file)
- [ ] No `!` force-unwraps without justification comment
- [ ] No `dynamic` types
- [ ] Proper error handling on all async calls
- [ ] Widget tree depth ≤ 3 levels (deeper = should be extracted)
- [ ] Missing `const` constructors?
- [ ] No business logic in build() methods
- [ ] No hardcoded strings (use constants or localization)
- [ ] dispose() called for all controllers, streams, and animations
- [ ] State management used consistently with the rest of the project
- [ ] Naming: snake_case files, PascalCase classes, camelCase variables
- [ ] Doc comments on all public APIs

## Output: Write REVIEW_REPORT.md
```
# Code Review Report
**Date:** <date>
**Feature:** <feature name>

## Critical Issues (must fix before merge)
1. [FILE:LINE] Description

## Warnings (should fix)
1. [FILE:LINE] Description

## Suggestions (optional improvements)
1. [FILE:LINE] Description

## Verdict
[ ] APPROVED — no critical issues
[ ] CHANGES REQUESTED — see critical issues above
```

- If APPROVED: "✅ Code approved. Ready for QA."
- If CHANGES REQUESTED: "🔄 Critical issues found. See REVIEW_REPORT.md."
""",

"qa_tester": """You are the QA Engineer and Test Automation Lead on a mobile development team.

## Your Role
Write, review, and execute Flutter/Dart tests. Validate that implementation matches IMPLEMENTATION_PLAN.md.

## Test Strategy (always in this order)
1. Unit tests — pure Dart logic, repositories, use cases → test/
2. Widget tests — UI components in isolation → test/widgets/
3. Integration tests — full user flows if specified → integration_test/

## Before Writing Tests
1. Read IMPLEMENTATION_PLAN.md for expected behavior
2. Read implementation files to understand actual contracts
3. Check pubspec.yaml: use mockito or mocktail — match what is already used

## Standards
- Use flutter_test for all tests
- Every public method: at least one happy-path + one error-path test
- Descriptive names: test('should return error when network is unavailable', ...)
- Group related tests: group('RepositoryName', () { ... })
- Never use sleep() — use tester.pump() or tester.pumpAndSettle()

## FVM Detection
If .fvm/ exists in the project root: run `fvm flutter test` instead of `flutter test`

## After Running Tests
Report: total / passed / failed / skipped
- All pass: "✅ All tests passing. Feature is ready for final approval."
- Failures: list each failure with file, test name, and error message.
""",
}

# ── CLAUDE.md ─────────────────────────────────────────────────────────────────

CLAUDE_MD = """# Claude Code — Flutter Project Rules

## SDLC Workflow (always follow this order)
1. architect → writes IMPLEMENTATION_PLAN.md → human approves
2. implementer → executes the plan
3. reviewer → writes REVIEW_REPORT.md → approve or loop back to implementer
4. qa_tester → writes + runs tests → loop until passing

Use /sdlc "<feature description>" to run the full loop automatically.
Never write code without an approved IMPLEMENTATION_PLAN.md.

## Project Detection (run at start of every session)
- Read pubspec.yaml to detect Flutter version, state management, key packages
- Check for .fvm/fvm_config.json: if present, use `fvm flutter` and `fvm dart` for ALL commands
- Check for analysis_options.yaml: follow its lint rules strictly

## Dart/Flutter Coding Standards
- Null safety: no `!` force-unwrap without an inline comment
- No `dynamic` types
- `const` constructors everywhere possible
- All async code: try/catch with typed errors
- Widgets over 50 lines → extract to a separate file
- No business logic in widget build() methods
- Proper dispose() for all controllers, streams, and AnimationControllers

## Clean Architecture
- Feature-first: lib/features/<name>/{data,domain,presentation}/
- Never mix data, domain, and presentation layers

## Off-Limits Without Explicit Permission
- pubspec.lock — never manually edit
- *.g.dart, *.freezed.dart — regenerate with build_runner, never hand-edit
- ios/, android/ native folders — flag as HIGH RISK before touching

## Context Management
- Load only relevant files into context — do not dump entire project
- Use /compact after each major agent handoff
- Run agents sequentially, never in parallel
"""

# ── /sdlc command ─────────────────────────────────────────────────────────────

SDLC_COMMAND = """---
description: Runs the full SDLC loop — Architect → Implementer → Reviewer → QA — sequentially for the given feature.
---

You are the SDLC Orchestrator. Execute these 4 steps in strict order for the feature: $1
Wait for each subagent to fully complete before starting the next one. Never run two agents at once.

# STEP 1 — PLAN
Call the `architect` subagent with: "Create an implementation plan for: $1"
Wait until IMPLEMENTATION_PLAN.md is written.
Then PAUSE and ask the user: "📋 Plan ready. Do you approve? (yes / provide feedback)"
Do not proceed until the user explicitly approves.

# STEP 2 — IMPLEMENT
Call the `implementer` subagent with: "Execute the approved IMPLEMENTATION_PLAN.md"
Wait until implementation is complete and all files are written.

# STEP 3 — REVIEW LOOP
Call the `reviewer` subagent with: "Review the implementation and write REVIEW_REPORT.md"
Wait for REVIEW_REPORT.md.
- If verdict is APPROVED → proceed to Step 4
- If verdict is CHANGES REQUESTED → call `implementer` with: "Fix the issues in REVIEW_REPORT.md"
  then repeat Step 3. Loop until APPROVED.

# STEP 4 — TEST LOOP
Call the `qa_tester` subagent with: "Write and run tests for this feature"
Wait for test results.
- If all pass → report: "✅ SDLC Complete. Feature is implemented, reviewed, and tested."
- If tests fail → call `implementer` with: "Fix the failing tests reported by qa_tester"
  then repeat Step 4. Loop until all tests pass.
"""

# ── Cheatsheet ────────────────────────────────────────────────────────────────

def build_cheatsheet(roles, project_name, context_length):
    return f"""# Claude Code Flutter Cheatsheet
> Project: {project_name}

## Your Dev Team

| Agent | Model | Role |
|---|---|---|
| `architect` | {roles['architect']} | Plans → IMPLEMENTATION_PLAN.md, waits for approval |
| `implementer` | {roles['implementer']} | Writes production Flutter/Dart code |
| `reviewer` | {roles['reviewer']} | Read-only review → REVIEW_REPORT.md |
| `qa_tester` | {roles['qa_tester']} | Writes + runs Flutter tests |

---

## Workflows

### Quick Task (no SDLC overhead)
Just type your request directly in Claude Code.
Best for: small bug fixes, renaming, simple widget tweaks.

### Full SDLC Loop (recommended for features)
```
/sdlc "describe your feature here"
```
Automatically: Plan → Approve → Implement → Review → Test

### Manual Step-by-Step
```
"Use the architect subagent to plan: <feature>"
→ read IMPLEMENTATION_PLAN.md, reply: "Approved"
"Use the implementer subagent to execute the plan"
"Use the reviewer subagent to review the implementation"
→ read REVIEW_REPORT.md
"Use the qa_tester subagent to write and run tests"
```

---

## Slash Commands

| Command | Purpose |
|---|---|
| `/sdlc "<feature>"` | Full automated SDLC loop |
| `/init` | Scan project and generate CLAUDE.md (run once per project) |
| `/memory` | Edit persistent instructions |
| `/compact` | Summarise context — run after every major agent handoff |
| `/clear` | Wipe context for a fresh task |
| `/model <name>` | Switch model mid-session |
| `/mcp` | Check Dart MCP server connection |
| `/cost` | Show token usage |
| `/doctor` | Diagnose config issues |

---

## SDLC Files

| File | Created by | Purpose |
|---|---|---|
| `IMPLEMENTATION_PLAN.md` | architect | Blueprint — approve before code is written |
| `REVIEW_REPORT.md` | reviewer | Issues list — drives fix iterations |
| `.claude/CLAUDE.md` | setup + /init | Coding standards loaded every session |

---

## Launch

```bash
./flutter_claude.sh              # start from project root
```
Ollama context: {context_length} tokens

---

## MCP (Dart/Flutter Tools)
Active if Dart >= 3.9 / Flutter >= 3.35. Register with:
```bash
claude mcp add --transport stdio dart -- dart mcp-server
```
Provides: error analysis, pub.dev search, symbol resolution, dart format, app introspection.

---

## Tips
- Always use /compact after each major agent handoff (saves token budget)
- Run agents sequentially — never ask two agents to work at the same time
- Use /sdlc for new features, direct prompts for small tasks
- FVM projects: agents auto-detect .fvm/ and use `fvm flutter` commands
"""

# ── Helpers ───────────────────────────────────────────────────────────────────

def run(cmd):
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    return result.stdout.strip(), result.returncode

def get_installed_models():
    out, code = run("ollama list")
    if code != 0:
        return []
    models = []
    for line in out.splitlines()[1:]:
        parts = line.split()
        if parts:
            models.append(parts[0])
    return models

def get_dart_version():
    for cmd in ["dart --version 2>&1", "fvm dart --version 2>&1"]:
        out, _ = run(cmd)
        match = re.search(r"(\d+)\.(\d+)", out)
        if match:
            return int(match.group(1)), int(match.group(2))
    return (0, 0)

def is_fvm_project(project_dir):
    return (project_dir / ".fvm").exists()

def has_flutter_pubspec(project_dir):
    pubspec = project_dir / "pubspec.yaml"
    if not pubspec.exists():
        return False
    return "flutter" in pubspec.read_text()

def warn_if_no_tools(model_name):
    for bad in NO_TOOL_SUPPORT:
        if bad in model_name:
            print(f"  ⚠️  Warning: '{model_name}' may not support tool calling via Ollama.")
            print(f"     This will cause 400 errors in agents. Consider a qwen2.5-coder or qwen3 model.")
            return

def suggest_default(role, installed):
    preferred = ROLE_DEFAULTS[role]
    for pref in preferred:
        for m in installed:
            if pref in m:
                return m
    return installed[0] if installed else "qwen2.5-coder:3b"

def pick_model(role, installed):
    suggested = suggest_default(role, installed)
    print(f"\n  [{role.upper()}]")
    print(f"  Suggested: {suggested}")
    print(f"  Installed models:")
    for i, m in enumerate(installed):
        flag = " ⚠️  (may not support tools)" if any(b in m for b in NO_TOOL_SUPPORT) else ""
        print(f"    [{i}] {m}{flag}")
    choice = input(f"  Select number or press Enter for '{suggested}': ").strip()
    if not choice:
        return suggested
    try:
        selected = installed[int(choice)]
        warn_if_no_tools(selected)
        return selected
    except (ValueError, IndexError):
        print(f"  Invalid — using: {suggested}")
        return suggested

# ── Writers ───────────────────────────────────────────────────────────────────

def write_agents(claude_dir, roles):
    agents_dir = claude_dir / "agents"
    agents_dir.mkdir(parents=True, exist_ok=True)
    for name, model in roles.items():
        content = f"""---
name: {name}
description: {ROLE_DESCRIPTIONS[name]}
tools: {ROLE_TOOLS[name]}
model: {model}
---

{AGENT_PROMPTS[name].strip()}
"""
        (agents_dir / f"{name}.md").write_text(content)
        print(f"  ✅ .claude/agents/{name}.md  ({model})")

def write_sdlc_command(claude_dir):
    commands_dir = claude_dir / "commands"
    commands_dir.mkdir(parents=True, exist_ok=True)
    (commands_dir / "sdlc.md").write_text(SDLC_COMMAND.strip())
    print(f"  ✅ .claude/commands/sdlc.md")

def write_claude_md(claude_dir):
    claude_dir.mkdir(parents=True, exist_ok=True)
    (claude_dir / "CLAUDE.md").write_text(CLAUDE_MD.strip())
    print(f"  ✅ .claude/CLAUDE.md")

def write_cheatsheet(claude_dir, roles, project_name, context_length):
    content = build_cheatsheet(roles, project_name, context_length)
    (claude_dir / "CHEATSHEET.md").write_text(content.strip())
    print(f"  ✅ .claude/CHEATSHEET.md")

def write_launch_script(project_dir, roles, context_length, use_fvm):
    flutter_cmd = "fvm flutter" if use_fvm else "flutter"
    dart_cmd = "fvm dart" if use_fvm else "dart"
    default_model = roles["implementer"]

    content = f"""#!/bin/bash
# flutter_claude.sh — Launch Claude Code + Ollama for this project
# Generated by claude_flutter_setup.py v{VERSION}
# Run from project root: ./flutter_claude.sh

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
DEFAULT_MODEL="{default_model}"
CONTEXT_LENGTH={context_length}
FLUTTER_CMD="{flutter_cmd}"
DART_CMD="{dart_cmd}"

# Restart Ollama with correct context length
echo "🦙 Starting Ollama (context: $CONTEXT_LENGTH tokens)..."
pkill -f "ollama serve" 2>/dev/null
sleep 1
OLLAMA_CONTEXT_LENGTH=$CONTEXT_LENGTH ollama serve &
OLLAMA_PID=$!
sleep 2

cd "$PROJECT_DIR"
echo "📁 Project: $PROJECT_DIR"
echo "🔧 Flutter: $FLUTTER_CMD | Dart: $DART_CMD"
echo "🤖 Model: $DEFAULT_MODEL"
echo ""
echo "   Type /init if first time in this project"
echo "   Type /sdlc \\"your feature\\" for the full SDLC loop"
echo ""

ollama run "$DEFAULT_MODEL" --keepalive 60m &>/dev/null &

ANTHROPIC_BASE_URL=http://localhost:11434 \\
ANTHROPIC_AUTH_TOKEN=ollama \\
claude --model "$DEFAULT_MODEL"

echo ""
echo "👋 Exited Claude Code. Stopping Ollama..."
kill $OLLAMA_PID 2>/dev/null
"""
    launch_path = project_dir / "flutter_claude.sh"
    launch_path.write_text(content)
    launch_path.chmod(0o755)
    print(f"  ✅ flutter_claude.sh")

def register_mcp():
    version = get_dart_version()
    if version >= DART_MCP_MIN:
        _, code = run("claude mcp add --transport stdio dart -- dart mcp-server")
        if code == 0:
            print(f"  ✅ Dart MCP server registered (Dart {version[0]}.{version[1]})")
        else:
            print(f"  ⚠️  Could not auto-register. Run manually:")
            print(f"      claude mcp add --transport stdio dart -- dart mcp-server")
    else:
        v = f"{version[0]}.{version[1]}" if version != (0,0) else "unknown"
        print(f"  ⚠️  Dart {v} detected — MCP requires Dart 3.9+. Skipping.")
        print(f"      When ready: claude mcp add --transport stdio dart -- dart mcp-server")

# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    project_dir = Path.cwd()
    claude_dir = project_dir / ".claude"
    project_name = project_dir.name

    print(f"\n🚀 Claude Code Flutter Dev Team Setup v{VERSION}")
    print("=" * 52)
    print(f"   Project: {project_name}")
    print(f"   Path:    {project_dir}")

    if not has_flutter_pubspec(project_dir):
        print("\n⚠️  No Flutter pubspec.yaml found in current directory.")
        proceed = input("   Continue anyway? (y/N): ").strip().lower()
        if proceed != "y":
            print("   Exiting. Run from a Flutter project root.")
            sys.exit(0)

    use_fvm = is_fvm_project(project_dir)
    if use_fvm:
        print("   FVM: detected — launch script will use `fvm flutter`")

    # Model selection
    installed = get_installed_models()
    if not installed:
        print("\n⚠️  No Ollama models detected. Is Ollama running?")
        print("   Start with: ollama serve")
        print("   Continuing with default model names...")
        installed = ["qwen2.5-coder:3b", "qwen2.5-coder:1.5b", "deepseek-r1:1.5b"]

    print(f"\n   {len(installed)} models installed.")
    customize = input("   Customize model assignments? (y/N): ").strip().lower()
    if customize == "y":
        roles = {role: pick_model(role, installed) for role in ROLE_DESCRIPTIONS}
    else:
        roles = {role: suggest_default(role, installed) for role in ROLE_DESCRIPTIONS}
        print("\n   Auto-assigned models:")
        for r, m in roles.items():
            print(f"   {r:12} → {m}")

    # Context length
    print(f"\n   Default Ollama context length: {DEFAULT_CONTEXT_LENGTH} tokens")
    ctx_input = input(f"   Change context length? (Enter to keep {DEFAULT_CONTEXT_LENGTH}): ").strip()
    try:
        context_length = int(ctx_input) if ctx_input else DEFAULT_CONTEXT_LENGTH
    except ValueError:
        context_length = DEFAULT_CONTEXT_LENGTH

    # Write everything
    print("\n[1/6] Writing agents...")
    write_agents(claude_dir, roles)

    print("\n[2/6] Writing /sdlc command...")
    write_sdlc_command(claude_dir)

    print("\n[3/6] Writing CLAUDE.md...")
    write_claude_md(claude_dir)

    print("\n[4/6] Writing cheatsheet...")
    write_cheatsheet(claude_dir, roles, project_name, context_length)

    print("\n[5/6] Writing launch script...")
    write_launch_script(project_dir, roles, context_length, use_fvm)

    print("\n[6/6] Checking Dart MCP compatibility...")
    register_mcp()

    print("\n" + "=" * 52)
    print("✅ Setup complete!\n")
    print("Next steps:")
    print("  ./flutter_claude.sh          ← start Ollama + Claude Code")
    print("  /init                        ← run once inside Claude Code")
    print("  /sdlc \"your feature\"         ← full SDLC loop")
    print(f"\nCheatsheet: .claude/CHEATSHEET.md")

if __name__ == "__main__":
    main()
