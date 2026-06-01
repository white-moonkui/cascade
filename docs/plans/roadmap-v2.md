# Cascade 路线图 v2 — 方向 A+B 并行战略

> 版本：v2.0 | 日期：2026-06-01
> 基于 Phase 1-5 完成 + 市场调研结论

---

## 战略总览

```
┌─────────────────────────────────────────────────┐
│              Cascade 生态战略                       │
├─────────────────┬───────────────────────────────┤
│   方向 A        │      方向 B                     │
│   cascade 迭代   │      cascade-scan 安全评测框架    │
│   (治理库深耕)    │      (蓝海赛道卡位)               │
├─────────────────┼───────────────────────────────┤
│   Phase 6-9     │      Phase S1-S4              │
│   适配器/优化/    │      MVP→评测平台→CI/CD→生态     │
│   文档/社区       │                               │
└─────────────────┴───────────────────────────────┘
```

### 核心原则

| 原则 | 说明 |
|------|------|
| 零依赖核心不变 | 两个方向均不向 `cascade` 核心添加运行时依赖 |
| 新依赖通过 extras | 所有框架适配器、评测工具依赖通过 optional-dependencies |
| C₃↔C₄ 闭环优势 | 方向 B 的核心差异化——竞品均无此能力 |
| 先开源后商业 | 两个方向均先完善开源版本，再考虑变现 |

---

## 方向 A：Cascade 迭代路线图（Phase 6-9）

### Phase 6 — 适配器扩展（估时：2 周）

**目标**：补齐主流 LLM 框架适配器，达到业界最全覆盖

#### 6.1 Google Gemini Adapter

```python
# cascade[gemini]
from cascade.adapters.gemini import guard_gemini_response
```

- `guard_gemini_response()` — 对 Gemini API 的 tool_call 响应进行治理
- 支持 `google-generativeai>=0.8`
- 惰性导入，零依赖核心
- ~70 行，匹配现有适配器风格

#### 6.2 AutoGen Adapter

```python
# cascade[autogen]
from cascade.adapters.autogen import guard_agent_output
```

- `guard_agent_output()` — 治理 AutoGen agent 的 tool 选择
- `wrap_agent(agent, pipeline=...)` — 自动包装 AutoGen Agent 类
- 支持 `pyautogen>=0.2`

#### 6.3 Cohere Adapter (可选)

```python
# cascade[cohere]
from cascade.adapters.cohere import guard_cohere_response
```

- 低优先级，Cohere 工具调用生态较小
- 只做基础 `guard_cohere_response()` 函数

#### 6.4 统一适配器测试套件

- 所有适配器共享 `tests/adapters/` 目录
- `test_openai.py`, `test_anthropic.py`, `test_gemini.py` 等独立的集成测试
- 遵循 Phase 4 建立的测试模式（mock 框架 SDK）

**验收标准**：
- [ ] Gemini adapter 实现 + 测试
- [ ] AutoGen adapter 实现 + 测试
- [ ] Cohere adapter 实现 + 测试（可选）
- [ ] 所有适配器测试通过（`pytest tests/test_adapters/`）
- [ ] CHANGELOG 更新，版本 v0.8.0

---

### Phase 7 — 策略引擎增强（估时：2 周）

**目标**：让策略定义更强大、更易复用

#### 7.1 内置规则预设库

```python
from cascade.presets import (
    DANGEROUS_TOOLS,      # 危险工具黑名单
    CODE_EXECUTION,       # 代码执行管控
    FILE_OPERATIONS,      # 文件操作治理
    NETWORK_ACCESS,       # 网络请求管控
    DATA_EXFILTRATION,    # 数据防泄漏
    PRIVILEGED_ACTIONS,   # 高权限操作
)
```

- 每个 preset 是一个 `list[dict]` 规则集合
- 可组合使用：`DANGEROUS_TOOLS + FILE_OPERATIONS`
- 零额外依赖

#### 7.2 策略模板系统

- YAML 策略文件支持 `@extends` 引用基础模板
- 内置模板库：`strict`, `moderate`, `permissive`, `production`
- 示例：

```yaml
# policy.yaml
name: my-policy
extends: production
rules:
  - field: name
    op: nin
    value: [my_custom_blocked_tool]
```

#### 7.3 策略版本管理

