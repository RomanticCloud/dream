---
name: dream
description: Run a strict question-driven workflow for general creative writing projects, including planning, drafting, revision, and export with stable continuity control.
compatibility: opencode
metadata:
  language: zh-CN
  domain: fiction
  genre: general
  mode: interactive-workflow
---

## When to use

Use this skill when the user wants to create, continue, plan, draft, revise, validate, or export a general creative writing project.

This skill is best for:

- new creative writing projects (novels, short stories, scripts)
- existing long-form writing projects
- outlines, volume plans, and batch plans
- chapter drafting and chapter revision
- continuity and consistency checks
- export, dashboard, and handoff tasks

Typical fit:

- any fiction genre (fantasy, sci-fi, romance, mystery, etc.)
- non-fiction creative projects
- screenplay and script writing
- collaborative writing projects

## Hard rules

- **所有面向用户的输出必须使用中文，包括提问、选项、报告、提示和菜单。**
- Respect explicit user intent before doing anything else.
- If the user says `停止`, `退出`, `中止`, `cancel`, or `stop`, stop immediately and do not call more tools.
- Do not guess branch decisions.
- If a branch decision is unclear, use a structured question.
- Use only fixed options for branch decisions.
- Treat strict interaction as branch control only. After a valid branch is confirmed, do not ask routine downstream state questions when a stable recommendation exists.
- In `完全自动` mode, downstream state-driven single-choice nodes default to the top recommendation derived from locked state.
- In `完全自动` mode, AI-generated content fields such as `core_promise`, `selling_point`, volume summaries, and batch plans should be produced automatically from locked state without asking the user to choose.
- Ask again only when no stable recommendation can be derived or when a decision would materially change project direction.
- Do not read project state files until the relevant branch has been confirmed.
- Do not read a specific existing project's files until that specific project name has been confirmed.
- Prefer continuing from discovered project state instead of repeating completed setup.
- Keep story logic bounded, consistent, and internally coherent.
- Preserve chosen point of view unless the user explicitly asks for another approach.

## Question rules

When a branch node requires user confirmation, use a structured question instead of open-ended branching.

Rules for structured questions:

- Present only the allowed fixed options for the current node.
- Do not replace fixed options with freeform paraphrases.
- If the runtime adds a custom input option, accept it only when it clearly maps to an allowed branch or an exact project name.
- If the answer is missing, invalid, or ambiguous, ask again once with the same fixed options.
- If the second attempt still does not yield a valid branch, exit safely.

Rules for downstream state nodes:

- Do not ask a structured question just because options exist.
- If the current locked state yields a recommended option, choose it automatically and continue.
- If several options are close, prefer the one with stronger continuity, coherence, and lower future rework cost.
- Surface multiple candidates only if the user explicitly asks to review options.

Implementation note:

- When the environment needs a serialized question payload instead of direct terminal interaction, prefer generating it through `python3 scripts/strict_interactive_runner.py`.
- Use fixed menus from `strict_interactive_runner.py init`, `strict_interactive_runner.py action-menu`, and `strict_interactive_runner.py final-menu` for branch nodes.
- Use `python3 scripts/strict_interactive_runner.py state <wizard_state.json|project_dir> <preset-key> [limit]` only when a state-driven branch truly requires explicit user selection after upstream information has been locked.
- Keep the runner output aligned with the fixed branch options and the current confirmed project state.

## Interactive workflow

### Node 1: INIT

First determine the top-level intent.

Allowed options:

- `新建项目`
- `退出`

Execution rule:

- **技能加载后，必须立即使用 Question 工具向用户提问，不要在此之前输出任何欢迎语、介绍语或其他文本。**
- 如果用户已经明确选择了分支，直接使用。
- 否则使用 Question 工具提出结构化问题，选项必须是：`新建项目` 和 `退出`。
- **所有面向用户的输出必须使用中文，包括提问、选项、报告和提示。**

### Node 2: RESUME_SCAN

Only enter this node if `继续已有项目` was confirmed.

Execution rule:

- Scan for existing creative writing projects.
- Prefer listing candidate projects in a clear numbered order.
- If no valid projects are found, report that and return to the top-level choice.

### Node 3: RESUME_PICK

Choose the exact project to continue.

Execution rule:

