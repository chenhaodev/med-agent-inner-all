# 西氏内科学精要 家属/临床问答 Agent

基于《西氏内科学精要》（Cecil Essentials of Medicine，中文版）的内科常见病问答系统，支持**家属（patient）**和**临床（doctor）**两种受众模式。

使用 DeepSeek API + Unix-CLI 编排，无需 RAG/向量库，通过结构化知识注入 + 确定性路由实现跨 **17 专科**高精度问答。支持《中国高血压防治指南 2024》等近期指南叠加，知识来源可审计、可回溯至原书页码。

## 特性

- **覆盖 17 patient-facing 专科**：心血管 / 内分泌代谢 / 呼吸 / 消化（含肝）/ 肾 / 血液 / 感染 / 风湿骨 / 神经 / 肿瘤 / 骨矿物代谢 / 老年 / 姑息 / 围手术期 / 男性健康 / 女性健康 / 物质依赖
- **双受众模式**：
  - **patient**（默认）：面向患者家属，中文朴素表达，5 段式结构（这是什么/日常怎么做/何时就医/常见误区/依据）
  - **doctor**：面向临床医生，证据档案式 5 段结构（定义与流行病学/循证管理/红旗症状/证据等级汇总/参考），每条建议带证据等级标注
- **指南叠加**：`knowledge/<专科>/guidelines/` 放入指南 YAML 即可叠加，教材与指南冲突以最新指南为准
- **越界保护（5 类 action-based）**：确定性拦截外科手术决策（A）/ 化疗剂量方案（B）/ 诊断红线（C）/ 调药红线（D）/ 无关任务（E）；doctor 模式放宽鉴别诊断框架，红线仍生效
- **可量化评估**：patient 77 题 38.8/40（98.7%）；doctor 77 题（见 eval 表）；OOB 双模式拦截率/无幻觉率 100%

## 快速开始

```bash
# 1. 配置 API key
cp .env.example .env
# 编辑 .env，填入 DEEPSEEK_API_KEY

# 2. 安装依赖（仅用于 ingest/extract 步骤）
pip install -r requirements.txt

# 3. 提问（patient 模式，默认）
./bin/ask.sh "我爸有高血压，平时饮食要注意什么？"
./bin/ask.sh "妈妈2型糖尿病，血糖控制目标是多少？"
./bin/ask.sh --debug "心衰患者能做什么运动？"   # 显示路由/注入信息

# 4. doctor 模式（证据档案式，面向临床医生）
./bin/ask.sh --mode doctor "高血压患者血压控制目标？"
./bin/ask.sh --mode doctor --deep "心衰的循证管理方案？"   # deep = 声明核验 + 回炉自纠

# 强制指定专科（跳过自动路由）
./bin/ask.sh --domain cardiology:hypertension "高血压患者能喝茶吗？"
./bin/ask.sh --mode doctor --domain neurology:stroke "缺血性卒中急性期管理？"
```

## 目录结构

