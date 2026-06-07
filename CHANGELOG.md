# 更新日志

本项目所有重要变更记录于此。格式参考 [Keep a Changelog](https://keepachangelog.com/zh-CN/)。

## [v3.1] - 2026-06-07 — 执行速度优化 + eval judge 修复

### 指标（2026-06-07 全量重跑，含 generation max_tokens + P2 修复）

| 测试集 | 模式 | 题数 | 通过率（≥34/40） | 平均分 |
|--------|------|------|------------------|--------|
| in-scope | patient | 112 | **92.8%** | 37.9/40 |
| in-scope | doctor  | 110 | **89.1%** | 37.9/40 |
| OOB | patient/doctor | — | 拦截 100% | — |

eval 耗时：**~13 min**（并发 8，原串行 ~30–50 min）

### 新增 (Added)

- **`bin/eval_worker.sh`** — 单题并发 worker：每题 3 次 python3（原 ~15），
  并发安全（写独立文件），`--no-cache` 默认保证新鲜度
- **`bin/eval_deep_worker.sh`** — deep eval worker variant（含 verify_claims + reroll）
- **`bin/call_deepseek_stream.sh`** — SSE 流式调用；与非流式共享缓存 key

### 变更 (Changed)

- **`bin/eval.sh` / `bin/eval_deep.sh`**：串行循环 → `xargs -P 8` 并发扇出；
  删 `sleep 1`；O(n²) 结果累加 → 末尾一次聚合；新增 `--concurrency N` / `--cache` 参数
- **`bin/call_deepseek.sh`**：加内容寻址磁盘缓存（`.cache/deepseek/sha256.txt`）；
  命中 ~0.02s，默认开，`NO_CACHE=1` / `--no-cache` 绕过
- **`bin/ask.sh`**：加 `--stream` opt-in 旗标（默认关）

### 修复 (Fixed)

- judge `max_tokens` 600 → 4000：v4-flash reasoning model 在 600/1500 token 预算下
  全部 token 用于 chain-of-thought，content JSON 截断 / 为空
- eval worker JSON 解析：judge 输出中字符串值含字面量换行符（`Expecting ',' delimiter`）
  → 解析前 `.replace('\n', ' ')` 消除

---

## [v3.0] - 2026-06-07 — Tier3 全覆盖 + 契约审计

本次发布完成知识库 Tier3 扩展，消除全部「路由声明但无 YAML」的接地缺口，
并引入零成本静态契约审计将 eval 失败前移拦截。

### 指标

| 测试集 | 模式 | 题数 | 通过率（≥34/40） | 平均分 |
|--------|------|------|------------------|--------|
| in-scope | patient | 112 | **100%** | 39.0/40 |
| in-scope | doctor  | 110 | **96.3%** | 38.3/40 |
| OOB | patient/doctor | 30×2 | 拦截 100% / 无幻觉 100% | — |

- 知识 YAML：**97** 个（覆盖 Tier1/2/3 全部病种，无重复病种）
- gold.yaml：**147** 题（patient + doctor 双视角）
- `audit_routing.py`：**0 ERROR / 0 WARN**，TAG 接地全通过

### 新增 (Added)

- **Tier3 知识扩展（22 病种）**：先以 `digestive:hepatitis` 跑通完整流水线
  （ingest→YAML→router→audit→gold→eval），再批量扩展 21 病种：
  - 心血管：瓣膜病 / 心包疾病 / 先心病 / 其他心脏病（肿瘤·夹层）
  - 呼吸：睡眠呼吸暂停 / 胸膜疾病 / 肺肿瘤 / 危重症（ARDS）
  - 消化：食管/GERD / 黄疸
  - 内分泌：垂体 / 肾上腺 / 营养支持
  - 肾：肾血管疾病（TTP/HUS/肾危象）
  - 血液：骨髓增殖性肿瘤（CML/PV/ET/PMF）
  - 感染：发热/FUO / 社区获得性肺炎 / 皮肤软组织感染
  - 风湿：脊柱关节炎 / 系统性硬化 / 血管炎
- **`bin/audit_routing.py`** — 路由 + 标签契约静态审计（无 LLM，<20s 跑完 147 题）：
  - `[ROUTE]`：gold `expected_domain` 过 router.sh，区分 ERROR（路由全无 YAML→知识静默跳过）/ WARN（命中其他有 YAML 的 disease）
  - `[TAG]`：`doctor_must_have_tags` 须在命中 YAML 中作子串找到，捕获「元描述型标签」
  - 退出码 1 可挂 pre-commit / CI，建议作为 `eval.sh` 前置门禁
- gold.yaml 新增 42 道 Tier3 金标题（每病种 1 patient + 1 doctor）

### 变更 (Changed)

- `bin/router.sh`：新增 21 个关键词块 + check；修复多处消歧与同义词缺口
  （`GFR→eGFR`、睡眠呼吸暂停归呼吸科、GERD 归食管、肺栓塞归血栓、
  `发烧/发热` 旅行发热同义、`性功能` 裸词、`术前` 围手术期跨专科优先）
- gold.yaml：对齐 8 处陈旧 `expected_domain`（指向实际/更全的 YAML）
- `doctor_must_have_tags`：将 7 个「元描述」标签换为模型会逐字输出的具体临床词
  （如 `药物选择依据→β受体阻滞剂`、`具体阈值→T值`、`诊断标准→运动迟缓`）
- README：目录树、专科路由表、eval 指标同步至 v3

### 修复 (Fixed)

- **5 个「知识静默跳过」缺陷**：问题路由到 `*:general` 兜底（无 YAML）→ 回退参数记忆
  （RENAL_CKD_02 / ONCO_NAUSEA_01 / ONCO_CANCER_PAIN_01 / DIGE_GI_DR_01 / RESP_LUNG_TUMOR_01）
- 3 道 doctor 失败题（PE 抗凝路由、RA/骨质疏松标签自然化）
- `bone_mineral:osteoporosis` 路由错配：`$KW_BONE_MINERAL`（甲状旁腺/钙磷代谢）
  实为矿物质关键词，已重定向至 `bone_mineral:mineral_disorders`

### 移除 (Removed)

- **消除 2 组重复病种 YAML**：
  - `rheumatology/gout.yaml`（9 条，无关键词路由=死 YAML）→ 统一到 `endocrine/gout.yaml`（15 条）
  - `bone_mineral/osteoporosis.yaml`（12 条）→ 统一到 `rheumatology/osteoporosis.yaml`（14 条）
- 仓库整理：清理可重生成的 eval 测试产物（292→基线参考）、`bin/__pycache__`、
  6 个早期误提交的 summary/audit txt；`.gitignore` 收紧

---

## [v2] - 2026-06-06 — 双模式 + Tier1/2 知识库

- patient / doctor 双受众模式，doctor 证据档案式 5 段结构 + 证据等级标注
- Tier1/2 知识覆盖（14 病种），gold.yaml 扩至双 tag
- 5 类 action-based 越界保护，OOB 双模式拦截 100%
- 《中国高血压防治指南 2024》指南叠加机制