- Present specific project names as options.
- Do not offer `继续已有项目` again at this node.
- Do not read `.project_config.json`, `.workflow_lock.json`, `README`, `reference/`, `BATCH_PLAN.md`, `CONSTRAINT_SNAPSHOT.md`, or `CHECKPOINT_LOG.md` for any specific project until that exact project has been confirmed.
- If there are more than four projects, present the top four candidates and allow exact custom input for the rest.
- If no valid project is confirmed, exit safely.

### Node 4: NEW_PROJECT_SETUP

Only enter this node if `新建项目` was confirmed.

Execution contract:

- Create a temporary project directory first.
- Persist each confirmed node into `wizard_state.json`.
- Do not write `.project_config.json`, `.workflow_lock.json`, `reference/`, or `BATCH_PLAN.md` until final confirmation.
- Book title is generated late from the fully locked state instead of being collected first.
- Downstream options must consume the already locked upstream state.

Collect and lock these foundations in order:

1. basic specs and genre
2. project positioning and reader promise
3. protagonist/character starting point and growth route
4. **(conditional) power system setup** - only when genre requires it
5. world setting, rules, and background
6. main characters and relationship network
7. volume/chapter architecture
8. current volume batch plan
9. naming and final review

Ask structured questions only when a real branch or direction-changing preference needs confirmation. Do not ask for routine downstream single-choice picks in `完全自动` mode.

- After `basic_specs` locks `目标字数` and `单章字数`, the system automatically derives `总章数`, `卷数`, and `每卷章节数` without requiring user confirmation.
- For `project positioning`, `protagonist`, `world`, `characters`, `volume architecture`, `batch plan`, and `naming`, consume locked upstream state and auto-lock the strongest recommendation.
- Generate `core_promise` and `selling_point` from locked state directly. Option review is optional and user-triggered, not default.

### Basic specs collection details

When collecting basic specs, ask for these fields in order:

1. **目标字数**: 30万字, 40万字, 50万字, 100万字, or custom input
2. **单章字数**: 3500-4500字, 4500-5500字, or custom input
3. **节奏偏好**: 偏快（每章推进）, 偏稳（允许铺垫）, 快慢交替
4. **文风基调**: 热血燃向, 轻松幽默, 严肃写实, 黑暗深邃, 甜宠治愈, 悬疑推理
5. **主题材** (multi-select 1-3): 都市高武, 玄幻奇幻, 都市生活, 悬疑推理, 科幻未来, 仙侠修真, 历史军事
6. **补充元素** (optional multi-select): 重生, 穿越, 系统流, 升级流, 甜宠, 虐恋, 群像, 单女主

After collecting `目标字数` and `单章字数`, automatically derive:
- `总章数` = 目标字数 ÷ 平均单章字数
- `卷数` (recommended 8-15 chapters per volume)
- `每卷章节数`

Display the auto-derived values to the user but do not require confirmation.

### Power system initialization condition

**Only initialize power system when the following genres are selected:**

- `都市高武`
- `玄幻奇幻`
- `仙侠修真`

If any of these genres are included in `主题材`, the power system setup node will be activated. Otherwise, skip it.

### Project positioning collection details

When collecting project positioning, ask for these fields in order:

1. **叙事方式**: 第三人称有限视角, 第一人称有限视角, 全知视角
2. **主冲突** (multi-select 2-3): Dynamically generated based on `main_genres` from basic_specs
3. **核心追读动力** (multi-select 2-3): Dynamically generated based on `style_tone` from basic_specs
4. **一句话主承诺**: Auto-generated based on locked basic_specs and positioning choices, user can edit
5. **一句话卖点**: Auto-generated based on locked basic_specs and positioning choices, user can edit

Conflict options by genre:
- 都市高武: 职业晋升, 升级成长, 势力打压, 复仇翻盘
- 玄幻奇幻: 探索秘境, 升级成长, 血脉觉醒, 种族战争
- 都市生活: 职场竞争, 情感纠葛, 身份追寻, 生活危机
- 悬疑推理: 谜题揭晓, 身份追寻, 势力博弈, 危机追逐
- 科幻未来: 星际探索, 科技竞争, 末日危机, 权力争斗
- 仙侠修真: 境界突破, 门派争斗, 秘境探索, 功法传承
- 历史军事: 权力争斗, 战争谋略, 身份追寻, 势力博弈

