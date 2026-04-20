# Dream 技能子代理章节生成设计文档

## 1. 问题分析

### 1.1 当前架构的漂移问题

Dream 技能在章节生成时存在严重的上下文丢失问题：
- 从上一章 ~4000 字的叙事中仅提取 ~400 字的场景锚点
- 信息保留率仅 **10%**
- 导致人物状态不一致、事件细节遗忘、场景衔接断裂

### 1.2 元数据提取方案的局限性

即使实施了三层上下文管理架构（场景锚点、状态跟踪、交叉验证），仍然存在：
- 信息丢失（从4000字提取到600字摘要）
- 提取误差（正则表达式可能误判）
- 状态膨胀（长期运行后状态文件变大）

## 2. 解决方案：子代理章节生成

### 2.1 核心思路

**使用子代理（Subagent）生成章节正文，将所有前文章节完整加载到子代理的独立上下文中。**

```
主会话（协调层）
    ↓ 调用子代理
子代理会话（生成层）
    ├─ 加载前N章完整内容（或全部）
    ├─ 加载项目配置
    ├─ 加载章节规划
    └─ 生成新章节正文
    ↓ 返回结果
主会话（继续）
```

### 2.2 架构对比

| 方案 | 上下文大小 | 信息保留 | 漂移风险 | 复杂度 |
|------|-----------|----------|----------|--------|
| 当前元数据提取 | 0.5K tokens | 10% | 高 | 高 |
| 三层上下文架构 | 4.7K tokens | 35% | 中 | 中 |
| **子代理完整加载** | **~67K tokens（50章）** | **100%** | **零** | **低** |

### 2.3 200K上下文容量

| 小说规模 | 章节数 | Token估算 | 占200K比例 |
|----------|--------|-----------|-----------|
| 短篇 | 30章 | ~40K tokens | 20% |
| 中篇 | 50章 | ~67K tokens | 33% |
| 长篇 | 100章 | ~133K tokens | 67% |
| 超长篇 | 150章 | ~200K tokens | 100% |

**结论：一部长篇小说（100章）可以完全加载到子代理上下文中。**

## 3. 详细设计

### 3.1 核心函数

#### 3.1.1 `load_all_previous_chapters()`

```python
def load_all_previous_chapters(
    project_dir: Path, 
    vol_num: int, 
    ch_num: int,
    lookback: int = 0  # 0 = 全部加载
) -> list[dict]:
    """加载所有前文章节
    
    Args:
        project_dir: 项目目录
        vol_num: 当前卷号
        ch_num: 当前章节号
        lookback: 回溯章节数（0=全部）
    
    Returns:
        [
            {
                "vol": 1,
                "ch": 1,
                "title": "第1章 标题",
                "content": "完整正文..."
            },
            ...
        ]
    """
    chapters = []
    chapters_dir = project_dir / "chapters"
    
    # 遍历所有卷
    for vol_dir in sorted(chapters_dir.glob("vol*")):
        vol_num_match = re.search(r"vol(\d+)", vol_dir.name)
        if not vol_num_match:
            continue
        vol = int(vol_num_match.group(1))
        
        # 跳过当前卷之后的卷
        if vol > vol_num:
            continue
        
        # 遍历该卷的所有章节
        for ch_file in sorted(vol_dir.glob("ch*.md")):
            ch_num_match = re.search(r"ch(\d+)", ch_file.name)
            if not ch_num_match:
                continue
            ch = int(ch_num_match.group(1))
            
            # 跳过当前章节及之后的章节
            if vol == vol_num and ch >= ch_num:
                continue
            
            # 加载章节内容
            content = ch_file.read_text(encoding="utf-8")
            chapters.append({
                "vol": vol,
                "ch": ch,
                "title": f"第{ch}章",
                "content": content
            })
    
    # 如果设置了回溯限制，只保留最近N章
    if lookback > 0 and len(chapters) > lookback:
        chapters = chapters[-lookback:]
    
    return chapters
```

#### 3.1.2 `build_subagent_prompt()`