- `cascade policy diff` — 对比两个策略文件的差异
- `cascade policy validate` — 严格 schema 验证
- `cascade policy apply` — 应用策略到 pipeline

**验收标准**：
- [ ] 5 个内置规则预设
- [ ] YAML `@extends` 模板系统
- [ ] 策略版本管理 CLI 命令
- [ ] 测试覆盖新增功能
- [ ] CHANGELOG 更新，版本 v0.9.0

---

### Phase 8 — 性能优化（估时：2 周）

**目标**：大规模场景下的 guard() 延迟优化

#### 8.1 规则引擎缓存

- 输入相同的规则集 + tool_calls 组合命中缓存，直接返回上一次结果
- `DecisionPipeline(cache_size=1024)` 配置缓存容量
- LRU 淘汰策略

#### 8.2 批量处理

- `pipe.guard_batch(tool_calls_list, ...)` — 一次调用处理多个 tool_calls 批次
- 内部并行评估，共享规则编译缓存

#### 8.3 延迟基准

- 建立 `perf/` 基准套件
- 记录 `guard()` P50/P95/P99 延迟
- 与 v0.7.0 基线对比

**验收标准**：
- [ ] 规则缓存实现（命中率 > 80% 典型场景）
- [ ] 批量 guard 接口 + 测试
- [ ] 延迟基准文档
- [ ] CHANGELOG 更新，版本 v0.10.0

---

### Phase 9 — 文档与社区（估时：1 周）

**目标**：降低上手成本，建立社区基础

#### 9.1 交互式教程

- `cascade tutorial` — CLI 交互式教程（类似 `pytest --tutorial`）
- 逐步引导用户完成安装 → 配置 → 运行

#### 9.2 示例仓库

- `examples/` 目录扩充：
  - `examples/guard_basic.py` — 基础用法
  - `examples/guard_with_injection.py` — 注入检测
  - `examples/guard_openai.py`, `guard_anthropic.py` — 适配器用法
  - `examples/policy_yaml.py` — YAML 策略
  - `examples/emergence.py` — C₃↔C₄ 闭环演示
  - `examples/audit_report.py` — 合规报告导出

#### 9.3 企业部署指南

- `docs/enterprise.md` — 企业级部署最佳实践
- 高可用部署架构
- 审计日志长期存储建议
- 与 SIEM 集成方案

**验收标准**：
- [ ] CLI 交互式教程
- [ ] 6+ 示例脚本
- [ ] 企业部署指南
- [ ] CHANGELOG 更新，版本 v0.11.0

---

## 方向 B：Cascade-Scan 安全评测框架

### 蓝海定位

```
市场缺口（WhiteFin 报告）：
┌─────────────────────────────────────┬──────────────┐
│ 能力                             │ 市场覆盖率    │
├─────────────────────────────────────┼──────────────┤
│ 对抗韧性测试 (Adversarial Resilience)│  5%          │
│ 执行后验证 (Post-Execution)        │  3%          │
│ 数据流治理 (Data Flow Governance)   │  0%          │
│ 跨平台治理 (Cross-Platform)        │  0 家解决    │
└─────────────────────────────────────┴──────────────┘

Cascade 差异化优势：
┌──────────────────────┬─────────────────────────┐
│ 能力                 │ 竞品状态                │
├──────────────────────┼─────────────────────────┤
│ C₃↔C₄ 闭环学习      │ 唯一（无竞品）          │
│ 零依赖核心           │ 唯一                    │
│ 适配器架构           │ 唯一（跨框架治理）       │
│ 注入检测+审计链      │ 极少数                  │
└──────────────────────┴─────────────────────────┘
```

### 产品定位

> **cascade-scan** — AI Agent 安全评测与持续进化平台
> 
> 基于 cascade 治理内核，自动化评估 Agent 系统的安全韧性。
> 与竞品的根本区别：每次评测结果反馈回 C₃↔C₄ 闭环，系统越用越强。

### 架构概览

```
cascade-scan
├── scan/                    # 评测引擎（核心）
│   ├── __init__.py
│   ├── engine.py            # 评测编排
│   ├── probes/              # 安全探针
│   │   ├── __init__.py
│   │   ├── injection.py     # 注入攻击测试
│   │   ├── tool_abuse.py    # 工具滥用测试
│   │   ├── escalation.py    # 权限提升测试
│   │   ├── data_leak.py     # 数据泄漏测试
│   │   └── prompt_leak.py   # 提示泄漏测试
│   ├── scenarios/           # 攻击场景
│   │   ├── __init__.py
│   │   └── registry.py
│   └── report.py            # 评测报告生成
├── cli.py                   # cascade-scan CLI
└── scorer.py                # 安全评分引擎
```