Reader hook options by tone:
- 热血燃向: 看主角逆袭, 看成长蜕变, 看实力爆发
- 轻松幽默: 看主角搞笑, 看日常轻松, 看反转打脸
- 严肃写实: 看现实困境, 看人性挣扎, 看社会洞察
- 黑暗深邃: 看主角黑化, 看复仇清算, 看世界崩塌
- 甜宠治愈: 看甜蜜恋爱, 看温暖成长, 看治愈救赎
- 悬疑推理: 看谜题揭晓, 看真相浮出, 看线索串联

### Node 4.x: POWER_SYSTEM_SETUP

**Only enter this node if `主题材` contains: 都市高武, 玄幻奇幻, or 仙侠修真.**

This node designs the combat-oriented power system including realm progression, resource economy, and character advancement mechanics.

#### Power system collection details

When collecting power system, ask for these fields in order:

1. **境界体系**: List the realm/level names in progression order
   - Example: 淬体 → 聚气 → 化灵 → 结丹 → 元婴 → 出窍 → 分神 → 渡劫 → 大乘
   - Recommended: 5-8 realms for medium-length projects, up to 10 for long projects

2. **每境界小阶段**: How many sub-levels per realm
   - Default: 1-9重 (9 sub-levels)
   - Alternative: 初期/中期/后期 (3 stages)

3. **战力差距标准**: Define combat power differences
   - 同境界一重差距: ~10% power difference
   - 跨小境界 (e.g., 9重 → 下一境1重): ~3x power difference
   - 跨大境界: ~10x power difference, lower realm cannot defeat higher

4. **主角金手指**: The protagonist's unique mechanism
   - 核心功能: What special ability does the protagonist have?
   - 限制条件: What are the usage limitations, cooldown, or side effects?
   - 边界: What problems CANNOT be solved by this mechanism?
   - 代价: What price must be paid for advancement or cross-realm combat?

5. **主要资源类型**: Main resource types in the world
   - 资源名称, 用途, 稀缺度 (普通/稀有/传说), 获取方式

6. **资源分层规则**: Resource hierarchy rules
   - 普通资源: Can be abundant in later story (e.g., basic training materials)
   - 稀有资源: Used at key moments only
   - 传说资源: Limited appearance throughout the entire story

7. **越级边界**: Cross-realm combat boundaries
   - 同境界越级 (e.g., 越3重): Conditions and代价
   - 跨小境界: Conditions and代价
   - 跨大境界: Conditions and代价 (usually requires significant advantage)

#### Power system design principles

1. **Each realm must have actual combat power difference** - not just name changes
2. **Protagonist cannot cross-realm without paying a price** - every advantage has a cost
3. **The special mechanism must have clear boundaries** - specify conditions, costs, and unsolvable problems
4. **Resources must be stratified** - common resources can be abundant, rare resources maintain scarcity

#### Auto-derivation rules

After collecting 境界体系, automatically derive:
- Total number of advancement gates = number of realms - 1
- Recommended breakthrough frequency: minor breakthrough every X chapters, major realm breakthrough every volume

#### Output for wizard_state.json

Store power system data in this structure:

```json
{
  "power": {
    "realms": ["realm1", "realm2", ...],
    "sub_levels": "1-9重",
    "power_gaps": {
      "same_realm": "10%",
      "cross_sub_realm": "3x",
      "cross_realm": "10x"
    },
    "protagonist_mechanism": {
      "core_function": "",
      "limitations": "",
      "boundaries": "",
      "cost": ""
    },
    "resources": [
      {"name": "", "usage": "", "rarity": "", "acquisition": ""}
    ],
    "resource_hierarchy": {
      "common": [],
      "rare": [],
      "legendary": []
    },
    "cross_realm_boundaries": {
      "same_realm": {"condition": "", "cost": ""},
      "cross_sub_realm": {"condition": "", "cost": ""},
      "cross_realm": {"condition": "", "cost": ""}
    }
  }
}
```

### Node 5: PLAN_ONLY

Only enter this node if `仅规划` was confirmed.

Execution rule:

- Do not force project initialization.
- Do not create a project directory.
- Do not write `.project_config.json`, `.workflow_lock.json`, `reference/`, or `BATCH_PLAN.md`.
- Focus on premise, promise, setting, characters, growth route, volume outline, and chapter batch planning.
- Ask targeted structured questions only when planning branches are truly ambiguous and no stable recommendation exists.
- Otherwise, continue autonomously and report the chosen planning result.

### Node 6: ACTION_MENU

Use this node for active writing-stage projects.

Allowed options:

- `继续写作`
- `本批检查`
- `本卷收尾`
- `导出归档`
- `结束`

Execution rule:

- If the user's request already maps clearly to one option, use it directly.
- Otherwise ask a structured question with exactly these five options.
- In `完全自动` mode, `继续写作` means continuous prose production from the current chapter until the whole book target is completed, unless the user explicitly selects another menu option or interrupts.
- Do not stop after a single chapter, a single batch, or a single volume when `继续写作` is active.
- During continuous writing, advance in this loop: chapter draft -> carry-over cards -> next chapter -> batch check -> next batch -> volume close -> next volume -> final completion.
- A chapter is not complete until post-generation validation confirms: canonical chapter format, canonical work-card marker, complete required structure, and body word count inside the configured range.
- The workflow must not advance chapter, batch, volume, or whole-book progress on planned counts alone.
- The runtime helper should use `continuous_writer.py run` or `resume` as the dispatcher. That dispatcher must prepare the next chapter scaffold and draft prompt automatically once the previous chapter passes the gate, instead of returning to the menu after every single chapter.
- If the next chapter file is missing or still only contains scaffold placeholders, the dispatcher should create or refresh the draft prompt and stop at `draft_required` for that exact chapter.
- If a generated chapter falls below the minimum, exceeds the maximum, or misses required card structure, the agent must revise that same chapter before continuing.
- Only pause continuous writing when one of these happens: the user interrupts, required state is missing, a structural conflict blocks safe continuation, or the whole-book target has been reached.

### Node 7: FINAL_MENU

Use this node for completed or closed-loop projects.

Allowed options:

- `扩写补字数`
- `增加番外`
- `精修润色`
- `修改设定`
- `审阅导出`
- `结束`

Execution rule:

- If the project's workflow is already complete, go here instead of replaying setup steps.
- If the user's request already maps clearly to one option, use it directly.
- Otherwise ask a structured question with exactly these six options.

## Fallback rules

- If the user interrupts, stop immediately.
- If a branch cannot be validated after one retry, exit safely.
- If a required file is missing, report the gap and ask only the minimum follow-up needed.
- If an existing project appears complete, do not replay the entire setup sequence.
- If project state conflicts with the user's request, tell the user what was found and ask one focused question.
- If multiple downstream options are near-equal, choose the one that best preserves continuity and coherence.
- In `完全自动` mode, prefer safe autonomous continuation over extra confirmation.
- When `继续写作` is active, prefer resuming the writing loop over returning to the menu after each chapter.
- Treat repeated short chapters or invalid chapter format as blocking failures, not soft suggestions.
- Prefer these continuous states when reporting or dispatching progress: `missing_chapter_file`, `draft_required`, `gate_failed`, `batch_ready`, `volume_ready`, `book_completed`.

## Project state files

When resuming a confirmed project, prefer reading these files in this order when they exist:

- `.project_config.json`
- `.workflow_lock.json`
- `reference/`
- `BATCH_PLAN.md`
- `CONSTRAINT_SNAPSHOT.md`
- `CHECKPOINT_LOG.md`

Use discovered state to continue from the current stage instead of repeating completed work.

## Global state tracking files

For projects with power system enabled (都市高武/玄幻奇幻/仙侠修真), maintain these global state files to ensure continuity:

### ABILITY_STATE.json
Track protagonist's ability changes across chapters:

```json
{
  "current_abilities": [
    {"name": "感知增强", "grade": 1, "acquired_chapter": 1}
  ],
  "total_abilities_held": 1,
  "max_abilities": 5,
  "last_synthesis_chapter": null
}
```

Update rules:
- When gaining a new ability, add to `current_abilities`
- When synthesizing, remove 3 abilities, add 1 new ability
- Update `last_synthesis_chapter` when synthesis occurs
- Verify `total_abilities_held` matches array length

