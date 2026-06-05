# 西氏内科学精要 家属问答 Agent

基于《西氏内科学精要》（Cecil Essentials of Medicine，中文版）的内科常见病患者/家属健康问答系统。

使用 DeepSeek API + Unix-CLI 编排，无需 RAG/向量库，通过结构化知识注入 + 确定性路由实现跨 8 专科 235 条知识条目的高精度问答。支持《中国高血压防治指南 2024》等近期指南叠加，知识来源可审计、可回溯至原书页码。

## 特性

- **覆盖 8 专科**：心血管 / 内分泌代谢 / 呼吸 / 消化（含肝）/ 肾 / 血液 / 感染 / 风湿骨
- **家属语气**：回答面向患者家属，非医学专业人员，中文朴素表达
- **5 段式结构输出**：【这是什么】/【日常该怎么做】/【什么情况要就医】/【常见误区】/【依据(章节/页·指南年)】
- **指南叠加**：`knowledge/<专科>/guidelines/` 放入指南 YAML 即可叠加，教材与指南冲突以最新指南为准
- **越界保护**：确定性拦截外科手术决策、肿瘤化疗方案、未覆盖专科（神内/精神/儿科/妇产）、无关任务
- **可量化评估**：in-scope eval 平均 39.3/40（98.3%）；OOB 拦截率 100%

## 快速开始

```bash
# 1. 配置 API key
cp .env.example .env
# 编辑 .env，填入 DEEPSEEK_API_KEY

# 2. 安装依赖（仅用于 ingest/extract 步骤）
pip install -r requirements.txt

# 3. 提问
./bin/ask.sh "我爸有高血压，平时饮食要注意什么？"
./bin/ask.sh "妈妈2型糖尿病，血糖控制目标是多少？"
./bin/ask.sh --debug "心衰患者能做什么运动？"   # 显示路由/注入信息

# 强制指定专科（跳过自动路由）
./bin/ask.sh --domain cardiology:hypertension "高血压患者能喝茶吗？"
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
│   ├── eval.sh             # in-scope 全量 eval（LLM judge）
│   ├── eval_oob.sh         # 越界专项 eval（确定性评分）
│   ├── ingest.py           # PDF → source/chapters/<专科>/<疾病>.md（含页码标注）
│   └── extract.py          # 章节 md → knowledge YAML（DeepSeek 结构化提取）
├── knowledge/
│   ├── cardiology/
│   │   ├── hypertension.yaml       # 教材基线，每条 source_page 可回溯
│   │   ├── heart_failure.yaml
│   │   ├── cad.yaml
│   │   ├── arrhythmia.yaml
│   │   └── guidelines/
│   │       └── 高血压防治指南2024.yaml   # 叠加层（优先级高于教材）
│   ├── endocrine/
│   │   ├── diabetes_t2.yaml
│   │   ├── dyslipidemia.yaml
│   │   ├── thyroid.yaml
│   │   ├── gout.yaml
│   │   └── obesity.yaml
│   ├── respiratory/    # asthma / copd / pneumonia
│   ├── digestive/      # gi / ibd / liver
│   ├── renal/          # ckd / nephritis
│   ├── hematology/     # anemia
│   ├── infectious/     # general
│   └── rheumatology/   # ra / sle / osteoporosis
├── prompts/
│   ├── system_base.md      # 角色设定 + 安全红线 + 教材vs指南优先级约定
│   ├── output_schema.md    # 5 段式输出规范（强制结构 + 禁止格式 + few-shot）
│   ├── oob_templates.md    # 越界拒答模板（4 类）
│   └── sections/           # 8 专科级回答指引 + few-shot
│       ├── cardiology.md
│       ├── endocrine.md
│       ├── respiratory.md
│       ├── digestive.md
│       ├── renal.md
│       ├── hematology.md
│       ├── infectious.md
│       └── rheumatology.md
├── eval/
│   ├── gold.yaml           # 29 题 in-scope 金标集（跨 8 专科，含指南叠加题）
│   ├── oob_gold.yaml       # 25 题越界 eval 集（A/B/C/D 类 + 负样本）
│   └── judge_prompt.md     # LLM judge 评分规范（覆盖/准确/安全/溯源）
└── source/                 # git-ignored；ingest.py 生成
    └── chapters/<专科>/<疾病>.md
```

## 运行 Eval

```bash
# in-scope 全量 eval（约 15 分钟，调用 LLM judge）
./bin/eval.sh

# 越界能力 eval（约 5 分钟，确定性评分，无 LLM judge）
./bin/eval_oob.sh
```

## 专科路由

| 专科 | 覆盖疾病 | 关键词示例 |
|------|---------|-----------|
| cardiology | 高血压、心衰、冠心病、心律失常 | 血压、心衰、冠心病、心绞痛、房颤 |
| endocrine | 2型糖尿病、血脂、甲状腺、痛风、肥胖 | 血糖、糖尿病、胰岛素、血脂、痛风 |
| respiratory | 哮喘、COPD、肺炎 | 哮喘、慢阻肺、喘息、肺炎、咳嗽 |
| digestive | 消化道疾病、IBD、肝病 | 胃、肠、肝硬化、乙肝、腹泻 |
| renal | 慢性肾病、肾炎 | 肾病、蛋白尿、肌酐、肾功能 |
| hematology | 贫血 | 贫血、血红蛋白、缺铁 |
| infectious | 感染性疾病 | 感染、发热、肺结核、乙肝 |
| rheumatology | 类风湿关节炎、SLE、骨质疏松 | 关节痛、类风湿、狼疮、骨质疏松 |

## 越界分类

| 类别 | 说明 | 示例 |
|------|------|------|
| A 外科/介入决策 | 搭桥/支架/移植/透析时机等手术指征 | "要放支架吗？" |
| B 肿瘤化疗方案 | 化疗药物选择、剂量、靶向/免疫方案 | "CHOP 还是 R-CHOP？" |
| C 未覆盖专科 | 神内、精神科、儿科、妇产科 | "帕金森怎么康复？" |
| D 无关任务 | 写作、翻译、天气、投资、菜谱等 | "帮我写作文" |

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

1. 写 `knowledge/<专科>/<疾病>.yaml`（或用 `bin/extract.py` 半自动提取）
2. 写 `prompts/sections/<专科>.md`（若新专科）
3. 在 `bin/router.sh` 补对应关键词

## Eval 指标（最新结果）

| 测试集 | 题数 | 指标 | 结果 |
|--------|------|------|------|
| in-scope | 29 | 平均分 / 40 | 39.3（98.3%）✓ |
| in-scope | 29 | 通过率 | 95.6% ✓ |
| OOB | 25 | 拦截准确率 | 100% ✓ |
| OOB | 25 | 无幻觉率 | 100% ✓ |

v1 目标：in-scope 平均 ≥85%（34/40），OOB 拦截 ~100%，grounding ≥90%。

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

## 知识来源

《西氏内科学精要》（Cecil Essentials of Medicine）中文版  
上卷（637 页）+ 下卷（632 页），共 1,269 页  
本机私有处理，生成的 YAML/章节文本不再分发（`pdfs/`、`source/` 已 git-ignored）
