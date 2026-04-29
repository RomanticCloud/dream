# 提示词目录

此目录用于存放创作提示词和辅助工具，包括但不限于：

- 章节起草提示词
- 修订建议模板
- 导出前自检清单

请根据项目需要使用相应的提示词。
# Prompt 运行约束

- 默认正文生成使用 compact-context：读取生成上下文包、连续性账本和预检计划，不再每章全量读取前文。
- `CONTINUITY_LEDGER` 是最高优先级事实源；当摘要、上一章片段或模型判断冲突时，以账本和预检计划为准。
- 工作卡必须基于正文事实抽取结果填写，不得新增正文未发生的事件、资源变化或人物关系变化。
- full-context 全前文读取仅作为回改、漂移修复、批次检查或卷尾检查的兜底模式。

## 正文模型配置

- 默认配置文件：skill 根目录 `dream_model_config.json`。
- 项目级覆盖：项目目录 `dream_model_config.json`。
- 默认 `body.backend=opencode`，表示继续使用当前 opencode 执行模型。
- 若要正文使用 DeepSeek，将项目级配置写为：

```json
{
  "body": {
    "provider": "deepseek",
    "model": "deepseek-v4-pro",
    "context_window_tokens": 1000000,
    "temperature": 0.8,
    "max_tokens": 6000
  }
}
```

- DeepSeek API Key 使用环境变量 `DEEPSEEK_API_KEY`，不要写入配置文件。
- Kimi 可选择 `kimi/kimi-k2.6`，API Key 使用环境变量 `KIMI_API_KEY`，不要写入配置文件。Kimi Coding Plan/网页订阅不等同于 Moonshot API 鉴权；若 `/v1/models` 返回 `401 Invalid Authentication`，需要在 Moonshot API 控制台确认 API Key 与 API 权限。
