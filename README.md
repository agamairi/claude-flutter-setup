# claude-flutter-setup

A one-command setup that turns Claude Code + Ollama into a full Flutter/Dart mobile development team — running entirely locally, for free.

---

## What It Does

Installs a 4-agent AI dev team into your Flutter project that follows a proper Software Development Life Cycle (SDLC):

| Agent | Role |
|---|---|
| **Architect** | Writes an implementation plan and waits for your approval before any code is written |
| **Implementer** | Writes production-quality Flutter/Dart code following clean code principles |
| **Reviewer** | Reviews code for bugs, null safety, and best practices — outputs `REVIEW_REPORT.md` |
| **QA Tester** | Writes and runs Flutter/Dart tests, loops back if tests fail |

You can run each agent manually, or trigger the entire pipeline with one command:

```
/sdlc "Add a bottom navigation bar with Home, Search, and Profile tabs"
```

---

## Requirements

- [Ollama](https://ollama.com) installed and running
- [Claude Code](https://claude.ai/code) installed (`npm install -g @anthropic-ai/claude-code`)
- At least one Ollama model pulled — recommended:
  ```bash
  ollama pull qwen2.5-coder:3b
  ollama pull qwen2.5-coder:1.5b
  ```
- Python 3.7+
- Flutter project to run it in

> ⚠️ **Model note:** `deepseek-r1` does not support tool calling via the Ollama API and will cause errors in agent roles. Use `qwen2.5-coder` or `qwen3` series models for agents.

---

## Installation

```bash
# 1. Download the script into your Flutter project root
curl -O https://raw.githubusercontent.com/yourusername/claude-flutter-setup/main/claude_flutter_setup.py

# 2. Run it
python3 claude_flutter_setup.py

# 3. Start coding
./flutter_claude.sh
```

---

## What Gets Created

```
your_flutter_project/
├── flutter_claude.sh              ← launch script (starts Ollama + Claude Code)
└── .claude/
    ├── CLAUDE.md                  ← project coding standards (loaded every session)
    ├── CHEATSHEET.md              ← quick reference for commands and workflow
    ├── agents/
    │   ├── architect.md
    │   ├── implementer.md
    │   ├── reviewer.md
    │   └── qa_tester.md
    └── commands/
        └── sdlc.md                ← /sdlc full-loop command
```

---

## Usage

### Start a session
```bash
./flutter_claude.sh
```
This restarts Ollama with the correct context length, sets up the API connection, and launches Claude Code.

### First time in a project
```
/init
```
Run this once inside Claude Code to scan your project and generate a project-level `CLAUDE.md`.

### Trigger the full SDLC loop
```
/sdlc "describe the feature you want to build"
```

The loop will:
1. Have the architect write `IMPLEMENTATION_PLAN.md`
2. **Pause and ask for your approval**
3. Implement the feature
4. Review and loop back if issues found
5. Write and run tests, loop back if tests fail
6. Report completion ✅

### Manual agent calls
```
"Use the architect subagent to plan: <feature>"
"Use the implementer subagent to execute the plan"
"Use the reviewer subagent to review the implementation"
"Use the qa_tester subagent to write and run tests"
```

### Quick tasks (no SDLC overhead)
Just type directly — best for small fixes, renames, and simple widget changes.

---

## RAM & Performance Notes

Tested on M2 MacBook Air 8GB. Key tips:
- Agents run **sequentially** — never in parallel (one model in memory at a time)
- Use `/compact` after each major agent handoff to free up context budget
- Default context length is 20,000 tokens (configurable during setup)

---

## Dart MCP Server

The setup script automatically registers the [official Dart/Flutter MCP server](https://docs.flutter.dev/ai/mcp-server) if your project is on Dart 3.9+ / Flutter 3.35+.

This gives agents live access to:
- Project error analysis
- Dart symbol resolution and docs
- pub.dev package search
- `dart format`
- Running app introspection (requires `flutter run --debug`)

For FVM-managed projects on older Flutter versions, MCP registration is skipped automatically.

---

## License

[MIT](LICENSE)
