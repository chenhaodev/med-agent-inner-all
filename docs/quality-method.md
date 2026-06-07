# 质量方法论：分析+研究驱动的主动缺陷发现

> 核心原则：**eval = 确认与度量，不是发现。**  
> 发现前移到 (1) 静态契约分析器，(2) 研究推导的参照标准。

---

## 为什么要转范式

旧方式：跑 eval（30–50min LLM judge）→ 发现症状 → 逐题修。

这是反应式的，有两个问题：

1. **漏洞**：eval 只覆盖 gold 题，结构性缺陷可能在 gold 没命中的角落继续存在。
2. **浪费**：大量缺陷根本不需要运行模型就能发现——读 schema 对照 YAML 就够了，eval 是昂贵的替代品。

`bin/audit_routing.py` 是新范式的原型：用 <20s 静态脚本，在 eval 跑之前就捕获「路由到无 YAML 域→知识静默跳过」这一整类缺陷。本文档把该哲学推广到全部缺陷类型。

---

## 举一反三协议

**观察到任一缺陷时，不修个例——先归类，再消灭同类全部。**

```
观察到缺陷
    │
    ▼
归类（见下方分类法）
    │
    ├─→ 形式缺陷 / 契约错配  ──→  写静态分析器（bin/audit_*.py）
    │                                捞出同类全部  →  一次性批量修
    │
    └─→ 内容缺陷（知识面）   ──→  写研究探针（/autoresearch:reason + PubMed）
                                    推导参照标准  →  diff 出缺口  →  喂 extract.py
```

可复用的循环步骤：

1. **命名缺陷**（一句话描述失效模式）
2. **找根因**（读 schema / YAML / prompt，不跑模型）
3. **估规模**（grep/python 统计：这是 3 例还是 200 例？）
4. **写检查**：规模 ≥2 → 静态分析器；内容正确性 → 研究探针
5. **挂门禁**：新检查通过才允许进 eval
6. **批量修**（脚本或 extract.py 重扩），不逐题手动

---

## 缺陷分类法（带已证明实例与规模）

### 类型 I — 契约⟷源错配

模板/judge 要求的字段，在 knowledge YAML 里无对应可接地物，或词汇/粒度对不上。

| 实例 | 规模 | 静态可发现？ |
|------|------|-------------|
| **证据等级词汇错配**：源用 `高/中/低/未注明`，模板要 `高级别证据/中级别证据/…`，无映射 → 模型退化为统一"中级别证据" | 全库 573+191+3+216=983 条受影响 | ✓ `audit_grounding.py` G2 |
| **粒度差**：1 grade/entry vs 模板要 1 grade/line；8 个 YAML key_points 内嵌 B级/C级/I类，与 entry 级冲突 | 8 个 YAML | ✓ G3 |
| **提取噪声**：evidence_level 出现 `A`(3条)/`B`(1条) 等杂质 | 4 条 | ✓ G1 |
| **must_have_tags 元描述化**：标签是抽象短语（"药物选择依据"），模型永远不会逐字输出 | 已修复（audit_routing v1 发现） | ✓ audit_routing `[TAG]` |

发现工具：`bin/audit_grounding.py`（本方法论交付的首个分析器）

### 类型 II — 知识面缺陷

YAML 内容薄或空，导致模型回答缺乏具体临床细节，或根本没有可注入的接地物。

| 实例 | 规模 | 发现方式 |
|------|------|---------|
| **空 YAML**（0 条目） | 1 个 | 静态 `audit_coverage.py`（待建） |
| **薄 YAML**（≤3 条目，Tier3 批量扩展的薄尾） | 19 个 | 静态 `audit_coverage.py`（待建） |
| **章节欠提取**（ingest 页范围正确，但 extract 只拿到少量 key_points） | 待核查，对照 chapters.yaml 页跨度 | 静态 `audit_coverage.py`（待建） |
| **核心事实缺失**（YAML 有条目，但遗漏该病种的关键管理要点） | 待推导，autoresearch:reason + PubMed | 研究探针 |
| **页码漂移**（source_page 与印刷页不符） | 见 [[grounding-precision]]；已有 audit_pages.py | 静态 + folio_map.py |

