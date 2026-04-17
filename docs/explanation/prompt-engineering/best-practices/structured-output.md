# 结构化输出（JSON Mode / Function Calling）设计技巧

## JSON Mode 设计技巧（OpenAI / Anthropic / Google 共识）

1. **显式声明输出格式**
   - 在 Prompt 中明确要求："请以 JSON 格式输出"
   - 提供完整的 JSON Schema 或示例结构

2. **提供示例（Example/Dummy Output）**
   ```
   请按以下格式返回结果：
   {
     "summary": "string",
     "items": [
       {"name": "string", "score": number}
     ]
   }
   ```

3. **使用 `response_format={"type": "json_object"}`**（OpenAI 兼容接口）
   - 确保模型被强制输出合法 JSON
   - 仍需在 Prompt 中说明期望结构

4. **处理嵌套与可选字段**
   - 对可选字段注明 `"description": "可选，如无则留空或省略"`
   - 避免过深的嵌套（>3 层易导致错误）

5. **验证与容错**
   - 始终在后端对模型输出做 JSON 解析和 Schema 校验
   - 准备重试/降级策略

## Function Calling 设计技巧

1. **函数描述要自解释**
   - `description` 字段必须清晰说明函数用途、参数含义、返回值
   - 这是模型决定是否调用的唯一依据

2. **参数 Schema 精确化**
   - 使用 `enum` 限制可选值
   - 明确 `required` 字段
   - 提供参数示例

3. **分离"思考"与"调用"**
   - 使用 `tool_choice` 控制调用行为
   - 让模型先输出推理（Chain-of-Thought），再决定函数调用

4. **错误处理注入**
   - 在 System Prompt 中告知模型：如果参数不足，应反问用户而非随意调用
