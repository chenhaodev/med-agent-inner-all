# 知识库维护指南

知识库扩展、eval 运行、目录结构详细说明。

---

## 添加新疾病

1. **抽取章节**（如章节 md 缺失）：
   ```bash
   python3 bin/ingest.py    # 按 knowledge/chapters.yaml 的 pdf_page 范围抽取
   ```

2. **生成知识 YAML**：
   ```bash
   python3 bin/extract.py source/chapters/<专科>/<疾病>.md
   # → knowledge/<专科>/<疾病>.yaml
   ```

3. **校验页码**：人工核对 `source_page` 对应印刷页码（folio）；
   ```bash
   python3 bin/audit_pages.py    # 检测漂移
   python3 bin/folio_map.py      # 页码映射
   ```

4. **加金标题**：在 `eval/gold.yaml` 加 1-2 道题（patient + doctor 双 tag），跑单题验证：
   ```bash
   ./bin/eval.sh --id <题目ID>
   ```

5. **新增专科时**：在 `prompts/sections/` 加专科回答指引，在 `bin/router.sh` 加关键词块。

---

## 添加指南叠加

向 `knowledge/<专科>/guidelines/` 下新增 YAML 文件，重启后自动生效：

```bash
knowledge/cardiology/guidelines/心衰指南2024.yaml
```

YAML 格式（`year` 字段必填）：

```yaml
- id: GL_HF_001
  title: 心衰射血分数保留型（HFpEF）血压控制目标
  source: 中国心力衰竭诊断和治疗指南2024
  year: 2024
  source_page: "第 12 页"
  key_points:
    - 血压控制目标 <130/80 mmHg
```

教材与指南冲突以最新指南为准；【依据】同时引用两者。

---

## 静态契约审计

```bash
python3 bin/audit_routing.py    # 0 ERROR / 0 WARN 才可进入 eval
```

检查内容：
- `[ROUTE]`：gold.yaml 里 `expected_domain` 经 router.sh，ERROR=路由到无 YAML 域（知识静默跳过），WARN=路由到次优域
- `[TAG]`：`doctor_must_have_tags` 须在命中 YAML 中作子串找到

退出码 1 时阻断，建议作为 `eval.sh` 前置门禁。

---

## Eval 方法

### in-scope eval

```bash
./bin/eval.sh                   # patient 模式，~50 分钟，147 题
./bin/eval.sh --mode doctor     # doctor 模式，~30 分钟，110 题
./bin/eval.sh --mode both       # 双模式同跑
./bin/eval.sh --id RENAL_CKD_01 # 单题调试
```

评分规范：`eval/judge_prompt.md`（patient）/ `eval/judge_prompt_doctor.md`（doctor）  
通过标准：平均分 ≥34/40（85%），OOB 拦截率 100%。

### 越界 eval

```bash
./bin/eval_oob.sh               # patient 模式，确定性评分，~5 分钟
./bin/eval_oob.sh --mode doctor # doctor 模式
```

### deep eval（核验 + 回炉）

```bash
./bin/eval_deep.sh --mode doctor
```

---

## 专科路由表

| 专科 | 覆盖疾病（已有 YAML） | 关键词示例 |
|------|----------------------|-----------|
| cardiology | 高血压、心衰、冠心病、心律失常、瓣膜病、心包炎、先心病、主动脉夹层 | 血压、心衰、冠心病、心绞痛、房颤、瓣膜、心包、先心病 |
| endocrine | 2型糖尿病、血脂异常、甲状腺、痛风、肥胖、垂体、肾上腺、营养支持 | 血糖、糖尿病、胰岛素、血脂、痛风、垂体、肾上腺、营养支持 |
| respiratory | 哮喘、COPD、肺炎、ILD、睡眠呼吸暂停、胸腔积液、肺癌、ARDS | 哮喘、慢阻肺、喘息、肺炎、睡眠呼吸暂停、胸水、肺癌、ARDS |
| digestive | 消化道疾病、IBD、肝病、肝炎、食管/GERD、黄疸 | 胃、肠、肝硬化、乙肝、腹泻、反流、黄疸 |
| renal | 慢性肾病、肾炎、AKI、电解质紊乱、肾血管性疾病 | 肾病、蛋白尿、肌酐、肾功能、TTP/HUS |
| hematology | 贫血、骨髓增殖性肿瘤（CML/PV/ET/PMF） | 贫血、血红蛋白、缺铁、CML、伊马替尼、骨髓纤维化 |
| infectious | 感染性疾病、发热/FUO、社区获得性肺炎、皮肤软组织感染 | 感染、发热、肺结核、乙肝、疟疾、蜂窝织炎、坏死性筋膜炎 |
| rheumatology | 类风湿关节炎、SLE、骨质疏松、强直性脊柱炎、系统性硬化、血管炎 | 关节痛、类风湿、狼疮、骨质疏松、强直性脊柱炎、硬皮病、血管炎 |
| neurology | 脑卒中、运动障碍、痴呆、癫痫、头痛、睡眠障碍 | 卒中、帕金森、痴呆、癫痫、头痛、失眠 |
| oncology | 肺癌、胃肠道癌、乳腺癌、泌尿系癌、肿瘤并发症 | 癌症、肿瘤、靶向治疗、化疗并发症 |
| bone_mineral | 矿物质代谢、代谢性骨病（骨质疏松统一归 rheumatology） | 钙磷代谢、甲旁亢、佝偻病、骨软化 |
| geriatrics | 老年综合评估、衰弱、多病共存 | 老年人、衰弱、跌倒、多重用药 |
| palliative | 姑息治疗、安宁疗护、疼痛管理 | 姑息、安宁、疼痛控制、临终 |
| perioperative | 围手术期内科管理 | 术前评估、围手术期、手术风险 |
| mens_health | 前列腺、勃起功能 | 前列腺、勃起、男性激素 |
| womens_health | 绝经、骨质疏松 | 绝经、更年期、女性激素 |
| substance_use | 酒精/药物依赖与戒断 | 酒精、戒酒、药物依赖、成瘾 |

