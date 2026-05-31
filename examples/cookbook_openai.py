"""
OpenAI SDK 集成示例 — 在 tool_choice 前插入 cascade 治理。

安装: pip install openai cascade
"""

# import openai
from cascade import DecisionPipeline

# 模拟 OpenAI 返回的 tool_calls (实际用 client.chat.completions.create)
llm_tool_calls = [
    {"id": "call_1", "name": "web_search", "arguments": {"q": "latest AI news"}, "confidence": 0.92},
    {"id": "call_2", "name": "send_email", "arguments": {"to": "admin@example.com"}, "confidence": 0.45},
    {"id": "call_3", "name": "delete_file", "arguments": {"path": "/etc/passwd"}, "confidence": 0.12},
]

# cascade: 三条规则确保安全
pipe = DecisionPipeline()
result = pipe.guard(
    tool_calls=llm_tool_calls,
    rules=[
        {"field": "confidence", "op": "gte", "value": 0.5},
        {"field": "name", "op": "nin", "value": ["delete_file", "rm_rf"]},
    ],
    strategy="softmax",
    top_k=1,
)

# 结果
if result["selected"]:
    safe_tool = result["selected"][0]
    print(f"✅ 安全通过: {safe_tool['name']} (confidence: {safe_tool['confidence']})")
    print(f"   参数: {safe_tool['arguments']}")
    print(f"   审计 ID: {result['audit_id']}")
else:
    print(f"⛔ 所有工具调用被拦截")
    for g in result["gate_results"]:
        if not g["passed"]:
            print(f"   - {g['tool_name']}: 未通过规则验证")
    print(f"   审计 ID: {result['audit_id']}")

# 查看审计日志
print("\n--- 最近审计记录 ---")
for entry in pipe.audit.recent(limit=3):
    print(f"  {entry['timestamp'][:19]} | {entry['tool_name']} | {entry['status']}")