```
├── bin/
│   ├── ask.sh              # 主入口（oob → router → build_prompt → deepseek → postprocess）
│   ├── oob_check.sh        # 越界检测（确定性关键词，<10ms，不调 API）
│   ├── router.sh           # 问题 → 专科:疾病（关键词优先，DeepSeek 兜底）
│   ├── build_prompt.sh     # 组装多源知识栈 payload（教材 YAML + 指南 YAML）
│   ├── call_deepseek.sh    # DeepSeek API 调用（含重试）
│   ├── postprocess.sh      # 输出结构校验（5 段式 + 【依据】必含）
│   ├── eval.sh             # in-scope 全量 eval（LLM judge），支持 --mode patient|doctor|both
│   ├── eval_deep.sh        # deep eval（verify_claims → reroll 回炉循环），支持 --mode
│   ├── eval_oob.sh         # 越界专项 eval（确定性评分），支持 --mode doctor
│   ├── ingest.py           # PDF → source/chapters/<专科>/<疾病>.md（含页码标注）
│   └── extract.py          # 章节 md → knowledge YAML（DeepSeek 结构化提取）
├── knowledge/
│   ├── cardiology/         # hypertension / heart_failure / cad / arrhythmia
│   │   └── guidelines/     # 高血压防治指南2024.yaml 等指南叠加层
│   ├── endocrine/          # diabetes_t2 / dyslipidemia / thyroid / gout / obesity
│   ├── respiratory/        # asthma / copd / pneumonia
│   ├── digestive/          # gi / ibd / liver
│   ├── renal/              # ckd / nephritis
│   ├── hematology/         # anemia
│   ├── infectious/         # general
│   ├── rheumatology/       # ra / sle / osteoporosis
│   ├── neurology/          # stroke / movement_disorders / dementia / epilepsy / headache_pain
│   │                       # sleep_disorders / mood_behavior / dizziness / consciousness / 等 20 个
│   ├── oncology/           # lung_cancer / gi_cancer / breast_cancer / gu_cancer
│   │                       # tumor_complications / tumor_treatment_principles / 等 9 个
│   ├── bone_mineral/       # osteoporosis / mineral_disorders / metabolic_bone
│   ├── geriatrics/         # elderly_care
│   ├── palliative/         # palliative_care
│   ├── perioperative/      # periop_management
│   ├── mens_health/        # mens_health
│   ├── womens_health/      # womens_health
│   └── substance_use/      # alcohol_drugs
├── prompts/
│   ├── system_base.md          # patient 模式角色设定 + 安全红线
│   ├── system_doctor.md        # doctor 模式角色设定（临床医生受众）
│   ├── output_schema.md        # patient 5 段式输出规范
│   ├── output_schema_doctor.md # doctor 5 段式输出规范（含证据等级标注要求）
│   ├── oob_templates.md        # patient 越界拒答模板（5 类）
│   ├── oob_templates_doctor.md # doctor 越界拒答模板
│   └── sections/               # 17 专科回答指引 + few-shot
│       ├── cardiology.md / endocrine.md / respiratory.md / digestive.md
│       ├── renal.md / hematology.md / infectious.md / rheumatology.md
│       ├── neurology.md / oncology.md / bone_mineral.md / geriatrics.md
│       └── palliative.md / perioperative.md / mens_health.md / womens_health.md / substance_use.md
├── eval/
│   ├── gold.yaml           # 49 题 in-scope 金标集（跨 17 专科，patient + doctor 双 tag）
│   ├── oob_gold.yaml       # 30 题越界 eval 集（A/B/C/D/E 类 + 负样本）
│   ├── judge_prompt.md     # patient LLM judge 评分规范
│   └── judge_prompt_doctor.md  # doctor LLM judge 评分规范（证据等级 + grounding）
└── source/                 # git-ignored；ingest.py 生成
    └── chapters/<专科>/<疾病>.md
```

## 运行 Eval

```bash
# in-scope 全量 eval（patient 模式，约 15 分钟）
./bin/eval.sh

# doctor 模式 eval
./bin/eval.sh --mode doctor

# 双模式同跑（patient + doctor，约 30 分钟）
./bin/eval.sh --mode both

# 越界能力 eval（patient 模式，确定性评分，约 5 分钟）
./bin/eval_oob.sh

# doctor 越界 eval
./bin/eval_oob.sh --mode doctor

# deep eval（verify_claims → reroll 回炉，降低格式塌缩和幻觉）
./bin/eval_deep.sh --mode doctor
```

## 专科路由

