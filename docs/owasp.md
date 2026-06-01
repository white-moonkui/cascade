# OWASP Agentic Top 10 — cascade 覆盖映射

> [OWASP Agentic Top 10 (2026)](https://genai.owasp.org/) 是 AI agent 安全
> 的行业基准。本文档映射 cascade 的 C1–C4 架构到每一项风险，
> 标明当前覆盖等级和需要补充的缺口。

---

## 覆盖等级

| 符号 | 含义 |
|------|------|
| ✅ **覆盖** | 模块直接满足 |
| ⚠️ **部分覆盖** | 需要配合外部逻辑 |
| ❌ **缺口** | 超出当前范围，需新增组件 |

---

## ASI-01 目标劫持 (Goal Hijacking)

攻击者通过 prompt injection 让 agent 执行非预期目标。

- **C1 Gate** 规则引擎可拦截特定工具 + 参数组合 → ✅
- **C4 Feedback** 负奖励信号降低被劫持工具的排名 → ✅
- 需要在 C1 前增加**注入检测层**作为深度防御 → ⚠️

> Phase 5 方向：运行时注入检测。

---

## ASI-02 过度能力 (Excessive Agency)

agent 拥有超出任务所需的工具权限。

- **C3 Selector** 选择压力（策略 + top_k）天然限制并行工具调用 → ✅
- C1 规则按 name/argument 过滤 → ✅
- **拒绝默认**（deny-by-default）模式：C1 gate 默认 reject 未显式允许的工具 → ⚠️ 当前是 permissive，需加 `default_action` 参数

> Phase 2/3 方向：CLI 增加 `--deny-by-default` 标志；C1 增加 default_action 配置。

---

## ASI-03 工具权限混乱 (Tool Permissions Confusion)

工具间的权限组合产生意料之外的副作用。

- C1 复合规则（`all_of` / `any_of` / `not_`）可表达跨工具约束 → ✅
- **操作链分析**（检测连续工具调用的副作用）→ ❌

> 超出当前范围，属于远期架构方向。

---

## ASI-04 不安全的输出处理 (Insecure Output Handling)

agent 输出包含注入载荷（SQLi、XSS 等）。

- **C2 Trigger** 可触发条件回调（如扫描输出中是否含引号/特殊字符）→ ⚠️
- 无内置内容安全策略 → ❌

> 补充方式：提供可插拔的**输出过滤器**（SQL 注入检测、shell 转义检查等）。

---

## ASI-05 投毒攻击 (Poisoning / Hallucination)

agent 基于幻觉或污染数据做出行动。

- C4 Feedback 通过奖励信号纠正持续误判 → ✅
- 无 RAG 对齐或事实核查 → ❌

> RAG 治理属于外部系统范畴，cascade 保持 focus 在 action 层。

---

## ASI-06 凭证/会话泄露 (Credential & Session Exposure)

工具调用泄漏敏感凭证。

- C1 规则可检查 `arguments` 中的敏感字段 → ✅
- **审计日志** JSONL 记录所有决策 → ✅
- 审计日志自身**无防篡改** → ⚠️

> Phase 2 方向：hash 链审计，确保日志不可抵赖。

---

## ASI-07 供应链漏洞 (Supply Chain Vulnerability)

第三方工具/插件引入恶意代码。

- 不在 cascade 直接范围，但每个工具调用经过治理即减少攻击面 → ⚠️
- **工具来源追溯**（在 metadata 中记录工具来源）→ ❌

> 适用方式：在 Candidate.metadata 中增加 `source` 字段以追溯。

---

## ASI-08 运行时错误处理不当 (Improper Error Handling)

agent 错误路径暴露敏感信息或被利用。

- C2 Trigger 可捕获特定条件并触发降级 → ✅
- Guard() 异常路径统一处理 → ✅

---

## ASI-09 人机信任缺口 (Human-in-the-Loop Gap)

高风险操作缺少人工确认。

- AuditTrail 提供完整的决策记录 → ✅
- **高风险操作 escalate**（触发人机确认流程）→ ❌
- 审计日志**合规导出**（JSON → CSV/PDF/SIEM）→ ❌

> Phase 5 方向：合规导出 + 人工 escalate 钩子。

---

## ASI-10 数据泄露 (Data Leakage)

Agent 通过工具调用间接泄露敏感数据。

- C1 规则按 argument 内容过滤 → ✅
- 审计日志中可能包含敏感数据 → ⚠️（依赖使用方清理）

---

## 汇总

| 风险 | 等级 | 已有模块 | 需要补充 |
|------|------|----------|---------|
| ASI-01 目标劫持 | ✅ | C1 + C4 | 注入检测（Phase 5） |
| ASI-02 过度能力 | ✅ | C1 + C3 | deny-by-default（Phase 2） |
| ASI-03 权限混乱 | ⚠️ | C1 复合规则 | 操作链分析（远期） |
| ASI-04 不安全输出 | ⚠️ | C2 | 输出过滤器（远期） |
| ASI-05 投毒攻击 | ✅ | C4 | — |
| ASI-06 凭证泄露 | ⚠️ | C1 + Audit | hash 链审计（Phase 2） |
| ASI-07 供应链漏洞 | ⚠️ | — | 来源追溯（远期） |
| ASI-08 错误处理 | ✅ | C2 | — |
| ASI-09 人机信任 | ⚠️ | Audit | 合规导出（Phase 5） |
| ASI-10 数据泄露 | ⚠️ | C1 | 审计脱敏（远期） |

**当前覆盖率：** 直接覆盖 5/10，部分覆盖 5/10，无完全覆盖缺口。

核心短板（按路线图依次补齐）：
1. Phase 2 → ASI-02 (deny-by-default) + ASI-06 (hash chain)
2. Phase 3 → ASI-05 (自适应阈值增强)
3. Phase 4 → 无新增 OWASP 覆盖（生态层）
4. Phase 5 → ASI-01 (注入检测) + ASI-09 (合规导出)
