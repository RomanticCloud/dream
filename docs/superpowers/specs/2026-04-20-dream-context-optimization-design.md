# Dream 技能上下文优化设计文档

## 1. 问题分析

### 1.1 根本问题
Dream 技能在章节生成时存在严重的上下文丢失问题：
- 从上一章 ~4000 字的叙事中仅提取 ~50 字的卡片元数据
- 信息丢失率高达 **98.75%**
- 导致人物状态不一致、事件细节遗忘、场景衔接断裂、伏笔丢失

### 1.2 当前架构缺陷

| 组件 | 当前行为 | 问题 |
|------|----------|------|
| `new_chapter.py` | 仅提取承接卡的 2-5 个要点 | 丢失叙事细节 |
| `writing_flow.py` | 不传递任何上下文 | 零上下文传播 |
| `chapter_validator.py` | 仅验证当前章 | 无跨章检查 |
| `common_io.py` | 仅处理 JSON/大纲 | 无叙事摘要功能 |

## 2. 解决方案：三层上下文管理架构

### 2.1 架构概览

```
┌─────────────────────────────────────────────────────────┐
│                    章节生成流程                           │
├─────────────────────────────────────────────────────────┤
│ 第1层：场景锚点层（即时连续性）                            │
│   - 提取上一章最后300-500字                                │
│   - 提供场景、对话、情绪的即时衔接                          │
├─────────────────────────────────────────────────────────┤
│ 第2层：状态跟踪层（中期一致性）                            │
│   - 跟踪人物状态（位置、情绪、目标、能力）                   │
│   - 跟踪事件线程（已发生、进行中、待解决）                   │
│   - 跟踪伏笔（已埋、待回收、已回收）                        │
├─────────────────────────────────────────────────────────┤
│ 第3层：交叉验证层（长期防漂移）                            │
│   - 验证承接卡要求是否被满足                               │
│   - 检测人物行为是否符合已建立的性格                         │
│   - 检测设定是否出现矛盾                                   │
└─────────────────────────────────────────────────────────┘
```

### 2.2 关键改进

| 维度 | 当前状态 | 改进后 | 提升倍数 |
|------|----------|--------|----------|
| 场景信息量 | ~50字 | ~400字 | 8倍 |
| 人物状态跟踪 | 3个字段 | 完整状态机 | 10倍 |
| 事件细节 | 关键事件字符串 | 完整事件线程 | 5倍 |
| 漂移检测 | 无 | 跨章验证 | ∞倍 |

## 3. 新模块设计

### 3.1 `narrative_context.py` - 叙事上下文模块

**职责**：提取和处理章节的叙事内容，提供即时场景连续性

**核心功能**：
- `extract_scene_anchor(chapter_path, word_count=400)`: 提取章节最后 N 字作为场景锚点
- `generate_narrative_summary(chapter_path)`: 生成结构化叙事摘要
- `extract_character_dialogue_style(chapter_path)`: 提取人物对话风格特征
- `save_chapter_context(chapter_num, context)`: 保存章节上下文到 `context/chapter_context.json`
- `load_previous_context(chapter_num, lookback=1)`: 加载前 N 章的上下文

### 3.2 `state_tracker.py` - 状态跟踪模块

**职责**：跟踪人物状态、事件线程、伏笔，提供中期一致性保障

**核心功能**：
- `update_character_state(chapter_path)`: 更新人物状态（位置、情绪、目标、能力）
- `track_plot_threads(chapter_path)`: 跟踪事件线程（已发生、进行中、待解决）
- `track_foreshadowing(chapter_path)`: 跟踪伏笔（已埋、待回收、已回收）
- `get_state_summary(chapter_num)`: 获取指定章节前的状态摘要
- `update_last_chapter(chapter_num)`: 更新最后处理的章节号

### 3.3 `enhanced_validator.py` - 增强的验证器

**职责**：添加跨章一致性检查，防止漂移累积