| 专科 | 覆盖疾病（已有知识 YAML） | 关键词示例 |
|------|--------------------------|-----------|
| cardiology | 高血压、心衰、冠心病、心律失常 | 血压、心衰、冠心病、心绞痛、房颤 |
| endocrine | 2型糖尿病、血脂异常、甲状腺、痛风、肥胖 | 血糖、糖尿病、胰岛素、血脂、痛风 |
| respiratory | 哮喘、COPD、肺炎 | 哮喘、慢阻肺、喘息、肺炎、咳嗽 |
| digestive | 消化道疾病、IBD、肝病 | 胃、肠、肝硬化、乙肝、腹泻 |
| renal | 慢性肾病、肾炎 | 肾病、蛋白尿、肌酐、肾功能 |
| hematology | 贫血 | 贫血、血红蛋白、缺铁 |
| infectious | 感染性疾病（发热通科） | 感染、发热、肺结核、乙肝 |
| rheumatology | 类风湿关节炎、SLE、骨质疏松 | 关节痛、类风湿、狼疮、骨质疏松 |
| neurology | 脑卒中、运动障碍、痴呆、癫痫、头痛、睡眠障碍等 | 卒中、帕金森、痴呆、癫痫、头痛、失眠 |
| oncology | 肺癌、胃肠道癌、乳腺癌、泌尿系癌、肿瘤并发症 | 癌症、肿瘤、靶向治疗、化疗并发症 |
| bone_mineral | 骨质疏松、矿物质代谢、代谢性骨病 | 骨密度、骨折、钙磷代谢、甲旁亢 |
| geriatrics | 老年综合评估、衰弱、多病共存 | 老年人、衰弱、跌倒、多重用药 |
| palliative | 姑息治疗、安宁疗护、疼痛管理 | 姑息、安宁、疼痛控制、临终 |
| perioperative | 围手术期内科管理 | 术前评估、围手术期、手术风险 |
| mens_health | 男性健康（前列腺、勃起功能等） | 前列腺、勃起、男性激素 |
| womens_health | 女性健康（绝经、骨质疏松等） | 绝经、更年期、女性激素 |
| substance_use | 酒精/药物依赖与戒断 | 酒精、戒酒、药物依赖、成瘾 |

> **接地漏洞提示**：router 已声明约 40 个疾病 tag（如 `infectious:hiv`、`renal:aki`、`hematology:bleeding_disorders` 等），
> 但部分 YAML 尚未创建。`build_prompt.sh` 对缺失 YAML 静默跳过，路由命中后仅有专科 few-shot 而无页码可溯源条目。
> 补缺优先级见本节末"知识覆盖说明"。

## Doctor 模式

Doctor 模式面向临床医生，输出证据档案式 5 段结构：

| 段落 | 内容 |
|------|------|
| 【定义与流行病学】 | 核心定义 + 流行病学要点（2-4 句） |
| 【循证管理】 | 4-8 条管理建议，每条末尾必须标注证据等级 `(高级别证据)` / `(中级别证据)` / `(低级别证据)` / `(指南推荐·[指南名][年份])` |
| 【红旗症状/转诊指征】 | 3-5 条需立即处理或转诊指征，格式：`[症状] → [建议动作]（立即/急诊/专科）` |
| 【证据等级汇总】 | 将【循证管理】各类标注汇总为表格（等级 / 条目数 / 代表来源） |
| 【参考】 | 逐条列出实际引用来源（教材页码 + 指南名称年份） |

```bash
# doctor 模式示例
./bin/ask.sh --mode doctor "2型糖尿病血糖控制目标及降糖药选择策略？"
./bin/ask.sh --mode doctor --domain renal:ckd "CKD患者血压管理循证方案？"
```

配置文件：`prompts/system_doctor.md`、`prompts/output_schema_doctor.md`、`eval/judge_prompt_doctor.md`

## 越界分类（5 类 action-based）

| 类别 | 说明 | 示例 | doctor 模式 |
|------|------|------|-------------|
| A 外科/介入决策 | 搭桥/支架/移植/透析时机等手术指征 | "要放支架吗？" | 同样拒答 |
| B 肿瘤化疗方案 | 化疗药物选择、剂量、靶向/免疫方案 | "CHOP 还是 R-CHOP？" | 同样拒答 |
| C 诊断红线 | 要求确诊/读化验单/解读影像报告 | "帮我看化验单" | 同样拒答 |
| D 调药红线 | 要求自行调整用药剂量/停药 | "胰岛素要减量吗？" | 同样拒答 |
| E 无关任务 | 写作、翻译、天气、投资、菜谱等 | "帮我写作文" | 同样拒答 |

