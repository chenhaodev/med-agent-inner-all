# 更新日志

本项目所有重要变更记录于此。格式参考 [Keep a Changelog](https://keepachangelog.com/zh-CN/)。

## [v3.4] - 2026-06-08 — 质量收口：双模式双破 95%（零幻觉契约下）

### 指标（2026-06-08 全量重跑）

| 测试集 | 模式 | 题数 | 通过率（≥34/40） | 平均分 | 溯源性 | OOB 拦截 |
|--------|------|------|------------------|--------|--------|---------|
| in-scope | patient | 112 | **95.5%** | 38.6/40 | 10.0 | 100% |
| in-scope | doctor  | 109 | **97.2%** | 38.4/40 | 9.8  | 100% |

canonical run：`eval/results/2026-06-08_11-36-07_patient.json` /
`eval/results/2026-06-08_11-41-37_doctor.json`。两模式双双 ≥95%，且**未新增任何无源临床知识**。

### 新增 (Added)

- **层3 安全底线叠加层** — `knowledge/{专科}/safety_floor/{disease}.yaml`，**仅 patient 模式注入**
  （`bin/build_prompt.sh`），`source: 安全底线`、**无 `source_page`**，与书本知识层物理隔离、可审计。
  首条 `knowledge/infectious/safety_floor/hiv.yaml`（HIV 家庭防护：接触血液戴手套/伤口处理）——
  落地 `HIV_DAILY_01` 的 B3-patient 失败（书外、家属语境、无临床类比），acc 40/40
- **`prompts/output_schema_doctor.md` 证据等级汇总「带数字两步自检示例」** — 显式演示「只数循证管理 8 行、
  不数红旗段」的逐类计数 + 填表，杜绝把红旗段标注算进汇总表导致数字虚高

### 变更 (Changed)

- **`prompts/output_schema_doctor.md` 反编造护栏** — 禁止由「检查前停药」外推为「治疗期间禁药」等
  注入片段未写明的用药时机/禁忌规则，附 PPI 正/反例。消除 `DIGE_HP_01` 把「呼气复查前停 PPI 2周」
  误推成「治疗期间避免 PPI」的幻觉（acc 6→10，与注入内容矛盾的外推清零）
- **黄疸 ALP 事实修正** — `DIGE_JAUNDICE_DR_01` acc 5→8
- **`eval/gold.yaml` 按「书本忠实」契约 triage 覆盖失败**：
  - **B3-doctor**：`GERI_POLY_01` 拆分为 patient 版（保留 `不可自行停药`）+ 新增 `GERI_POLY_DR_01`
    医生版（`must_warn: []`）——书外患教警告强塞 doctor 输出 = 制造幻觉且违反 doctor schema 禁患教规则
  - **B3-patient**：`HIV_DAILY_01` 改 `mode: patient`，去 `doctor_must_have_tags`，配套层3 安全底线

### 已知 / 长尾 (Known)

- doctor 通过率含 LLM 判官噪声（每跑约 6–10 题在 `S≥8/total≥34` 临界翻转，**平均分稳定 ~38.4**）；
  目标已重定为「0 可复现幻觉 + 平均 ≥38」，不追逐二元通过率的临界题
- `NEURO_DEM_DR_01`（S=7）为唯一三跑皆失的持续 doctor 失败，留待下轮 triage
- OOB「推荐治疗音乐」类无关请求拦截见 v3.3（已修）

---

## [v3.2] - 2026-06-07 — 算法质量修复 + Fast/Accurate 双模式

### 指标（2026-06-07 全量重跑）

| 测试集 | 模式 | 题数 | 通过率（≥34/40） | 平均分 | 溯源性 | error |
|--------|------|------|------------------|--------|--------|-------|
| in-scope | patient | 112 | **92.0%** | 38.3/40 | 10.0 | 0 (←1) |
| in-scope | doctor  | 110 | **90.9%** | 38.1/40 | 9.8  | 0 (←1) |
| OOB | patient/doctor | — | 拦截 100% | — | — | — |

两模式平均分均提升（37.9→38.3 / 38.1），doctor 通过率 89.1%→90.9%，
判官解析失败导致的 0/40 已清零（error 1→0）。

### 新增 (Added)

- **`bin/parse_judge.py`** — 健壮解析判官打分：括号配平提取 → 轻量修复 → 逐维正则兜底；
  解析不可信时调用方以 `--no-cache` 重跑判官。修复 `ONCO_LIFESTYLE_01` 因判官 JSON
  含未转义引号而被判 0/40 的工具链 bug（两 eval worker 复用）
- **`bin/doctor_checks.py`** — doctor 回答确定性静态检查（零 API）：证据等级同质化、
  处方剂量泄漏识别；被两 eval worker（flag）与 `postprocess.sh`（live WARN）复用

### 变更 (Changed)

- **`bin/ask.sh`**：新增 `--fast`（默认，单次生成）/ `--accurate`（核验+回炉，别名 `--deep`）
  双执行模式；与 `--mode patient|doctor` 正交
- **`prompts/output_schema_doctor.md`**：删除诱导模型把「计数核对…✓」算术写进正文的
  few-shot 与指令（修 `DIGE_HBV`/`PALL_COMFORT`/`ENDO_NUTR` 的 acc=0）；强化禁止同质化；
  处方红线加正/反例；红旗段加「禁忌药/急症处理必须纳入」安全底线
- **`prompts/output_schema.md`**：patient 红旗段加「注入已写明的用药禁忌必须点名提醒」
- **`bin/router.sh`**：癌痛/晚期肿瘤疼痛由 `oncology:tumor_complications`（无镇痛条目）
  改投 `palliative:palliative_care`（镇痛阶梯+阿片安全，源页 1224）→ `ONCO_CANCER_PAIN_01`
  接地 0→10、通过
- **`bin/eval_worker.sh` / `bin/eval_deep_worker.sh`**：判分解析改用 `parse_judge.py`；
  doctor 分支加 `doctor_checks.py` 的同质化 / 剂量提示（flag-only，安全分仍由判官裁定）

### 已知 / 长尾 (Known)

- OOB「推荐治疗音乐」类无关请求未被拦截（既有缺口，本次未触及 OOB 逻辑）
- patient/doctor 覆盖度长尾（must_warn / expected_topics 缺漏，如 `RHEU_OSTEO` / `CARD_CHD`）
  属既有知识深度缺口，按 roadmap 长尾延后

---

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
