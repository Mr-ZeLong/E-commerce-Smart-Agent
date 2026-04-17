# 中文大模型（Qwen）Prompt 技巧

## 中文场景核心原则：真诚 + 直接

Qwen 在中文客服场景下表现优异的核心要诀是：**"把 AI 当人看"**。不要堆砌复杂的英文提示词技巧，而应采用真诚、直接的表达方式。

**推荐原则**：
- 使用自然的口语化中文，避免翻译腔
- 指令清晰明确，不要绕弯子
- 用"请"、"需要"等礼貌用语，但不要过度客套
- 结构化表达优先于长段落描述

## 充分利用 Qwen 的指令遵循能力

Qwen 对结构化指令的遵循度较高，适合使用：
- 明确的编号列表（1. 2. 3.）
- Markdown 层级标题（## 规则、## 输出格式）
- 代码块包裹 JSON 示例

## Function Calling 兼容性

`IntentClassifier` 中已经做了兼容性处理：

```python
if "dashscope" in settings.OPENAI_BASE_URL.lower() or settings.LLM_MODEL.startswith("qwen"):
    tool_choice = "auto"  # Qwen 使用 auto 而非强制 function
```

**建议**：在使用 Qwen 的 `bind_tools` 时，优先使用 `"auto"` 模式，避免 `"required"` 导致的兼容性问题。

## 温度参数控制

| 场景 | 推荐 temperature |
|------|------------------|
| 意图分类 / 路由 | `0.0` - `0.2` |
| 结构化输出（JSON） | `0.0` - `0.3` |
| RAG 回答生成 | `0.3` - `0.5` |
| 会话摘要 / 创意回复 | `0.5` - `0.7` |