---

## 目录结构（完整）

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
│   ├── audit_routing.py    # 路由 + 标签契约静态审计（无 LLM，<20s）
│   ├── ingest.py           # PDF → source/chapters/<专科>/<疾病>.md（含页码标注）
│   └── extract.py          # 章节 md → knowledge YAML（DeepSeek 结构化提取）
├── knowledge/              # 97 个 YAML，覆盖 Tier1/2/3 全部病种
│   ├── cardiology/         # hypertension / heart_failure / cad / arrhythmia
│   │   │                   # valve_disease / pericardial / congenital_hd / other_cardiac
│   │   └── guidelines/     # 高血压防治指南2024.yaml 等指南叠加层
│   ├── endocrine/          # diabetes_t2 / dyslipidemia / thyroid / gout / obesity
│   │                       # pituitary / adrenal / nutrition
│   ├── respiratory/        # asthma / copd / pneumonia / ild
│   │                       # sleep_breathing / pleural / lung_tumor / critical_care
│   ├── digestive/          # gi / ibd / liver / hepatitis / esophagus / jaundice
│   ├── renal/              # ckd / nephritis / aki / electrolytes / renal_vascular
│   ├── hematology/         # anemia / bleeding_disorders / thrombosis / lymphocyte / myeloid_clonal
│   ├── infectious/         # general / hiv / uti / sepsis / cns_infection
│   │                       # fever / lower_resp_infection / skin_soft_tissue
│   ├── rheumatology/       # ra / sle / osteoporosis / oa / spa / systemic_sclerosis / vasculitis
│   ├── neurology/          # stroke / movement_disorders / dementia / epilepsy / headache_pain
│   │                       # sleep_disorders / mood_behavior
│   ├── oncology/           # lung_cancer / gi_cancer / breast_cancer / gu_cancer
│   │                       # tumor_complications / tumor_treatment_principles
│   ├── bone_mineral/       # bone_physiology / mineral_disorders / metabolic_bone
│   ├── geriatrics/         # elderly_care
│   ├── palliative/         # palliative_care
│   ├── perioperative/      # periop_management
│   ├── mens_health/        # mens_health
│   ├── womens_health/      # womens_health
│   └── substance_use/      # alcohol_drugs
├── prompts/
│   ├── system_base.md          # patient 模式角色设定 + 安全红线
│   ├── system_doctor.md        # doctor 模式角色设定
│   ├── output_schema.md        # patient 5 段式输出规范
│   ├── output_schema_doctor.md # doctor 5 段式输出规范（含证据等级标注要求）
│   ├── oob_templates.md        # patient 越界拒答模板（5 类）
│   ├── oob_templates_doctor.md # doctor 越界拒答模板
│   └── sections/               # 17 专科回答指引 + few-shot
├── eval/
│   ├── gold.yaml               # 147 题 in-scope 金标集（patient + doctor 双 tag）
│   ├── oob_gold.yaml           # 30 题越界 eval 集（A/B/C/D/E 类 + 负样本）
│   ├── judge_prompt.md         # patient LLM judge 评分规范
│   └── judge_prompt_doctor.md  # doctor LLM judge 评分规范
└── source/                     # git-ignored；ingest.py 生成
    └── chapters/<专科>/<疾病>.md
```

---

## 知识来源

《西氏内科学精要》（Cecil Essentials of Medicine）中文版  
上卷（637 页）+ 下卷（632 页），共 1,269 页  
本机私有处理；生成的 YAML / 章节文本不再分发（`pdfs/`、`source/` 已 git-ignored）