### RESOURCE_INVENTORY.json
Track resource gains and consumption across chapters:

```json
{
  "resources": [
    {"name": "能力素材", "quantity": 2, "grade": 1}
  ],
  "last_updated_chapter": 3
}
```

Update rules:
- When gaining resources, increase quantity
- When consuming resources, decrease quantity
- Verify quantity never goes negative
- Update `last_updated_chapter` on each change

### Maintenance rules
- Read these files before generating each chapter
- Update these files after each chapter is completed
- If state files don't exist, create them from the latest chapter's work cards
- If state conflicts with work cards, use work cards as source of truth

## Output expectations

Prefer structured outputs that are easy to continue later.

In `完全自动` mode, each stage update should briefly report:

- what was auto-locked
- why it was chosen
- what node comes next

Recommended deliverables:

- one-sentence premise
- core promise and selling point
- power system summary (if applicable - for 都市高武/玄幻奇幻/仙侠修真)
- world/setting summary
- character summary
- growth route
- volume outline
- chapter batch plan
- chapter draft or rewrite notes

#### Power system output (when applicable)

For projects with power system enabled, include:

- **境界划分**: List of realms in order
- **战力差距标准**: Same-realm, cross-sub-realm, cross-realm gaps
- **主角金手指**: Core function, limitations, boundaries, cost
- **资源系统**: Resource types, rarity hierarchy, acquisition methods
- **越级边界**: Conditions and costs for cross-realm combat

For continuous writing mode, also keep these operational expectations:

- each chapter remains a complete single chapter file with continuity cards
- the agent keeps producing subsequent chapter files without re-asking the menu
- each completed batch triggers a lightweight continuity check
- each completed volume triggers a volume-end delivery and handoff check

#### Continuity check for projects with power system

When `本批检查` is selected for projects with power system enabled (都市高武/玄幻奇幻/仙侠修真), perform these additional checks:

- [ ] 境界提升是否有合理铺垫和触发条件
- [ ] 资源获取是否有相应代价
- [ ] 越级战斗是否有合理条件和后果
- [ ] 是否出现战力通货膨胀（对手突然变弱）
- [ ] 主角金手指使用是否保持边界
- [ ] 高级资源是否保持稀缺，未出现泛滥

If any check fails, flag for revision before continuing.

- `book_completed` requires both validated chapter count and validated total prose length inside the configured completion range
- chapter drafting should target the mid-high part of the configured word range first, then compress once if needed; do not aim for the minimum on the first pass
- a chapter that lands below the configured `safe_lower` draft threshold is treated as a failed first draft and must be rewritten as a whole chapter instead of patched with trailing filler lines
- prefer whole-chapter rewrite and compression over repeated local append edits when fixing body length

When drafting a chapter, include necessary continuity cards using the canonical marker `## 内部工作卡`:

**For projects WITH power system (都市高武/玄幻奇幻/仙侠修真):**

1. Status card (add current realm field)
2. Combat card
3. Resource card
4. Relationship card
5. Emotion arc card
6. Carry-over card

**For projects WITHOUT power system:**

1. Status card
2. Plot card
3. Resource card
4. Relationship card
5. Emotion arc card
6. Carry-over card

#### Status card (with power system)

- 主角当前境界: [update]
- 主角当前伤势/疲劳: [update]
- 主角当前情绪基调: [update]
- 主角当前目标: [update]
- 本章结束后的状态变化: [update]

#### Combat card (replaces Plot card when power system is active)

- 本章主要交手对象: [update]
- 对方层级: [update]
- 主角是否越级: [是/否]
- 越级是否合理: [explanation]
- 是否暴露新底牌: [是/否]
- 本章战斗结果的后续影响: [update]

## Drafting gate policy

For chapter generation, the skill now uses a two-stage body-length policy:

- `min_words-max_words` remains the hard acceptance range for final validation
- `draft_target` is the preferred first-draft target and should sit in the mid-high part of the chapter range
- `safe_lower` is the minimum acceptable first-draft threshold before compression

Execution rules:

- Do not intentionally draft near the minimum word threshold on the first pass
- If the first draft falls below `safe_lower`, treat it as a failed draft and rewrite the whole chapter
- If the chapter is within the hard range but still below `draft_target`, prefer a stronger next first-draft rather than normalizing around thin chapters
- If the chapter exceeds the hard maximum, compress repeated reactions, redundant explanation, repeated environment description, and duplicate interior monologue before changing core action beats
- Avoid tail-end patching that only adds filler lines to satisfy length gates

## Project shape defaults

Use these defaults unless the user overrides them:

- 30k-100k words
- 3-6 volumes
- 30-80 chapters
- first-person or third-person limited point of view
- 8-12 chapters per batch

## Available local assets

This skill package includes reusable material under:

- `references/` for genre and craft guidance
- `templates/` for project documents
- `prompts/` for drafting support
- `scripts/` for project setup, validation, export, and dashboards
- `docs/` and `README.md` for package usage notes

## Useful scripts

If the environment allows shell commands, these local scripts can support the workflow:

- `python3 scripts/init_wizard.py` - 初始化项目
- `python3 scripts/volume_outline_generator.py .` - 生成卷纲
- `python3 scripts/new_chapter.py . --auto` - 自动生成模式（生成起草提示供对话使用）
- `python3 scripts/new_chapter.py . [vol] [ch]` - 生成章节起草提示（指定卷章）
- `python3 scripts/chapter_validator.py . [vol] [ch]` - 章节验证（质量门）
- `python3 scripts/chapter_validator.py . --json` - JSON格式输出（自动化集成）
- `python3 scripts/writing_flow.py .` - 连续写作流程
- `python3 scripts/merge_export.py . --format txt` - 导出合并
- `python3 scripts/project_dashboard.py . --save` - 项目仪表盘

Treat these as helpers. Adapt to the current workspace layout before running them.

## Quality Gate Policy (Reject & Regenerate)

This skill uses a strict quality gate policy instead of patching:

### Thresholds

| Metric | Threshold | Action |
|--------|-----------|--------|
| Word count | ≥ 85% of target | Pass |
| Word count | < 85% of target | **Reject** - Regenerate |
| Format | Missing markers | **Reject** - Regenerate |
| Cards | Incomplete | Warning - Allow with note |

### Pipeline Flow

```
Generate Chapter → Quality Gate Check → Pass? → Accept
                                      ↓ No
                              Reject → Adjust Prompt → Regenerate
```

### Example

```
Target: 4500 words/chapter
Pass threshold: 3825 words (4500 × 85%)

If chapter has 264 words:
  → REJECT (below 3825 threshold)
  → Do NOT patch/extend
  → Regenerate with adjusted prompt
```

## Hard constraints for final prose

Avoid these failure modes in final chapter text:

- uncontrolled point-of-view jumps
- inconsistent story logic
- character behavior that ignores prior setup
- exposition dumps that stall momentum
- hooks that are not paid off within a reasonable span

### Additional constraints for power system projects

For projects with power system enabled, also avoid:

- **Unbounded realm inflation**: Realms must have actual combat power differences, not just name changes
- **Free cross-realm combat**: Every cross-realm advantage must come with a cost
- **Resource abundance inflation**: Rare/legendary resources must remain scarce throughout the story
- **Power without consequence**: Every gain must have an appropriate cost or limitation

## Content Generation Workflow

This skill supports automated chapter content generation through the main conversation:

### Workflow

```
1. new_chapter.py --auto → 生成draft_prompt
2. 对话中根据prompt生成正文
3. 写入章节文件（含6张工作卡）
4. chapter_validator.py → 质量验证（85%阈值）
5. 失败 → 重试（最多5次，每次等待3秒）
6. 重试5次失败 → 暂停等待用户确认
```

### Commands

```bash
# 生成起草提示（自动模式）
python3 scripts/new_chapter.py . --auto

# 指定卷和章
python3 scripts/new_chapter.py . 1 1

# 质量验证
python3 scripts/chapter_validator.py . 1 1
```

### Quality Thresholds

| Metric | Threshold | Action |
|--------|-----------|--------|
| Word count | ≥ 85% × min_words | PASS |
| AI texture | ≤ 3/千字 | PASS |
| Retry | 5次失败 | 等待用户确认 |

## Style note

Aim for readable, engaging prose with clear momentum, visible escalation, and strong chapter-end hooks. Keep the world concrete, the stakes trackable, and the character's journey earned.