### 关键差异化能力

| 能力 | 说明 | 竞品对比 |
|------|------|---------|
| **闭环进化** | 扫描结果反馈回 C₃ 选择器，安全策略越用越精准 | 所有竞品为静态一次性扫描 |
| **执行后验证** | C₄ 反馈回路验证 Agent 实际执行结果 vs 声称行为 | 仅 3% 市场覆盖率 |
| **跨平台评测** | 适配器架构支持 OpenAI、Anthropic、Gemini 等 | 无竞品统一评测 |
| **审计证明** | SHA-256 审计链提供不可篡改的评测证据 | 极少支持 |
| **零依赖注入** | 评测本身无运行时依赖，适合 CI/CD | 多数竞品需要大量依赖 |

---

### Phase S1 — MVP：cascade-scan CLI（估时：2 周）

**目标**：可独立运行的 CLI 评测工具

#### S1.1 项目结构

```
cascade-scan/                 # 独立仓库（或 cascade 内置子包）
├── pyproject.toml
├── src/cascade_scan/
│   ├── __init__.py
│   ├── cli.py               # cascade-scan CLI 入口
│   ├── engine.py             # 评测引擎
│   ├── probes/
│   │   ├── __init__.py
│   │   ├── injection.py      # 注入攻击探针
│   │   └── tool_abuse.py     # 工具滥用探针
│   ├── scenarios/
│   │   ├── __init__.py
│   │   └── registry.py
│   ├── scorer.py             # 安全评分
│   └── report.py             # HTML/JSON 报告
├── tests/
└── README.md
```

#### S1.2 核心探针实现

**注入攻击探针**：
- 自动生成 20+ 注入向量（prompt injection, jailbreak, payload smuggling）
- 向目标 Agent 发送含攻击向量的 tool call
- 评估 cascade 治理是否拦截
- 利用 `cascade._injection` 模块作为检测后端

**工具滥用探针**：
- 模拟 Agent 调用危险工具（exec, delete, rm）
- 验证 cascade 规则引擎（C1）是否正确阻止
- 测试不同策略（softmax/threshold/ucb1）的响应

#### S1.3 评测报告

- HTML 报告：通过率/失败率图表 + 详细探测日志
- JSON 报告：结构化数据，方便 CI 集成
- 评分：0-100 安全评分，基于探针通过率

#### S1.4 CLI 命令

```bash
# 运行完整评测
cascade-scan run --pipeline my_pipeline.py

# 运行特定探针
cascade-scan run --probes injection,tool_abuse

# 生成报告
cascade-scan report --format html --output scan-report.html

# 查看安全评分
cascade-scan score --pipeline my_pipeline.py

# 持续评测（C₃↔C₄ 进化模式）
cascade-scan evolve --pipeline my_pipeline.py --iterations 10
```

**验收标准**：
- [ ] 2+ 核心探针实现并测试
- [ ] CLI 工具可独立运行
- [ ] HTML/JSON 评测报告
- [ ] 安全评分输出
- [ ] PyPI 发布 `cascade-scan` 包
- [ ] CHANGELOG + README 更新

---

### Phase S2 — 全面探针矩阵（估时：3 周）

**目标**：覆盖 OWASP Agentic Top 10 的 80%

#### S2.1 探针扩展

| 探针 | 覆盖攻击面 | 依赖 |
|------|-----------|------|
| `injection` | Prompt injection, jailbreak, payload smuggling | cascade._injection |
| `tool_abuse` | 危险工具调用、参数篡改 | cascade C1 |
| `escalation` | 权限提升、越权访问 | cascade C1 |
| `data_leak` | 数据泄漏、敏感文件读取 | cascade._injection |
| `prompt_leak` | 系统提示泄漏、指令提取 | 对话模式 |
| `loop_dos` | 无限循环、资源耗尽 | 超时检测 |
| `mcp_abuse` | MCP 工具滥用 | cascade MCP adapter |
| `feedback_poison` | 反馈投毒攻击 | cascade C4 |

#### S2.2 Attack Registry

