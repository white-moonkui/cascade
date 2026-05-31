"""
LangChain 集成示例 — 在链式调用中注入 cascade 治理。

安装: pip install langchain langchain-community cascade
"""

# from langchain.tools import tool
from cascade import DecisionPipeline

# 模拟 LangChain Agent 生成的工具调用
agent_tool_calls = [
    {"id": "1", "name": "search", "arguments": {"query": "cascade python package"}, "confidence": 0.88},
    {"id": "2", "name": "calculator", "arguments": {"expression": "2+2"}, "confidence": 0.76},
    {"id": "3", "name": "shell_exec", "arguments": {"cmd": "rm -rf /"}, "confidence": 0.05},
]

# cascade 治理
pipe = DecisionPipeline()
result = pipe.guard(
    tool_calls=agent_tool_calls,
    rules=[
        {"field": "name", "op": "nin", "value": ["shell_exec", "delete_resource"]},
        {"field": "confidence", "op": "gte", "value": 0.3},
    ],
    strategy="linear",
    top_k=2,
)

print(f"通过: {result['passed']}")
print(f"选中 {len(result['selected'])} 个工具:")
for t in result["selected"]:
    print(f"  - {t['name']} (pressure: {t['pressure']:.3f})")

if result["rejected"]:
    print(f"拒绝 {len(result['rejected'])} 个工具:")
    for t in result["rejected"]:
        print(f"  - {t['name']} ({t['reason']})")
