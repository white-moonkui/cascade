# Cascade：给你的 AI Agent 装上一道治理阀门

> 当 LLM 可以调用 `delete_file`、`exec_sql`、`send_email` 时，你还能放心让它「自主决定」吗？

---

## 问题：AI Agent 的工具调用是一把没有保险的枪

2026 年，每个开发者都在往应用里塞 AI Agent。OpenAI Function Calling、LangChain Agent、MCP Server——工具调用的门槛从未如此之低。

但有一个问题被系统性地忽视了：**Agent 决定调用哪个工具时，没有治理层。**

```
User: "帮我查一下最近的订单"
LLM: → 调用 delete_all_orders()
```

当前所有主流 Agent 框架（LangGraph、AutoGPT、crewAI、OpenAI SDK）都有一个共同的盲区：**LLM 自主决定一切，没有任何规则约束、审计追踪或反馈学习。**

Cascade 就是为填补这个空白而生的。

---

## Cascade 是什么

Cascade 是一个 **零依赖、纯 Python 的 AI Agent 工具调用治理中间件**。它插入 LLM 与工具执行之间，提供四层保护：

```
C1 (Gate)      ── 规则引擎，准入控制：「delete_file 不允许通过」
C2 (Trigger)   ── 事件触发器，状态监控：「连续 3 次高危调用 → 熔断」
C3 (Selector)  ── 选择压力，智能排序：「search 比 exec 更优先」
C4 (Feedback)  ── 反馈闭环，从结果中学习：「上次 delete 失败了，降权」
```

最核心的差异化能力：**C3↔C4 自涌现闭环**。系统会记住每次工具调用的结果，自动调整未来的选择偏好——无需人工标注，无需训练数据。

---

## 30 秒快速开始

```python
from cascade import DecisionPipeline

pipe = DecisionPipeline()

result = pipe.guard(
    tool_calls=[
        {"id": "1", "name": "search", "confidence": 0.92},
        {"id": "2", "name": "delete_file", "confidence": 0.15},
        {"id": "3", "name": "send_email", "confidence": 0.88},
    ],
    rules=[
        {"field": "confidence", "op": "gte", "value": 0.5},       # 只要高置信度
        {"field": "name", "op": "nin", "value": ["delete_file"]},  # 禁止危险工具
    ],
    strategy="softmax",
    top_k=1,
)

print(result["selected"])  # → search (唯一通过门控的工具)
print(result["audit_id"])  # → 审计追踪 ID
```

一行 `guard()` 完成四件事：**规则过滤 → 策略排序 → 审计记录 → 自涌现学习**。

---

## C1-C4 架构详解

### C1 门控（Gate）：确定性安全边界

11 种内置算子（`eq`、`ne`、`gt`、`regex`、`in` 等），支持 AND/OR/NOT 复合规则：

```python
from cascade.rules import all_of, high_confidence, safe_tools

pipe.guard(
    tool_calls=[...],
    rules=[
        all_of(
            high_confidence(0.7),           # confidence >= 0.7
            safe_tools(),                   # 不在危险名单中
        ),
    ],
)
```

### C3 选择器（Selector）：不只是 filter，是 rank

四种选择策略，让正确工具「浮上来」：

| 策略 | 逻辑 | 适用场景 |
|------|------|----------|
| **softmax** | 概率分布加权 | 多候选精选 |
| **linear** | 分数线性排序 | 确定性优先 |
| **uniform** | 等权随机 | 负载均衡 |
| **threshold** | 阈值截断 | 严格准入 |

### C4 反馈（Feedback）：从结果中学习

```python
# 工具执行成功，给正反馈
pipe.record_outcome("search", reward=+0.5)

# 工具执行失败，给负反馈
pipe.record_outcome("shell_exec", reward=-1.0)

# 查看系统学到了什么
print(pipe.governance_report())
# → {'scores': {'search': 0.5, 'shell_exec': -0.3}, ...}
```

下一次 `guard()` 调用时，`search` 的分数会自动提升，`shell_exec` 的分数会自动下降——**系统自己学会了哪些工具可靠，哪些不可靠。**

### Actions：不止拦截，还能修复

