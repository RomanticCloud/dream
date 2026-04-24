---
name: dream
description: Run a script-controlled workflow for general creative writing projects, with the execution path delegated to dream_orchestrator.py.
compatibility: opencode
metadata:
  language: zh-CN
  domain: fiction
  genre: general
  mode: interactive-workflow
---

## When to use

Use this skill when the user wants to create, continue, plan, draft, revise, validate, or export a creative writing project, and the workflow should be controlled by scripts instead of freeform model decisions.

## Hard rules

- **所有面向用户的输出必须使用中文，包括提问、选项、报告和提示。**
- If the user says `停止`, `退出`, `中止`, `cancel`, or `stop`, stop immediately and do not call more tools.
- After this skill is triggered, always call `python3 scripts/dream_orchestrator.py start --json` first unless a valid orchestrator session is already active.
- After every user answer inside the dream workflow, always call `python3 scripts/dream_orchestrator.py answer --session <id> --value "<answer>" --json` before doing anything else.
- Do not decide the next workflow node yourself. Only the orchestrator may decide the next node.
- Do not read a specific project's files until the orchestrator has confirmed the exact project.
- Do not call downstream workflow scripts unless the orchestrator explicitly returns a `run_script` action.

## Execution Contract

The skill is a thin router. The Python orchestrator owns workflow control.

The assistant may only do these actions in this skill:

1. Call `dream_orchestrator.py`
2. Ask the user a structured question when the orchestrator returns `question`
3. Execute a script when the orchestrator returns `run_script`
4. Report a result when the orchestrator returns `report`
5. Stop when the orchestrator returns `done` or the user interrupts

The assistant must not:

- skip nodes
- infer the next step from conversation context
- start project setup directly
- continue writing directly
- ask extra downstream questions that were not requested by the orchestrator

## Orchestrator Protocol

`dream_orchestrator.py` returns JSON with one of these statuses:

- `question`: ask the user exactly the returned question and options
- `run_script`: execute the returned script command
- `report`: tell the user the returned message
- `done`: end the workflow
- `error`: report the error and stop safely unless the orchestrator indicates a retry path

Expected shape:

```json
{
  "status": "question|run_script|report|done|error",
  "session_id": "dream-...",
  "node": "INIT",
  "message": "optional message"
}
```

For `question`, use the Question tool with the returned labels and descriptions only.

For `run_script`, execute the returned command without adding extra workflow logic.

## User Interaction Rules

- When the orchestrator returns `question`, ask only that question.
- Do not paraphrase fixed branch labels into different options.
- If the environment adds custom freeform input, pass the user answer back to the orchestrator unchanged.
- If the orchestrator returns `report`, report it briefly and wait unless another orchestrator call is explicitly required.

## Stop Rules

- Stop immediately on explicit user interruption.
- Stop if the orchestrator returns `done`.
- Stop safely if the orchestrator returns `error` and no retry path is provided.