> v1 的 C 类"未覆盖专科"已在 v2 移除（神经/肿瘤/精神等现已 in-scope）。
> Doctor 模式对鉴别诊断框架讨论放宽（可列鉴别要点），但诊断红线仍生效（不替代临床判断）。

## 指南叠加

向已有专科目录的 `guidelines/` 下新增 YAML 文件即可自动生效：

```bash
# 示例：叠加心衰指南
knowledge/cardiology/guidelines/心衰指南2024.yaml
```

字段格式（与教材 YAML 相同，加 `year` 字段）：

```yaml
- id: GL_HF_001
  title: 心衰射血分数保留型（HFpEF）血压控制目标
  source: 中国心力衰竭诊断和治疗指南2024
  year: 2024
  source_page: "第 12 页"
  key_points:
    - 血压控制目标 <130/80 mmHg
```

教材与指南冲突时，系统约定以最新指南为准，【依据】同时引用教材章节/页与指南名/年。

## 添加新疾病/专科

1. 若章节 md 缺失：`bin/ingest.py`（按 `knowledge/chapters.yaml` 的 pdf_page 范围抽取）
2. `bin/extract.py source/chapters/<专科>/<疾病>.md` → 生成 `knowledge/<专科>/<疾病>.yaml`
3. 人工核对每条 `source_page` 对应印刷页码（folio），用 `bin/audit_pages.py` / `bin/folio_map.py` 校页码漂移
4. 在 `eval/gold.yaml` 加 1–2 道金标题（patient + doctor 双 tag），跑 `eval.sh --id` 验证
5. 若新专科：在 `prompts/sections/` 加专科回答指引

## Eval 指标（v2 最新结果）

| 测试集 | 模式 | 题数 | 指标 | 结果 |
|--------|------|------|------|------|
| in-scope | patient | 77 | 平均分 / 40 | 38.8（97.0%）✓ |
| in-scope | patient | 77 | 通过率（≥34/40）| 98.7% ✓ |
| in-scope | doctor | 77 | 平均分 / 40 | 待更新（temperature 降至 0.2 后重测中）|
| in-scope | doctor | 77 | 通过率（≥34/40）| 待更新 |
| OOB | patient | 30 | 拦截准确率 | 100% ✓ |
| OOB | patient | 30 | 无幻觉率 | 100% ✓ |
| OOB | doctor | 30 | 拦截准确率 | 100% ✓ |
| OOB | doctor | 30 | 无幻觉率 | 100% ✓ |

v2 目标：in-scope 平均 ≥85%（34/40），OOB 双模式拦截 100%，grounding ≥90%。

## 依赖

- `bash` ≥ 4.0
- `python3` ≥ 3.8
- `curl`
- `pyyaml`、`pymupdf`（仅 ingest/extract 步骤需要）
- DeepSeek API key（[申请地址](https://platform.deepseek.com)）

```bash
pip install -r requirements.txt
```

## 安全说明

- 本系统不替代专科医生诊断，所有药物调整建议均需就医
- 急症（胸痛、呼吸困难、突发偏瘫、意识丧失、大出血）→ 立即就医 / 拨打 120
- 诊断、处方、剂量调整类问题一律建议就诊，系统不给出具体用药方案
- Doctor 模式输出为教材知识摘要，不构成临床处方依据，实际诊疗须结合具体患者情况

## 知识来源

《西氏内科学精要》（Cecil Essentials of Medicine）中文版  
上卷（637 页）+ 下卷（632 页），共 1,269 页  
本机私有处理，生成的 YAML/章节文本不再分发（`pdfs/`、`source/` 已 git-ignored）