```python
from cascade.actions import block, redirect, transform

def scrub_pii(tc):
    """脱敏 PII 数据后再调用"""
    tc["arguments"]["text"] = "[REDACTED]"
    return tc

pipe.guard(
    tool_calls=[...],
    rules=[...],
    actions={
        "delete_file": redirect("safe_delete"),     # 自动重定向
        "send_email": transform(scrub_pii),          # 自动脱敏
        "exec_shell": block("Shell 调用已禁止"),      # 直接拦截
    },
)
```

---

## 与其他方案的对比

| 能力 | Cascade | LangGraph | AutoGPT | crewAI |
|------|---------|-----------|---------|--------|
| 确定性规则引擎 | ✅ 11 种算子 | ❌ | ❌ | ❌ |
| 复合规则 (AND/OR/NOT) | ✅ | ❌ | ❌ | ❌ |
| 选择策略排序 | ✅ 4 种 | ❌ | ❌ | ❌ |
| 反馈闭环学习 | ✅ C3↔C4 | ❌ | ❌ | ❌ |
| 审计追踪 | ✅ JSONL | 部分 | ❌ | ❌ |
| Actions（修复） | ✅ 3 种 | ❌ | ❌ | ❌ |
| 零外部依赖 | ✅ | ❌ | ❌ | ❌ |
| 插入现有框架 | ✅ 中间件 | N/A | N/A | N/A |

**Cascade 不是替代你的 Agent 框架——它是插入现有框架的治理层。** 用在 OpenAI SDK、LangChain、MCP Server 前面，都只需要一行 `pipe.guard()`。

---

## 实际集成示例

### 集成 OpenAI SDK

```python
import openai
from cascade import DecisionPipeline

pipe = DecisionPipeline()
BLOCKED = {"delete_file", "exec_shell", "drop_table"}

response = openai.chat.completions.create(
    model="gpt-4",
    tools=[...],
    messages=[{"role": "user", "content": "清理过期数据"}],
)

# 在工具执行前插入治理层
safe = pipe.guard(
    tool_calls=[tc.model_dump() for tc in response.choices[0].message.tool_calls],
    rules=[
        {"field": "name", "op": "nin", "value": list(BLOCKED)},
        {"field": "confidence", "op": "gte", "value": 0.6},
    ],
)

for tool in safe["selected"]:
    execute_tool(tool)  # 只执行通过治理的工具
```

### 集成 MCP Server

```python
# MCP Client 的工具列表经过 cascade 治理
mcp_tools = mcp_client.list_tools()
governed = pipe.guard(
    tool_calls=mcp_tools,
    rules=[
        {"field": "name", "op": "nin", "value": ["filesystem_write", "shell_exec"]},
    ],
    strategy="threshold",
    top_k=3,
)
```

---

## 当前状态与路线图

| 指标 | 数据 |
|------|------|
| 版本 | v0.3.0 |
| 代码量 | 1468 行（纯 Python，零依赖） |
| 测试覆盖 | 128 个测试全通过，代码/测试 ≈ 1:1 |
| 许可证 | MIT |
| 安装 | `pip install cascade` |

**已完成** (v0.3.0)：
- ✅ C1-C4 全链路治理
- ✅ C3↔C4 自涌现闭环
- ✅ 11 种规则算子 + 复合规则
- ✅ block/redirect/transform 动作修复
- ✅ CLI 工具 + 审计追踪

**下一阶段** (v0.4.0)：
- 🔜 异步 API（`async guard_async()`）
- 🔜 MCP Server 集成适配器
- 🔜 Web 控制台（规则可视化编辑器）
- 🔜 行业规则预设包（金融合规、医疗 HIPAA）

---

## 为什么你应该关注

如果你正在构建：
- 让 AI Agent 调用内部 API
- 让 AI Agent 访问数据库
- 让 AI Agent 执行系统命令
- 让 AI Agent 发送消息/邮件
- 任何 Agentic Workflow 的生产环境

**你需要 Cascade。** 不是因为 AI 今天会出错——而是因为当它出错时，你需要一个可观测、可修复、可学习的治理层。

---

## 安装与贡献

```bash
pip install cascade
```

- GitHub: [github.com/white-moonkui/cascade](https://github.com/white-moonkui/cascade)
- 文档: [github.com/white-moonkui/cascade#readme](https://github.com/white-moonkui/cascade#readme)
- 许可证: MIT
- 贡献指南: [CONTRIBUTING.md](https://github.com/white-moonkui/cascade/blob/main/CONTRIBUTING.md)

**1468 行代码，零依赖，MIT 开源。给你的 Agent 装上保险。**
