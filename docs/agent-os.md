# Agent-OS 接口文档

当前 CLI 接口的现状说明，供 agent 编排器 / pipeline 调用时参考。

---

## 调用接口

```bash
./bin/ask.sh [OPTIONS] "QUESTION"
```

| 参数 | 类型 | 说明 |
|------|------|------|
| `"QUESTION"` | 必填（positional） | 问题文本 |
| `--mode patient\|doctor` | 可选 | 受众模式，默认 `patient` |
| `--domain SPEC` | 可选 | 强制路由，格式 `specialty:disease`（例：`cardiology:hypertension`） |
| `--deep` | 可选 | 原子声明核验 + 回炉自纠（降低幻觉，耗时约 2×） |
| `--debug` | 可选 | 路由和 payload 调试信息写入 stderr |

---

## 退出码

| 码 | 含义 |
|----|------|
| 0 | 正常回答（in-scope）或 OOB 拦截回答均返回 0 |
| 1 | 用法错误（缺少问题参数） |

**注意**：OOB 拦截与正常回答同为 exit 0，调用方需通过解析 stdout 区分（见下节）。

---

## 标准输出（stdout）

**In-scope 回答**：结构化文本直接输出（patient 五段 / doctor 五段），无额外包装。

**OOB 拦截**：输出内容以 `═══` 边框包裹：

```
═══════════════════════════════════════════════════════
[拒答模板内容]
═══════════════════════════════════════════════════════
```

调用方可检测 stdout 首个非空行是否以 `═══` 开头来判断 OOB。

---

## 标准错误（stderr）

仅在 `--debug` 时写入路由中间结果，格式固定以 `[DEBUG]` 开头：

```
[DEBUG] OOB 检测 → in_scope
[DEBUG] 自动路由 → cardiology:hypertension
[DEBUG] 正在构建 prompt (领域: cardiology:hypertension)...
```

正常调用（不带 `--debug`）stderr 静默。

---

## 前置过滤：oob_check.sh

`bin/oob_check.sh` 可单独作为 pipeline 前置过滤器，不调 API，<10ms 返回：

```bash
./bin/oob_check.sh "问题文本"
./bin/oob_check.sh --mode doctor "问题文本"
```

输出（stdout，单行）：

| 值 | 含义 |
|----|------|
| `in_scope` | 进入正常管道 |
| `out_of_scope:surgery` | A 类：外科/介入决策 |
| `out_of_scope:chemo` | B 类：化疗具体方案 |
| `out_of_scope:diagnosis` | C 类：确诊/读化验单 |
| `out_of_scope:dosing_change` | D 类：调药剂量 |
| `out_of_scope:unrelated` | E 类：无关任务 |

典型用法：先跑 `oob_check.sh`，in_scope 再调 `ask.sh`，省去一次 API roundtrip。

---

## 环境变量

| 变量 | 必须 | 说明 |
|------|------|------|
| `DEEPSEEK_API_KEY` | 是 | DeepSeek API 鉴权 |

通过项目根目录的 `.env` 文件或 shell 环境传入；`ask.sh` 会自动 source `.env`。

---

## 当前限制

- **无 JSON 输出模式**：stdout 为人类可读文本，无结构化 envelope
- **OOB 与正常回答同为 exit 0**：需依赖 stdout 格式（`═══`）区分
- **不支持 stdin / 批量输入**：每次调用传单个 positional 参数
- **路由器调用 API**：未命中关键词时，router.sh 会调 DeepSeek 做兜底路由（非纯本地）