**核心功能**：
- `validate_cross_chapter_consistency(current_ch, prev_ch)`: 跨章一致性验证
- `check_carry_over_fulfilled(prev_carry, current_ch)`: 承接要求检查
- `detect_drift_patterns(state_history)`: 漂移模式检测

## 4. 数据流

### 4.1 完整流程

```
Chapter N 完成
    ↓
提取场景锚点（最后400字）
    ↓
更新状态跟踪器
    - 人物状态
    - 事件线程
    - 伏笔
    ↓
存储到 context/ 目录
    - chapter_context.json
    - state_tracker.json
    ↓
生成 Chapter N+1
    - 加载场景锚点
    - 加载状态摘要
    - 加载卡片元数据
    - 组装综合提示
    ↓
生成 Chapter N+1 正文
    ↓
跨章一致性验证
    - 人物状态检查
    - 场景衔接检查
    - 承接要求检查
    ↓
验证通过 → 继续下一章
验证失败 → 修正后重新生成
```

### 4.2 文件结构

```
project_dir/
├── chapters/
│   ├── vol1/
│   │   ├── ch01.md
│   │   ├── ch02.md
│   │   └── ...
│   └── vol2/
│       └── ...
├── context/                          # 新增目录
│   ├── chapter_context.json          # 每章的场景锚点和摘要
│   ├── state_tracker.json            # 人物/事件/伏笔状态
│   └── drift_log.json               # 漂移检测记录
├── scripts/
│   ├── narrative_context.py          # 新增模块
│   ├── state_tracker.py              # 新增模块
│   ├── enhanced_validator.py         # 增强的验证器
│   ├── new_chapter.py                # 修改：集成新模块
│   ├── writing_flow.py               # 修改：集成新模块
│   └── ...
└── ...
```

## 5. 集成点

### 5.1 与 `new_chapter.py` 集成

在 `generate_dynamic_content()` 函数中：
- 加载叙事上下文（场景锚点）
- 加载状态摘要
- 将两者添加到生成提示中

### 5.2 与 `writing_flow.py` 集成

在 `run_writing_flow()` 函数中：
- 章节完成后提取场景锚点
- 更新状态跟踪器
- 执行跨章一致性验证
- 检测到漂移时暂停并提示用户

### 5.3 与 `chapter_validator.py` 集成

在 `validate_chapter()` 函数中：
- 添加跨章一致性检查
- 集成承接要求验证
- 添加漂移检测

## 6. 实现步骤

### 阶段1：基础设施搭建（预计2小时）

1. 创建新模块文件
   - `scripts/narrative_context.py`
   - `scripts/state_tracker.py`
   - `scripts/enhanced_validator.py`

2. 创建 context 目录结构
   - 确保 `context/` 目录存在
   - 初始化 `chapter_context.json`
   - 初始化 `state_tracker.json`
   - 初始化 `drift_log.json`

3. 添加工具函数到 `common_io.py`
   - `extract_body()`: 提取章节正文
   - `extract_section()`: 提取指定章节
   - `extract_bullets()`: 提取要点列表

### 阶段2：核心模块实现（预计4小时）

1. 实现 `narrative_context.py`
   - 场景锚点提取
   - 叙事摘要生成
   - 对话风格提取
   - 上下文保存/加载

2. 实现 `state_tracker.py`
   - 人物状态更新
   - 事件线程跟踪
   - 伏笔跟踪
   - 状态摘要生成

3. 实现 `enhanced_validator.py`
   - 跨章一致性验证
   - 承接要求检查
   - 漂移模式检测

### 阶段3：集成和修改（预计3小时）

1. 修改 `new_chapter.py`
   - 集成叙事上下文
   - 集成状态摘要
   - 修改提示模板

2. 修改 `writing_flow.py`
   - 添加章节完成后的处理
   - 集成场景锚点提取
   - 集成状态更新
   - 集成跨章验证

3. 修改 `chapter_validator.py`
   - 添加跨章一致性检查
   - 集成承接要求验证
   - 添加漂移检测