发现工具：`bin/audit_coverage.py`（队列 D）+ `/autoresearch:reason`（队列 E）

### 类型 III — 路由可达性

问题被路由到无 YAML 的域 → 知识静默跳过 → 模型回退到参数记忆（高幻觉风险）。

| 实例 | 规模 | 静态可发现？ |
|------|------|-------------|
| 路由到 `*:general` 但该域无 YAML | 已消除（v3 修复） | ✓ `audit_routing.py` [ROUTE] ERROR |
| gold expected_domain 陈旧（指向次优有 YAML 的域） | 已消除（v3 修复） | ✓ [ROUTE] WARN |

发现工具：`bin/audit_routing.py`（已建，已通过）

---

## 两引擎 + eval 重定位

```
静态分析器套件          研究推导引擎             eval
(bin/audit_*.py)        (/autoresearch:reason     (eval.sh)
                         + PubMed MCP)

· 零 LLM               · 每病种推导应有           · 仅测残差
· <30s 全库扫完          核心事实集                · 通过三门禁
· 挂 CI/pre-commit      · diff 出内容缺口          后才运行
· 捕获 I/III 类         · 捕获 II 类              · 度量而非发现
```

**eval 前强制门禁（目标态）**：

```bash
python3 bin/audit_routing.py   # 路由可达性（已建）
python3 bin/audit_grounding.py # 证据接地可靠性（本次建）
python3 bin/audit_coverage.py  # 知识面完整性（队列 D）
# 三者全 exit 0 → 方可运行 eval.sh
```

---

## 后续队列（按举一反三协议排期）

### C — 降模板+定映射（证据等级真正修复）

根因：模板 vs 源词汇无映射，且过度要求逐条粒度。  
修复：只改 prompts/eval，不动 97 个 YAML。

1. `prompts/output_schema_doctor.md`：加「源等级→模板标注」映射表（`高→高级别证据`，`中→中级别证据`，`低→低级别证据`，`未注明→临床常用`），放宽到 entry 粒度
2. `bin/build_prompt.sh`：注入该 entry 实际 evidence_level 值，让模型有接地物
3. `eval/judge_prompt_doctor.md`：rubric 对齐——不再罚 entry 粒度标注，仅罚真违规（无标注、未映射、`未注明`当高级别）

门禁：`audit_grounding.py` G2 通过（mapping marker 存在且覆盖全部源取值）→ C 完成

### D — 知识面静态审计 `bin/audit_coverage.py`

目标：`python3 bin/audit_coverage.py` 精确命中 1 空 + 19 薄 YAML + 欠提取章节（对照 chapters.yaml 页跨度）。

### E — autoresearch 知识推导

对 D 标出的 ~20 个薄/破损 YAML：`/autoresearch:reason`（可配 PubMed MCP）推导核心事实集 → diff key_points → 喂 `bin/extract.py` 重扩。先从最高频问诊病种（心衰、糖尿病、CKD）的薄 Tier3 YAML 开始。

### F — eval 重定位

- 三门禁全 exit 0 后重跑 `eval.sh --mode both`，刷新过期 v3 指标
- 更新 README 性能指标表 + CHANGELOG
- `docs/roadmap.md` P0 顺延至三门禁通过之后

---

## 本文档自洽验证

任取已知缺陷，应能套用举一反三协议得出确定性动作：

| 缺陷观察 | 归类 | 规模估计 | 分析器/探针 |
|---------|------|---------|------------|
| "统一中级别证据" (HEMA_ANEMIA_01) | 类型 I：词汇错配 | 全库 216 条未注明 | `audit_grounding.py` G2 |
| PE_ANTICOAG_01 整段无证据标注 | 类型 I：契约错配 | 需 G2 mapping 修复 | Part C |
| AKI_MONITOR_01 回答被截断 | 形式缺陷（生成 bug） | 单例复现查 `call_deepseek.sh` max_tokens | 手动复现 + fix |
| CARD_VALVE_DR_01 内嵌 B级证据 | 类型 I：粒度冲突 | 8 个 YAML | `audit_grounding.py` G3 |