- 集中管理攻击向量数据
- 支持自定义攻击向量导入
- 社区贡献攻击向量（JSON 格式）

#### S2.3 与 cascade 的深度集成

- `cascade-scan run --policy my-policy.yaml` — 加载 YAML 策略进行评测
- 评测结果自动写入 cascade 审计链
- C₃↔C₄ 闭环：扫描发现的弱点反馈给 C₃，减少未来同类攻击成功概率

**验收标准**：
- [ ] 8+ 探针实现
- [ ] OWASP Agentic Top 10 覆盖 80%
- [ ] Attack registry 支持自定义导入
- [ ] 与 cascade 审计链集成

---

### Phase S3 — CI/CD 集成（估时：2 周）

**目标**：让 cascade-scan 成为 CI pipeline 的自然步骤

#### S3.1 GitHub Actions

```yaml
# .github/workflows/cascade-scan.yml
name: Agent Security Scan
on: [push, pull_request]
jobs:
  scan:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: pip install cascade-scan
      - run: cascade-scan run --config scan-config.yaml
      - run: cascade-scan score --fail-below 70
```

- `--fail-below` 选项：安全评分低于阈值时 CI 失败
- `--diff` 选项：仅扫描与上次相比有变更的部分

#### S3.2 Pre-commit Hook

- `cascade-scan pre-commit` — 提交前快速扫描
- 轻量模式（仅 injection + tool_abuse 探针）

#### S3.3 VSCode Extension（可选）

- 在 VSCode 中 inline 显示安全评分
- 扫描结果集成到 PROBLEMS panel

**验收标准**：
- [ ] GitHub Action 模板
- [ ] `--fail-below` 阈值功能
- [ ] Pre-commit hook
- [ ] 完整测试覆盖

---

### Phase S4 — 进化平台（估时：3 周）

**目标**：C₃↔C₄ 闭环成为 cascade-scan 的核心差异化

#### S4.1 进化评测

- `cascade-scan evolve --iterations N` — 迭代评测
- 每次迭代后，结果反馈回 C₃ 选择器
- 安全评分随时间提升
- 输出进化曲线图表

```
示例输出：
Iteration 1: Score 52/100 — 12/23 probes passed
Iteration 2: Score 61/100 — 14/23 probes passed (+3 new blocks)
Iteration 3: Score 74/100 — 17/23 probes passed
...
Iteration 10: Score 91/100 — 21/23 probes passed
📈 +39 points in 10 iterations
```

#### S4.2 基线对比

- 保持每个版本的扫描结果基线
- `cascade-scan compare baseline.json current.json` — 版本间安全评分对比
- `cascade-scan regress` — 检测安全评分回退

#### S4.3 社区 Hub（可选）

- 共享攻击向量和场景
- 社区评测排行榜
- PR 提交新探针

**验收标准**：
- [ ] 进化评测模式实现
- [ ] 基线对比 + 回归检测
- [ ] 进化曲线可视化
- [ ] 完整文档

---

## 时间线与依赖关系

```
方向A                       方向B
─────                       ─────
Phase 6 (2周) ──────────┐   Phase S1 (2周)
  Gemini/AutoGen 适配器   │     MVP CLI + 核心探针
                         ├── 依赖 cascade v0.7+
Phase 7 (2周)            │   Phase S2 (3周)
  规则预设 + 策略模板      │     探针矩阵扩展
                         │
Phase 8 (2周)            │   Phase S3 (2周)
  性能优化                │     CI/CD 集成
                         │
Phase 9 (1周)            │   Phase S4 (3周)
  文档 + 社区             │     进化平台
```

**总估时**：
- 方向 A：~7 周（Phase 6-9）
- 方向 B：~10 周（Phase S1-S4）
- 可并行推进，总工期 ~10 周

**依赖关系**：
- Phase S1 依赖 cascade v0.7+（已满足）
- Phase S2 依赖 Phase S1 + cascade v0.7+
- Phase S3 依赖 Phase S2
- Phase S4 依赖 Phase S2（可与 S3 并行）

---

## 下一步建议

1. **立刻启动方向 B Phase S1**：创建 `cascade-scan` 项目骨架 + 2 个核心探针
2. **方向 A Phase 6 同步推进**：Gemini + AutoGen 适配器
3. **两路并行**：方向 A/B 由不同 subagent 同时推进

开始执行哪个方向？
