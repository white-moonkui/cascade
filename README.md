# cascade

**Guard LLM tool calls with rules, scoring, and audit trails.**

AI Agent 做工具选择是随机的、不可控的、不可审计的。cascade 在 LLM 选出工具之后、执行之前，插入一道治理阀门。

## 安装

```bash
pip install cascade
```

零外部依赖。

## 三行搞定

```python
from cascade import DecisionPipeline

pipe = DecisionPipeline()
result = pipe.guard(
    tool_calls=[
        {"id": "1", "name": "web_search",   "confidence": 0.9, "arguments": {"q": "..."}},
        {"id": "2", "name": "delete_file",  "confidence": 0.3, "arguments": {"path": "/"}},
        {"id": "3", "name": "send_email",   "confidence": 0.7, "arguments": {"to": "..."}},
    ],
    rules=[
        {"field": "confidence", "op": "gte",   "value": 0.5},
        {"field": "name",       "op": "nin",   "value": ["delete_file"]},
    ],
    strategy="softmax",
    top_k=2,
)

for tool in result["selected"]:
    print(f"✅ {tool['name']} (conf={tool['confidence']}, pressure={tool['pressure']:.3f})")
# ✅ web_search (conf=0.9, pressure=0.665)
# ✅ send_email (conf=0.7, pressure=0.335)
```

## 集成

```python
# OpenAI SDK — 在 tool_choice 前拦截
response = client.chat.completions.create(..., tools=my_tools)
safe_tools = pipe.guard(
    tool_calls=[t.dict() for t in response.choices[0].message.tool_calls],
    rules=[{"field": "name", "op": "nin", "value": BLOCKED_TOOLS}],
)
```

```python
# LangChain — Agent 输出过一道 cascade
agent_result = agent.invoke({"input": query})
safe = pipe.guard(tool_calls=agent_tool_calls, rules=[...])
```

## API

| 方法 | 作用 |
|---|---|
| `pipe.guard(tool_calls, rules, strategy, top_k, context)` | 一条命令完成规则验证 + 择优选择 + 审计日志 |
| `pipe.audit.recent(limit=10)` | 查看最近审计记录 |
| `pipe.audit.query(tool_name="...")` | 按工具名或状态查询审计记录 |

## 选择策略

| 策略 | 行为 |
|---|---|
| `softmax` | 按 confidence 软最大化分配压力（默认） |
| `linear` | 按 confidence 线性分配 |
| `uniform` | 所有候选等概率 |
| `threshold` | 低于 `min_score` 的候选直接淘汰 |

## 项目状态

v0.2.0 — 方向确定、API 稳定、81 个测试全过。正在建立集成生态。
