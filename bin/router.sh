#!/usr/bin/env bash
# router.sh — 将问题分类到 专科:疾病 标签（最多 2 个）
# 用法：./bin/router.sh "问题文本"
# 输出：空格分隔的 specialty:disease 标签，例如 "cardiology:hypertension"
#
# 专科列表（与教材部分对齐）：
#   cardiology      心血管（第二部分）
#   endocrine       内分泌代谢（第五部分）
#   respiratory     呼吸（第三部分）
#   digestive       消化含肝（第四部分）
#   renal           肾（第六部分）
#   hematology      血液（第七部分）
#   infectious      感染（第八部分）
#   rheumatology    风湿骨（第十部分）

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(dirname "$SCRIPT_DIR")"

if [[ $# -ge 1 ]]; then
  QUESTION="$1"
else
  QUESTION="$(cat)"
fi

if [[ -z "$QUESTION" ]]; then
  echo "cardiology:general"
  exit 0
fi

# ─── 关键词路由表（专科:疾病 粒度）──────────────────────────
# v2：扩展至全书 18 专科

# 心血管
KW_CARDIOLOGY_HYPERTENSION="高血压|血压高|降压|血压控制|收缩压|舒张压|高压|低压|降压药"
KW_CARDIOLOGY_HEART_FAILURE="心衰|心力衰竭|心功能不全|射血分数|BNP|NT-proBNP|喘|端坐呼吸|下肢水肿.*心"
KW_CARDIOLOGY_CAD="冠心病|冠状动脉|心绞痛|心肌梗死|心梗|胸痛|心肌缺血|稳定型|不稳定型|戒烟|尼古丁替代|尼古丁贴片|戒烟方法|帮助戒烟"
KW_CARDIOLOGY_ARRHYTHMIA="心律失常|房颤|心房颤动|早搏|室速|室颤|心动过速|心动过缓|心跳不规则|心跳乱"
KW_CARDIOLOGY_GENERAL="心脏病|心脏|心血管|心脏功能|心电图"

# 内分泌代谢
KW_ENDOCRINE_DIABETES="糖尿病|血糖|高血糖|低血糖|胰岛素|降糖药|糖化血红蛋白|HbA1c|空腹血糖|餐后血糖|二甲双胍|胰岛"
KW_ENDOCRINE_THYROID="甲状腺|甲亢|甲减|甲状腺功能|促甲状腺|T3|T4|TSH|甲状腺素|甲状腺结节"
KW_ENDOCRINE_OBESITY="肥胖|减重|减肥|BMI|体重超标|代谢综合征"
KW_ENDOCRINE_GOUT="痛风|高尿酸|尿酸|尿酸盐|别嘌醇|非布司他"
KW_ENDOCRINE_LIPID="血脂|高血脂|胆固醇|LDL|HDL|甘油三酯|他汀|降脂"
KW_ENDOCRINE_GENERAL="内分泌|激素|代谢|肾上腺|垂体|胰腺"

# 呼吸
KW_RESPIRATORY_COPD="慢阻肺|COPD|慢性阻塞性肺疾病|肺气肿|慢性支气管炎|气流受限|肺功能下降"
KW_RESPIRATORY_ASTHMA="哮喘|支气管哮喘|气喘|喘息|过敏性哮喘|哮喘发作|吸入激素"
KW_RESPIRATORY_PNEUMONIA="肺炎|肺部感染|社区获得性肺炎|医院获得性|肺炎球菌|肺部阴影"
KW_RESPIRATORY_GENERAL="咳嗽|咳痰|呼吸困难|气短|气急|肺|呼吸|支气管|氧饱和度"

# 消化含肝
KW_DIGESTIVE_LIVER="肝炎|乙肝|丙肝|肝硬化|肝功能|肝纤维化|转氨酶|ALT|AST|胆红素|肝癌风险|抗病毒"
KW_DIGESTIVE_IBD="炎症性肠病|克罗恩|溃疡性结肠炎|肠炎|肠道炎症|IBD"
KW_DIGESTIVE_GI="胃炎|消化性溃疡|胃溃疡|十二指肠溃疡|幽门螺杆菌|HP感染|反流|胃食管反流|GERD|消化不良"
KW_DIGESTIVE_GENERAL="消化|肠道|胃肠|腹泻|便秘|腹痛|腹胀|大便|肠胃"

# 肾
KW_RENAL_CKD="慢性肾病|CKD|慢性肾功能不全|肾功能减退|肌酐升高|肾小球滤过率|GFR|蛋白尿"
KW_RENAL_NEPHRITIS="肾炎|肾小球肾炎|IgA肾病|膜性肾病"
KW_RENAL_GENERAL="肾|尿蛋白|血尿|肾功能|尿毒症|肾脏病"

# 血液
KW_HEMATOLOGY_ANEMIA="贫血|血红蛋白低|缺铁性贫血|恶性贫血|溶血性贫血|地中海贫血|再生障碍性贫血"
KW_HEMATOLOGY_GENERAL="血液病|白血病|淋巴瘤|骨髓瘤|血小板减少|白细胞低|血细胞|骨髓"

# 感染
KW_INFECTIOUS_GENERAL="感染|发烧|发热|细菌感染|病毒感染|抗生素|抗感染|败血症|脓毒症|结核|TB|艾滋|HIV|梅毒"

# 风湿骨
KW_RHEUMATOLOGY_RA="类风湿|类风湿关节炎|RA|关节肿胀|晨僵|抗CCP|类风湿因子|RF"
KW_RHEUMATOLOGY_SLE="系统性红斑狼疮|SLE|蝴蝶斑|狼疮肾炎"
KW_RHEUMATOLOGY_OSTEOPOROSIS="骨质疏松|骨密度|骨折风险|钙|维生素D|双膦酸盐|T值"
KW_RHEUMATOLOGY_GENERAL="风湿|关节炎|关节痛|骨关节炎|痛风性关节|脊柱关节炎|强直性脊柱炎|干燥综合征|系统性硬化|血管炎"

# 肿瘤（科普级别，不含化疗方案）
KW_ONCOLOGY_LUNG="肺癌|肺部肿瘤|非小细胞肺癌|小细胞肺癌|肺结节.*恶性"
KW_ONCOLOGY_GI="肠癌|结直肠癌|胃癌|食管癌|胰腺癌|肝癌"
KW_ONCOLOGY_BREAST="乳腺癌|乳腺肿瘤"
KW_ONCOLOGY_LYMPHOMA="淋巴瘤|霍奇金淋巴瘤|非霍奇金"
KW_ONCOLOGY_GENERAL="肿瘤|癌症|癌|靶向治疗副作用|化疗副作用|化疗后.*恶心|化疗后.*疲乏|肿瘤营养|肿瘤患者.*饮食|癌症患者"

# 神经内科
KW_NEUROLOGY_STROKE="脑卒中|脑梗|脑出血|中风|偏瘫|失语|吞咽困难.*脑|脑梗康复|脑血管"
KW_NEUROLOGY_PARKINSON="帕金森|帕金森病|震颤|运动迟缓|肌强直|帕金森康复"
KW_NEUROLOGY_DEMENTIA="痴呆|阿尔茨海默|老年痴呆|记忆障碍|认知障碍|血管性痴呆"
KW_NEUROLOGY_EPILEPSY="癫痫|癫痫发作|抗癫痫|惊厥"
KW_NEUROLOGY_HEADACHE="偏头痛|头痛|紧张型头痛|丛集性头痛"
KW_NEUROLOGY_SLEEP="失眠|睡眠障碍|睡不着|入睡困难|睡眠呼吸暂停"
KW_NEUROLOGY_GENERAL="神经|肌无力|麻木|感觉异常|眩晕|头晕|意识障碍|运动障碍|神经病变"

# 精神/心理（归入神经科路由）
KW_NEUROLOGY_PSYCH="抑郁症|抑郁|焦虑症|焦虑|双相情感障碍|躁郁症|精神分裂|心理健康|情绪障碍"

# 妇科健康
KW_WOMENS_HEALTH="月经不调|痛经|更年期|绝经|围绝经期|多囊卵巢|宫颈|卵巢|乳腺健康|女性健康|骨盆底"

# 男性健康
KW_MENS_HEALTH="前列腺|ED|勃起功能|男性健康|睾酮|男性性功能|前列腺增生"

# 骨代谢矿物质
KW_BONE_MINERAL="骨代谢|维生素D缺乏|甲状旁腺|钙代谢|磷代谢|代谢性骨病|佝偻病|骨软化"

# 老年医学
KW_GERIATRICS="老年患者|老年人用药|老年综合评估|衰弱|跌倒.*老人|老年痴呆.*管理|多重用药"

# 姑息治疗
KW_PALLIATIVE="姑息治疗|缓和医疗|临终关怀|安宁疗护|终末期|疼痛控制.*癌症|生命末期"

# 物质滥用
KW_SUBSTANCE="酗酒|酒精依赖|戒酒|酒精性.*肝|药物滥用|成瘾"

# 围术期
KW_PERIOPERATIVE="术前评估|围手术期|围术期管理|手术前.*内科|手术风险.*内科"

# ─── 匹配逻辑 ────────────────────────────────────────────────
matched=()

check() {
  local tag="$1" pattern="$2"
  if echo "$QUESTION" | grep -qE "$pattern"; then
    matched+=("$tag")
  fi
}

# 按疾病粒度检查（越具体越先检查）
check "cardiology:hypertension"    "$KW_CARDIOLOGY_HYPERTENSION"
check "cardiology:heart_failure"   "$KW_CARDIOLOGY_HEART_FAILURE"
check "cardiology:cad"             "$KW_CARDIOLOGY_CAD"
check "cardiology:arrhythmia"      "$KW_CARDIOLOGY_ARRHYTHMIA"

check "endocrine:diabetes_t2"      "$KW_ENDOCRINE_DIABETES"
check "endocrine:thyroid"          "$KW_ENDOCRINE_THYROID"
check "endocrine:obesity"          "$KW_ENDOCRINE_OBESITY"
check "endocrine:gout"             "$KW_ENDOCRINE_GOUT"
check "endocrine:dyslipidemia"     "$KW_ENDOCRINE_LIPID"

check "respiratory:copd"           "$KW_RESPIRATORY_COPD"
check "respiratory:asthma"         "$KW_RESPIRATORY_ASTHMA"
check "respiratory:pneumonia"      "$KW_RESPIRATORY_PNEUMONIA"

check "digestive:liver"            "$KW_DIGESTIVE_LIVER"
check "digestive:ibd"              "$KW_DIGESTIVE_IBD"
check "digestive:gi"               "$KW_DIGESTIVE_GI"

check "renal:ckd"                  "$KW_RENAL_CKD"
check "renal:nephritis"            "$KW_RENAL_NEPHRITIS"

check "hematology:anemia"          "$KW_HEMATOLOGY_ANEMIA"

check "infectious:general"         "$KW_INFECTIOUS_GENERAL"

check "rheumatology:ra"            "$KW_RHEUMATOLOGY_RA"
check "rheumatology:sle"           "$KW_RHEUMATOLOGY_SLE"
check "rheumatology:osteoporosis"  "$KW_RHEUMATOLOGY_OSTEOPOROSIS"

# 肿瘤
check "oncology:lung_cancer"       "$KW_ONCOLOGY_LUNG"
check "oncology:gi_cancer"         "$KW_ONCOLOGY_GI"
check "oncology:breast_cancer"     "$KW_ONCOLOGY_BREAST"
check "oncology:lymphocyte"        "$KW_ONCOLOGY_LYMPHOMA"

# 神经（含精神科症状）
check "neurology:stroke"           "$KW_NEUROLOGY_STROKE"
check "neurology:movement_disorders" "$KW_NEUROLOGY_PARKINSON"
check "neurology:dementia"         "$KW_NEUROLOGY_DEMENTIA"
check "neurology:epilepsy"         "$KW_NEUROLOGY_EPILEPSY"
check "neurology:headache_pain"    "$KW_NEUROLOGY_HEADACHE"
check "neurology:sleep_disorders"  "$KW_NEUROLOGY_SLEEP"
check "neurology:mood_behavior"    "$KW_NEUROLOGY_PSYCH"

# 其他专科
check "womens_health:womens_health" "$KW_WOMENS_HEALTH"
check "mens_health:mens_health"     "$KW_MENS_HEALTH"
check "bone_mineral:osteoporosis"   "$KW_BONE_MINERAL"
check "geriatrics:elderly_care"     "$KW_GERIATRICS"
check "palliative:palliative_care"  "$KW_PALLIATIVE"
check "substance_use:alcohol_drugs" "$KW_SUBSTANCE"
check "perioperative:periop_management" "$KW_PERIOPERATIVE"

# 专科级兜底（如果疾病级未命中）
if [[ ${#matched[@]} -eq 0 ]]; then
  check "cardiology:general"    "$KW_CARDIOLOGY_GENERAL"
  check "endocrine:general"     "$KW_ENDOCRINE_GENERAL"
  check "respiratory:general"   "$KW_RESPIRATORY_GENERAL"
  check "digestive:general"     "$KW_DIGESTIVE_GENERAL"
  check "renal:general"         "$KW_RENAL_GENERAL"
  check "hematology:general"    "$KW_HEMATOLOGY_GENERAL"
  check "rheumatology:general"  "$KW_RHEUMATOLOGY_GENERAL"
  check "oncology:general"      "$KW_ONCOLOGY_GENERAL"
  check "neurology:general"     "$KW_NEUROLOGY_GENERAL"
fi

# ─── DeepSeek 兜底分类 ──────────────────────────────────────
if [[ ${#matched[@]} -eq 0 ]]; then
  if [[ -f "$ROOT_DIR/.env" ]]; then
    source "$ROOT_DIR/.env" 2>/dev/null || true
  fi

  if [[ -n "${DEEPSEEK_API_KEY:-}" ]]; then
    DOMAINS_LIST="cardiology:hypertension, cardiology:heart_failure, cardiology:cad, cardiology:arrhythmia, cardiology:valve_disease, endocrine:diabetes_t2, endocrine:thyroid, endocrine:dyslipidemia, endocrine:gout, endocrine:obesity, respiratory:copd, respiratory:asthma, respiratory:pneumonia, respiratory:ild, digestive:liver, digestive:gi, digestive:ibd, digestive:hepatitis, renal:ckd, renal:nephritis, renal:aki, hematology:anemia, hematology:bleeding_disorders, infectious:general, infectious:hiv, infectious:sepsis, rheumatology:ra, rheumatology:sle, rheumatology:osteoporosis, rheumatology:gout, oncology:lung_cancer, oncology:gi_cancer, oncology:breast_cancer, oncology:tumor_complications, neurology:stroke, neurology:movement_disorders, neurology:dementia, neurology:epilepsy, neurology:headache_pain, neurology:sleep_disorders, neurology:mood_behavior, womens_health:womens_health, mens_health:mens_health, bone_mineral:osteoporosis, geriatrics:elderly_care, palliative:palliative_care, substance_use:alcohol_drugs, perioperative:periop_management"

    CLASSIFY_PAYLOAD=$(python3 -c "
import json, sys
question = sys.argv[1]
domains = sys.argv[2]
payload = {
  'model': 'deepseek-chat',
  'temperature': 0,
  'max_tokens': 40,
  'messages': [
    {'role': 'system', 'content': f'你是一个医学分类器。从以下专科:疾病标签中选出1-2个最匹配的，只输出标签，用空格分隔，不要其他文字。\\n标签：{domains}'},
    {'role': 'user', 'content': question}
  ]
}
print(json.dumps(payload))
" "$QUESTION" "$DOMAINS_LIST" 2>/dev/null)

    if [[ -n "$CLASSIFY_PAYLOAD" ]]; then
      CLASSIFIED=$(echo "$CLASSIFY_PAYLOAD" | "$SCRIPT_DIR/call_deepseek.sh" 2>/dev/null | tr -s ' ' | xargs) || true
      VALID_TAGS="cardiology:hypertension cardiology:heart_failure cardiology:cad cardiology:arrhythmia cardiology:valve_disease cardiology:pericardial cardiology:congenital_hd cardiology:other_cardiac cardiology:general endocrine:diabetes_t2 endocrine:thyroid endocrine:obesity endocrine:gout endocrine:dyslipidemia endocrine:pituitary endocrine:adrenal endocrine:nutrition endocrine:general respiratory:copd respiratory:asthma respiratory:pneumonia respiratory:ild respiratory:pulmonary_vascular respiratory:sleep_breathing respiratory:pleural respiratory:lung_tumor respiratory:critical_care respiratory:general digestive:liver digestive:ibd digestive:gi digestive:hepatitis digestive:esophagus digestive:pancreas digestive:biliary digestive:jaundice digestive:general renal:ckd renal:nephritis renal:aki renal:electrolytes renal:renal_vascular renal:general hematology:anemia hematology:myeloid_clonal hematology:lymphocyte hematology:bleeding_disorders hematology:thrombosis hematology:general infectious:fever infectious:sepsis infectious:hiv infectious:uti infectious:lower_resp_infection infectious:cns_infection infectious:skin_soft_tissue infectious:general rheumatology:ra rheumatology:sle rheumatology:osteoporosis rheumatology:gout rheumatology:oa rheumatology:vasculitis rheumatology:spa rheumatology:systemic_sclerosis rheumatology:general oncology:lung_cancer oncology:gi_cancer oncology:breast_cancer oncology:gu_cancer oncology:other_solid_tumors oncology:tumor_complications oncology:tumor_treatment_principles oncology:general neurology:stroke neurology:movement_disorders neurology:dementia neurology:epilepsy neurology:headache_pain neurology:sleep_disorders neurology:mood_behavior neurology:dizziness neurology:consciousness neurology:general womens_health:womens_health mens_health:mens_health bone_mineral:osteoporosis bone_mineral:mineral_disorders bone_mineral:metabolic_bone geriatrics:elderly_care palliative:palliative_care substance_use:alcohol_drugs perioperative:periop_management"
      VALID_RESULT=""
      for d in $CLASSIFIED; do
        if echo "$VALID_TAGS" | grep -qw "$d"; then
          VALID_RESULT="$VALID_RESULT $d"
        fi
      done
      VALID_RESULT=$(echo "$VALID_RESULT" | xargs)
      if [[ -n "$VALID_RESULT" ]]; then
        echo "$VALID_RESULT"
        exit 0
      fi
    fi
  fi

  echo "cardiology:general"
  exit 0
fi

# 最多保留 2 个标签
if [[ ${#matched[@]} -gt 2 ]]; then
  matched=("${matched[@]:0:2}")
fi

echo "${matched[*]}"