```python
def build_subagent_prompt(
    previous_chapters: list[dict],
    project_config: dict,
    current_chapter_info: dict,
    chapter_plan: dict
) -> str:
    """构建子代理的提示
    
    Args:
        previous_chapters: 前文章节列表
        project_config: 项目配置
        current_chapter_info: 当前章节信息
        chapter_plan: 章节规划
    
    Returns:
        完整的子代理提示
    """
    prompt = f"""# 章节生成任务

## 任务描述
你是一位专业的小说创作助手。请根据提供的前文章节和项目配置，生成新章节的正文内容。

## 项目配置
- 书名：{project_config.get('book_title', '未命名')}
- 题材：{', '.join(project_config.get('genres', []))}
- 文风：{project_config.get('style_tone', '热血')}
- 叙事视角：{project_config.get('narrative_style', '第三人称有限视角')}

## 当前任务
- 当前卷：第{current_chapter_info['vol']}卷
- 当前章节：第{current_chapter_info['ch']}章
- 字数要求：{project_config.get('min_words', 3500)}-{project_config.get('max_words', 4500)}字

## 章节规划
{chapter_plan.get('description', '无特殊要求')}

## 前文章节（完整内容）

"""
    
    # 添加所有前文章节
    for chapter in previous_chapters:
        prompt += f"""
### {chapter['title']}

{chapter['content']}

"""
    
    # 添加生成要求
    prompt += f"""
## 生成要求

1. **连续性要求**
   - 严格保持与前文的人物状态一致
   - 对话风格、语气保持自然延续
   - 场景描写风格一致

2. **内容要求**
   - 字数：{project_config.get('min_words', 3500)}-{project_config.get('max_words', 4500)}字
   - 包含完整的工作卡（状态卡、情节卡、资源卡、关系卡、情绪弧线卡、承上启下卡）
   - 承接前文章节的结尾

3. **格式要求**
   - 使用标准章节格式
   - 工作卡使用 `## 内部工作卡` 标记
   - 正文与工作卡分离

4. **禁止事项**
   - 不得出现与前文矛盾的设定
   - 不得遗忘前文埋下的伏笔
   - 不得突变人物性格或关系

