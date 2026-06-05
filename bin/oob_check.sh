#!/usr/bin/env bash
# oob_check.sh — 确定性越界检测器（不调 API，<10ms）
# 用法：./bin/oob_check.sh "问题文本"
#
# 输出：
#   in_scope                          — 进入正常管道
#   out_of_scope:surgery              — A类：外科手术/介入决策
#   out_of_scope:chemo                — B类：肿瘤化疗具体剂量方案
#   out_of_scope:uncovered_specialty  — C类：未覆盖专科
#   out_of_scope:unrelated            — D类：完全无关任务

set -euo pipefail

if [[ $# -ge 1 ]]; then
  QUESTION="$1"
else
  QUESTION="$(cat)"
fi

if [[ -z "$QUESTION" ]]; then
  echo "in_scope"
  exit 0
fi

# ─── A 类：外科手术 / 介入决策（应拒答）────────────────────
# 本项目 in-scope 是内科常见病管理，外科决策属 OOB
KEYWORDS_SURGERY="搭桥手术|冠状动脉搭桥|CABG|心脏手术|换瓣|瓣膜手术|心脏移植|\
肾移植|肝移植|器官移植|骨髓移植|造血干细胞移植|\
支架手术|放支架|放不放支架|要不要手术|手术指征|\
介入治疗|冠脉介入|射频消融|导管消融|心脏消融|\
透析|血液透析|腹膜透析|要不要透析|透析时机|\
手术风险|术前评估|术后护理"

if echo "$QUESTION" | grep -qE "$KEYWORDS_SURGERY"; then
  echo "out_of_scope:surgery"
  exit 0
fi

# ─── B 类：肿瘤化疗具体方案/剂量（应拒答）───────────────────
KEYWORDS_CHEMO="化疗方案|化疗剂量|化疗用什么药|化疗药物选择|化疗后|\
骨髓抑制|升白细胞针|升血小板|G-CSF|\
紫杉醇|顺铂|卡铂|奥沙利铂|伊立替康|吉西他滨|培美曲塞|\
靶向治疗用什么药|靶向治疗用哪个药|免疫治疗剂量|PD-1|PD-L1|CTLA-4|\
CAR-T|细胞免疫治疗|肿瘤免疫治疗方案|\
放疗剂量|放化疗方案|化放疗|同步放化疗|\
CHOP|R-CHOP|利妥昔单抗|淋巴瘤.*方案|方案.*淋巴瘤|ABVD|BEP|FOLFOX|FOLFIRI|EC方案|AC方案"

if echo "$QUESTION" | grep -qE "$KEYWORDS_CHEMO"; then
  echo "out_of_scope:chemo"
  exit 0
fi

# ─── C 类：未覆盖专科（应拒答）─────────────────────────────
# 本项目覆盖：心血管/内分泌/呼吸/消化/肾/血液/感染/风湿骨
# 未覆盖：神经内科（脑卒中除外共病提及）、精神科、儿科、妇产科、外科
KEYWORDS_UNCOVERED="帕金森|帕金森病|阿尔茨海默|老年痴呆|血管性痴呆|路易体痴呆|\
额颞叶痴呆|脑梗后遗症|脑卒中康复|脑出血康复|\
精神分裂|躁郁症|双相情感|抑郁症|焦虑症|心理治疗|精神科|\
儿童|小孩|小儿|婴幼儿|新生儿|儿科|宝宝|孩子.*发热|孩子.*发烧|\
妇科|产科|妊娠期|孕期|孕妇|哺乳期|月经不调|子宫|卵巢|\
骨科手术|关节置换|脊柱手术|骨折固定"

if echo "$QUESTION" | grep -qE "$KEYWORDS_UNCOVERED"; then
  echo "out_of_scope:uncovered_specialty"
  exit 0
fi

# ─── D 类：完全无关任务（应礼貌拒答）───────────────────────
KEYWORDS_WRITING="作文|写一篇文章|帮我写文|帮我写篇|写代码|帮我编程|帮我写程序"
KEYWORDS_FINANCE="股票|基金|理财|投资建议|炒股"
KEYWORDS_WEATHER="天气怎么样|天气如何|天气预报|查天气|今天.*天气|明天.*天气"
KEYWORDS_COOKING="菜谱|烹饪方法|怎么做菜|做菜|食谱|红烧|清蒸|怎么烹饪|怎么做.*肉|怎么煮|炖.*汤"
KEYWORDS_TRANSLATE="翻译成英文|翻译成中文|请翻译|帮我翻译"

if echo "$QUESTION" | grep -qE "$KEYWORDS_WRITING|$KEYWORDS_FINANCE|$KEYWORDS_WEATHER|$KEYWORDS_COOKING|$KEYWORDS_TRANSLATE"; then
  echo "out_of_scope:unrelated"
  exit 0
fi

# ─── 通过所有检测 → in_scope ──────────────────────────────
echo "in_scope"