### 阶段4：测试和验证（预计2小时）

1. 单元测试
   - 测试各模块核心函数

2. 集成测试
   - 测试完整章节生成流程
   - 测试跨章一致性验证
   - 测试漂移检测

3. 实际项目测试
   - 在现有项目上测试
   - 验证连续性改进效果
   - 收集性能数据

## 7. 预期效果

### 7.1 连续性改进

| 指标 | 当前状态 | 改进后 |
|------|----------|--------|
| 场景衔接 | 断裂 | 自然流畅 |
| 人物状态一致性 | 频繁不一致 | 高度一致 |
| 事件细节保留 | 遗忘 | 完整保留 |
| 伏笔回收率 | 低 | 高 |

### 7.2 性能影响

| 维度 | 影响 | 说明 |
|------|------|------|
| 生成时间 | +10-20% | 增加上下文加载时间 |
| 存储空间 | +5-10% | 增加状态文件 |
| 提示长度 | +30-50% | 增加上下文信息 |

## 8. 风险和缓解

### 8.1 主要风险

1. **提示长度增加**
   - 风险：可能超过模型上下文限制
   - 缓解：使用摘要而非全文，限制上下文长度

2. **性能下降**
   - 风险：生成时间增加
   - 缓解：异步处理状态更新，缓存常用数据

3. **实现复杂度**
   - 风险：多模块集成可能引入新bug
   - 缓解：充分测试，渐进式集成

### 8.2 缓解策略

1. 使用渐进式部署
   - 先在单个项目测试
   - 收集反馈后优化
   - 逐步推广到所有项目

2. 保持向后兼容
   - 新功能作为可选模块
   - 不影响现有工作流
   - 用户可选择启用

## 9. 附录

### 9.1 关键代码片段

#### 场景锚点提取
```python
def extract_scene_anchor(chapter_path: Path, word_count: int = 400) -> str:
    content = chapter_path.read_text(encoding="utf-8")
    body = extract_body(content)
    
    if len(body) <= word_count:
        return body
    
    anchor = body[-word_count:]
    first_period = anchor.find('。')
    if first_period > 0:
        anchor = anchor[first_period + 1:]
    
    return anchor.strip()
```

#### 状态摘要生成
```python
def get_state_summary(chapter_num: int) -> str:
    summary_parts = []
    
    # 人物状态摘要
    if self.state["characters"]:
        summary_parts.append("## 人物当前状态")
        for char_name, char_data in self.state["characters"].items():
            if char_data["states"]:
                latest_state = char_data["states"][-1]
                summary_parts.append(f"- {char_name}: {latest_state['location']}, {latest_state['emotion']}, 目标: {latest_state['goal']}")
    
    # 进行中的事件线程
    recent_threads = [t for t in self.state["plot_threads"][-3:]]
    if recent_threads:
        summary_parts.append("\n## 进行中的事件线程")
        for thread in recent_threads:
            if thread.get("ongoing_threads"):
                for thread_item in thread["ongoing_threads"]:
                    summary_parts.append(f"- {thread_item}")
    
    return "\n".join(summary_parts)
```

### 9.2 文件清单

| 文件 | 操作 | 说明 |
|------|------|------|
| `scripts/narrative_context.py` | 新增 | 叙事上下文模块 |
| `scripts/state_tracker.py` | 新增 | 状态跟踪模块 |
| `scripts/enhanced_validator.py` | 新增 | 增强验证器 |
| `scripts/new_chapter.py` | 修改 | 集成新模块 |
| `scripts/writing_flow.py` | 修改 | 集成新模块 |
| `scripts/chapter_validator.py` | 修改 | 集成新模块 |
| `scripts/common_io.py` | 修改 | 添加工具函数 |
| `context/chapter_context.json` | 新增 | 章节上下文存储 |
| `context/state_tracker.json` | 新增 | 状态跟踪存储 |
| `context/drift_log.json` | 新增 | 漂移检测记录 |