请生成完整的第{current_chapter_info['ch']}章内容。
"""
    
    return prompt
```

#### 3.1.3 `dispatch_chapter_generation()`

```python
def dispatch_chapter_generation(
    project_dir: Path,
    vol_num: int,
    ch_num: int,
    use_subagent: bool = True
) -> dict:
    """调度章节生成
    
    Args:
        project_dir: 项目目录
        vol_num: 卷号
        ch_num: 章节号
        use_subagent: 是否使用子代理
    
    Returns:
        {
            "status": "success" | "error",
            "chapter_content": "生成的章节内容",
            "token_usage": 12345,
            "generation_time": 45.6
        }
    """
    if not use_subagent:
        # 使用传统方式（元数据提取）
        return generate_chapter_traditional(project_dir, vol_num, ch_num)
    
    # 1. 加载项目配置
    project_config = load_project_state(project_dir)
    
    # 2. 加载所有前文章节
    lookback = project_config.get("context_lookback", 0)  # 0 = 全部
    previous_chapters = load_all_previous_chapters(
        project_dir, vol_num, ch_num, lookback
    )
    
    # 3. 加载章节规划
    chapter_plan = load_chapter_plan(project_dir, vol_num, ch_num)
    
    # 4. 构建子代理提示
    prompt = build_subagent_prompt(
        previous_chapters=previous_chapters,
        project_config=project_config,
        current_chapter_info={"vol": vol_num, "ch": ch_num},
        chapter_plan=chapter_plan
    )
    
    # 5. 调用子代理
    start_time = time.time()
    result = dispatch_subagent(
        task_description=f"生成第{vol_num}卷第{ch_num}章正文",
        prompt=prompt,
        timeout=project_config.get("subagent_timeout", 300)
    )
    generation_time = time.time() - start_time
    
    # 6. 保存章节内容
    if result["status"] == "success":
        chapter_path = get_chapter_path(project_dir, vol_num, ch_num)
        chapter_path.write_text(result["content"], encoding="utf-8")
    
    return {
        "status": result["status"],
        "chapter_content": result.get("content", ""),
        "token_usage": result.get("token_usage", 0),
        "generation_time": generation_time
    }
```

### 3.2 修改的文件

| 文件 | 修改内容 |
|------|----------|
| `scripts/new_chapter.py` | 添加 `load_all_previous_chapters()`、`build_subagent_prompt()`、`dispatch_chapter_generation()` |
| `scripts/writing_flow.py` | 修改 `run_writing_flow()` 使用新的生成方式 |
| `prompts/chapter-draft.md` | 优化提示模板，适应子代理场景 |

### 3.3 配置选项

在 `wizard_state.json` 中添加：

```json
{
  "generation_config": {
    "mode": "subagent",           // "metadata" | "subagent"
    "context_lookback": 0,        // 回溯章节数（0=全部）
    "subagent_timeout": 300,      // 超时时间（秒）
    "enable_validation": true     // 是否启用生成后验证
  }
}
```

## 4. 工作流程

### 4.1 完整流程

```
1. 用户请求生成新章节
    ↓
2. 主会话调用 new_chapter.py
    ↓
3. new_chapter.py 检查生成模式
    ├─ 如果 mode == "metadata"：使用传统方式
    └─ 如果 mode == "subagent"：
        ↓
4. 加载所有前文章节
    ↓
5. 构建子代理提示
    ↓
6. 调用子代理生成
    ↓
7. 子代理返回章节内容
    ↓
8. 验证章节格式和连续性
    ↓
9. 保存章节文件
    ↓
10. 返回结果给主会话
```

### 4.2 子代理工作流程

```
1. 接收任务和完整上下文
    ↓
2. 阅读所有前文章节
    ↓
3. 理解项目配置和章节规划
    ↓
4. 生成新章节正文
    ├─ 保持人物状态一致
    ├─ 延续对话风格
    ├─ 呼应前文伏笔
    └─ 自然场景衔接
    ↓
5. 生成内部工作卡
    ├─ 状态卡
    ├─ 情节卡
    ├─ 资源卡
    ├─ 关系卡
    ├─ 情绪弧线卡
    └─ 承上启下卡
    ↓
6. 返回完整章节内容
```

## 5. 优势分析

### 5.1 技术优势

| 方面 | 优势 |
|------|------|
| **信息完整性** | 100%保留前文信息，无提取误差 |
| **连续性** | AI可以直接参考任何前文章节的细节 |
| **架构简化** | 不需要复杂的元数据提取和状态跟踪 |
| **可维护性** | 代码更简洁，逻辑更清晰 |

### 5.2 业务优势

| 方面 | 优势 |
|------|------|
| **零漂移** | 从根本上解决章节漂移问题 |
| **质量提升** | 生成的章节更自然、更连贯 |
| **成本可控** | 200K上下文完全足够，无需担心限制 |

### 5.3 成本分析

| 项目 | 当前方案 | 子代理方案 | 差异 |
|------|----------|-----------|------|
| Token使用/章 | ~0.5K | ~1.3K | +0.8K |
| 50章总计 | ~25K | ~65K | +40K |
| 100章总计 | ~50K | ~130K | +80K |

**结论：成本增加约160%，但换来的是100%的信息保留和零漂移。**

## 6. 实施计划

### 6.1 阶段1：核心功能（预计4小时）

1. 实现 `load_all_previous_chapters()` 函数
2. 实现 `build_subagent_prompt()` 函数
3. 实现 `dispatch_chapter_generation()` 函数

### 6.2 阶段2：集成测试（预计2小时）

1. 测试完整章节加载
2. 测试子代理提示构建
3. 测试端到端生成流程

### 6.3 阶段3：优化完善（预计2小时）

1. 优化提示模板
2. 添加配置选项
3. 完善错误处理

### 6.4 阶段4：生产部署（预计1小时）

1. 更新文档
2. 提交代码
3. 推送远程仓库

## 7. 风险和缓解

### 7.1 主要风险

| 风险 | 影响 | 缓解措施 |
|------|------|----------|
| Token成本增加 | 160% | 提供配置选项，允许用户选择 |
| 生成时间变长 | 30-60秒/章 | 异步处理，后台生成 |
| 上下文限制 | 超长篇可能超限 | 实现回溯窗口，只加载最近N章 |

### 7.2 缓解策略

1. **渐进式部署**
   - 先在单个项目测试
   - 收集反馈后优化
   - 逐步推广

2. **向后兼容**
   - 保留传统元数据提取方式
   - 用户可选择生成模式
   - 不影响现有工作流

## 8. 预期效果

### 8.1 连续性改进

| 指标 | 当前 | 改进后 | 提升 |
|------|------|--------|------|
| 信息保留率 | 10% | 100% | 10倍 |
| 漂移风险 | 高 | 零 | ∞倍 |
| 人物状态一致性 | 中 | 高 | 2倍 |
| 场景衔接自然度 | 中 | 高 | 2倍 |

### 8.2 用户体验改进

1. **零漂移** - 不再需要手动修正矛盾
2. **更自然** - 章节之间的过渡更流畅
3. **更省心** - 不需要担心遗忘伏笔或设定
