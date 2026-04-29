# Dream Skill 协议文档

## 通用规则
- **所有面向用户的输出必须使用中文**，包括提问、选项、报告和提示
- 用户说 `停止`/`退出`/`中止`/`cancel`/`stop` 时立即停止，不再调用更多工具

## Status 处理规则

### question
- 使用 Question 工具，精确使用返回的 `header`、`text`、`options`
- 不得改述、增删或解释选项
- 用户回答后，执行 `python3 scripts/dream_orchestrator.py answer --session <id> --value "<answer>" --json`

### derive
1. 根据 `derive.kind`、`inputs`、`requirements` 生成候选
2. 生成完整 JSON payload：
   - `recommended`: 每个字段的最佳值
   - `candidates`: 每个字段最多 3 个候选
   - `reason`: 简要推荐理由
3. 通过以下命令提交：
   ```bash
   python3 scripts/dream_orchestrator.py submit-derived --session <id> --node <node> --value '<json>' --json
   ```
4. 最多 3 次重试

### run_script
- 直接执行返回的 `command`，不添加额外工作流逻辑
- 执行后将输出原样返回给 orchestrator（通过 answer 命令）

### report
- 向用户展示返回的 `message`
- 等待用户输入或 orchestrator 下一步指令

### done
- 结束工作流，不再调用 orchestrator

### error
- 向用户报告错误信息
- 安全停止

### outline_required
- 启动 Task 子代理
- 子代理读取 `prompt_file`（context/outline_prompt.txt）
- 调用 LLM 生成卷纲，确保包含：卷标题、卷定位、卷目标、抬升路径、核心冲突、关键转折、卷尾钩子
- 写入 `reference/卷纲总表.md`
- 完成后向 orchestrator 提交 `answer`（结果通过文件体现，answer 值可为"完成"）

### chapter_outline_required
- 启动 Task 子代理
- 子代理读取 `prompt_file`（context/chapter_outline_prompt_volXX.txt）
- 调用 LLM 生成章级规划，每章包含：章标题、核心事件、角色状态、必须出现、必须回收、新埋伏笔、悬念强度、字数建议
- 写入 `reference/volXX_chapter_outline.md`
- 完成后向 orchestrator 提交 `answer`

### body_required
- 启动 Task 子代理：
  1. 读取 `prompt_file`、`manifest_file`、`request_file`
  2. 如果 JSON 中存在非空 `model_runner_command`，优先直接执行该命令调用配置模型生成正文；执行后再次运行 `python3 scripts/continuous_writer.py run <project_dir> --generation-mode auto` 推进状态
  3. 如果 `model_runner_command` 为空，使用当前 opencode/Task 模型按 `prompt_file` 执行正文生成
  4. 默认使用 `compact_context` 链路：按 `required_context_files` 读取轻量上下文包、连续性账本和生成前预检计划
  5. 仅当请求中 `context_mode=full` 时，才按旧版 `required_read_sequence` 全量读取前文
  6. 生成正文（使用项目锁定字数范围）
  7. **自检格式**（最多3次重试）：
      - 时间流逝：`^\d+(分钟|小时|天|月)$`
      - 时间点：`^第\d+天(清晨|早晨|上午|中午|下午|傍晚|晚上|深夜)$`
      - 资源格式：`[+-]\d+[\u4e00-\u9fa5A-Za-z]+`
      - 悬念强度：`^[1-9]|10$`
      - 检查 `## 正文` 标记存在
      - 检查正文不含 `## 内部工作卡`
      - 检查正文服从 `preflight_plan` 与 `CONTINUITY_LEDGER`
  8. 直接写入 `chapters/volXX/chXX.md`
- 完成后向 orchestrator 提交 `answer`

### 模型配置
- skill 根目录默认配置：`dream_model_config.json`
- 项目目录可放置同名 `dream_model_config.json` 覆盖默认配置
- 进入正文生成前会先出现 `BODY_MODEL_SELECT` question，选项来自配置中的 `providers` 和默认 `opencode/current`
- 正文生成读取 `body` 配置；当 `body.backend=opencode` 时使用当前 opencode 模型，当 `body.provider=deepseek` 且 provider backend 为 `openai_compatible` 时，使用 `scripts/model_runner.py` 调用 DeepSeek
- API Key 只通过环境变量读取，例如 DeepSeek 使用 `DEEPSEEK_API_KEY`，不得写入配置文件

### cards_required
- 启动 Task 子代理：
  1. 读取 `prompt_file`、正文文件和 `chapter_facts` 文件
  2. 基于正文事实抽取结果生成6张工作卡，不得新增正文未发生事实
  3. **自检格式**（最多3次重试）
  4. 通过章节校验后更新 `context/CONTINUITY_LEDGER.json` 与 `context/CONTINUITY_LEDGER.md`
  5. 直接写入 `chapters/volXX/cards/chXX_card.md`
- 完成后向 orchestrator 提交 `answer`

### chapter_ready
- 主会话弹出 Question 询问用户：
  - 继续生成下一章
  - 查看当前章节
  - 暂停生成
  - 退出工作流
- 用户选择后向 orchestrator 提交 `answer`
- **注意**：body → cards 自动，无需用户确认；cards → chapter_ready 需用户确认
