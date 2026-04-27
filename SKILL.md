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

- **所有面向用户的输出必须使用中文。**
- 用户说 `停止`/`退出`/`中止`/`cancel`/`stop` 时立即停止。
- 触发后**立即**执行：`python3 scripts/dream_orchestrator.py start --json`
- 每次用户回答后**立即**执行：`python3 scripts/dream_orchestrator.py answer --session <id> --value "<answer>" --json`
- 助手不得自行决定下一步。严格遵循脚本 JSON 中的 `instructions` 字段。

## Execution

脚本 JSON 中包含 `instructions` 字段，助手按该字段执行对应 status 的操作。`instructions` 可能包含当前及后续流程的完整规则。
