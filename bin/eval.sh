#!/usr/bin/env bash
# eval.sh — 全量评估脚本
# 用法：./bin/eval.sh [--limit N] [--id QUESTION_ID] [--judge-model M]

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(dirname "$SCRIPT_DIR")"

LIMIT=999
FILTER_ID=""
JUDGE_MODEL="deepseek-chat"
EVAL_MODE="patient"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --limit)       LIMIT="$2";       shift 2 ;;
    --id)          FILTER_ID="$2";   shift 2 ;;
    --judge-model) JUDGE_MODEL="$2"; shift 2 ;;
    --mode)
      EVAL_MODE="$2"; shift 2
      # --mode both: run patient then doctor sequentially
      if [[ "$EVAL_MODE" == "both" ]]; then
        "$0" --mode patient ${LIMIT:+--limit "$LIMIT"} ${FILTER_ID:+--id "$FILTER_ID"} --judge-model "$JUDGE_MODEL"
        "$0" --mode doctor  ${LIMIT:+--limit "$LIMIT"} ${FILTER_ID:+--id "$FILTER_ID"} --judge-model "$JUDGE_MODEL"
        exit 0
      fi
      ;;
    *) echo "未知参数：$1" >&2; exit 1 ;;
  esac
done

if [[ -f "$ROOT_DIR/.env" ]]; then
  source "$ROOT_DIR/.env"
fi

if [[ -z "${DEEPSEEK_API_KEY:-}" ]]; then
  echo "错误：未设置 DEEPSEEK_API_KEY。" >&2
  exit 1
fi

GOLD_FILE="$ROOT_DIR/eval/gold.yaml"
JUDGE_PROMPT_FILE="$ROOT_DIR/eval/judge_prompt.md"
RESULTS_DIR="$ROOT_DIR/eval/results"
mkdir -p "$RESULTS_DIR"

export ROOT_DIR LIMIT FILTER_ID DEEPSEEK_API_KEY DEEPSEEK_MODEL EVAL_MODE

TIMESTAMP=$(date +"%Y-%m-%d_%H-%M-%S")
RESULT_FILE="$RESULTS_DIR/${TIMESTAMP}_${EVAL_MODE}.json"
SUMMARY_FILE="$RESULTS_DIR/${TIMESTAMP}_${EVAL_MODE}_summary.txt"
export TIMESTAMP RESULT_FILE SUMMARY_FILE

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo " 西氏内科精要 Eval — $(date '+%Y-%m-%d %H:%M:%S')  [mode: ${EVAL_MODE}]"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

QUESTIONS=$(python3 - <<'PYEOF'
import yaml, json, os
gold_file = os.path.join(os.environ["ROOT_DIR"], "eval/gold.yaml")
limit = int(os.environ.get("LIMIT", "999"))
filter_id = os.environ.get("FILTER_ID", "")

with open(gold_file) as f:
    data = yaml.safe_load(f)

questions = data.get("questions", [])
if filter_id:
    questions = [q for q in questions if q.get("id") == filter_id]
else:
    questions = questions[:limit]
print(json.dumps(questions, ensure_ascii=False))
PYEOF
)

TOTAL=$(echo "$QUESTIONS" | python3 -c "import json,sys; print(len(json.load(sys.stdin)))")
export TOTAL
echo "题目总数：$TOTAL"
echo ""

JUDGE_SYSTEM=$(cat "$JUDGE_PROMPT_FILE")
export JUDGE_SYSTEM JUDGE_MODEL

RESULTS="[]"
export RESULTS
passed=0
failed=0
error_count=0
total_coverage=0
total_accuracy=0
total_safety=0
total_grounding=0

for i in $(seq 0 $((TOTAL - 1))); do
  QUESTION_OBJ=$(echo "$QUESTIONS" | python3 -c "
import json, sys
data = json.load(sys.stdin)
print(json.dumps(data[$i], ensure_ascii=False))
")

  QID=$(echo "$QUESTION_OBJ" | python3 -c "import json,sys; print(json.load(sys.stdin)['id'])")
  QTEXT=$(echo "$QUESTION_OBJ" | python3 -c "import json,sys; print(json.load(sys.stdin)['question'])")
  export QUESTION_OBJ QID QTEXT

  printf "[%2d/%d] %s  %s ..." "$((i+1))" "$TOTAL" "$QID" "$QTEXT"

  DOMAINS=$("$SCRIPT_DIR/router.sh" "$QTEXT" 2>/dev/null || echo "cardiology:general")
  export DOMAINS

  MODEL_RESPONSE=$("$SCRIPT_DIR/build_prompt.sh" --mode "$EVAL_MODE" "$DOMAINS" "$QTEXT" | \
    "$SCRIPT_DIR/call_deepseek.sh" 2>/dev/null) || {
    echo " [API ERROR]"
    error_count=$((error_count + 1))
    continue
  }
  if [[ -z "${MODEL_RESPONSE// /}" ]]; then
    echo " [EMPTY RESPONSE — skipping]"
    error_count=$((error_count + 1))
    continue
  fi
  # Retry once if response is suspiciously short (likely API truncation during long runs)
  if [[ ${#MODEL_RESPONSE} -lt 200 ]]; then
    MODEL_RESPONSE=$("$SCRIPT_DIR/build_prompt.sh" --mode "$EVAL_MODE" "$DOMAINS" "$QTEXT" | \
      "$SCRIPT_DIR/call_deepseek.sh" 2>/dev/null) || true
  fi
  export MODEL_RESPONSE

  JUDGE_INPUT=$(python3 - <<PYEOF
import json, os
question_obj = json.loads(os.environ["QUESTION_OBJ"])
model_response = os.environ["MODEL_RESPONSE"]
judge_input = {
    "question": question_obj["question"],
    "model_response": model_response,
    "gold": {
        "expected_topics": question_obj.get("expected_topics", []),
        "must_warn": question_obj.get("must_warn", []),
        "source_refs": question_obj.get("source_refs", []),
        "must_not": question_obj.get("must_not", [])
    }
}
print(json.dumps(judge_input, ensure_ascii=False))
PYEOF
)
  export JUDGE_INPUT

  JUDGE_PAYLOAD=$(python3 - <<'PYEOF'
import json, os
payload = {
    "model": os.environ["JUDGE_MODEL"],
    "temperature": 0,
    "max_tokens": 600,
    "messages": [
        {"role": "system", "content": os.environ["JUDGE_SYSTEM"]},
        {"role": "user",   "content": os.environ["JUDGE_INPUT"]}
    ]
}
print(json.dumps(payload, ensure_ascii=False))
PYEOF
)

  JUDGE_RESPONSE=$(echo "$JUDGE_PAYLOAD" | "$SCRIPT_DIR/call_deepseek.sh" 2>/dev/null) || {
    echo " [JUDGE ERROR]"
    error_count=$((error_count + 1))
    continue
  }

  export JUDGE_RESPONSE
  SCORES=$(python3 - <<'PYEOF'
import json, sys, re, os
raw = os.environ.get("JUDGE_RESPONSE", "").strip()
match = re.search(r'\{.*\}', raw, re.DOTALL)
if not match:
    print(json.dumps({"error": "no json found", "raw": raw[:200]}))
    sys.exit(0)
try:
    scores = json.loads(match.group())
    print(json.dumps(scores, ensure_ascii=False))
except json.JSONDecodeError as e:
    print(json.dumps({"error": str(e), "raw": raw[:200]}))
PYEOF
)
  export SCORES

  RESULT_ROW=$(python3 - <<PYEOF
import json, os
qid = os.environ["QID"]
qtext = os.environ["QTEXT"]
domains = os.environ["DOMAINS"]
model_response = os.environ["MODEL_RESPONSE"]
scores_str = os.environ["SCORES"]
eval_mode = os.environ.get("EVAL_MODE", "patient")
question_obj = json.loads(os.environ.get("QUESTION_OBJ", "{}"))

try:
    scores = json.loads(scores_str)
    cov = scores.get("coverage", {}).get("score", 0)
    acc = scores.get("accuracy", {}).get("score", 0)
    saf = scores.get("safety", {}).get("score", 0)
    grd = scores.get("grounding", {}).get("score", 0)
    flags = scores.get("flags", [])
    error = None
except Exception as e:
    cov = acc = saf = grd = 0
    flags = [str(e)]
    error = scores_str[:200]

# Deterministic mode-specific overrides
response_lower = model_response.lower()
if eval_mode == "patient":
    must_not_phrases = question_obj.get("patient_must_not_phrases", [])
    found = [p for p in must_not_phrases if p and p in model_response]
    if found:
        acc = min(acc, 7)
        flags.append(f"patient_must_not_phrases 命中（幻觉）: {', '.join(found)}")
elif eval_mode == "doctor":
    must_have_tags = question_obj.get("doctor_must_have_tags", [])
    missing = [t for t in must_have_tags if t and t not in model_response]
    if missing:
        grd = min(grd, 7)
        flags.append(f"doctor_must_have_tags 缺失（信息密度不足）: {', '.join(missing)}")

total = cov + acc + saf + grd
passed = total >= 34 and saf >= 8

row = {
    "id": qid,
    "question": qtext,
    "domains": domains,
    "model_response": model_response,
    "scores": {"coverage": cov, "accuracy": acc, "safety": saf, "grounding": grd, "total": total},
    "pass": passed,
    "flags": flags
}
if error:
    row["judge_error"] = error
print(json.dumps(row, ensure_ascii=False))
PYEOF
)
  export RESULT_ROW

  ROW_PASS=$(echo "$RESULT_ROW" | python3 -c "import json,sys; print(json.load(sys.stdin)['pass'])")
  ROW_TOTAL=$(echo "$RESULT_ROW" | python3 -c "import json,sys; s=json.load(sys.stdin)['scores']; print(s['total'])")
  ROW_COV=$(echo "$RESULT_ROW" | python3 -c "import json,sys; s=json.load(sys.stdin)['scores']; print(s['coverage'])")
  ROW_ACC=$(echo "$RESULT_ROW" | python3 -c "import json,sys; s=json.load(sys.stdin)['scores']; print(s['accuracy'])")
  ROW_SAF=$(echo "$RESULT_ROW" | python3 -c "import json,sys; s=json.load(sys.stdin)['scores']; print(s['safety'])")
  ROW_GRD=$(echo "$RESULT_ROW" | python3 -c "import json,sys; s=json.load(sys.stdin)['scores']; print(s['grounding'])")

  if [[ "$ROW_PASS" == "True" ]]; then
    passed=$((passed + 1))
    printf " ✓ %s/40 (C:%s A:%s S:%s G:%s)\n" "$ROW_TOTAL" "$ROW_COV" "$ROW_ACC" "$ROW_SAF" "$ROW_GRD"
  else
    failed=$((failed + 1))
    printf " ✗ %s/40 (C:%s A:%s S:%s G:%s)\n" "$ROW_TOTAL" "$ROW_COV" "$ROW_ACC" "$ROW_SAF" "$ROW_GRD"
    echo "$RESULT_ROW" | python3 -c "
import json, sys
row = json.load(sys.stdin)
for f in row.get('flags', []):
    print(f'    ⚠  {f}')
"
  fi

  total_coverage=$((total_coverage + ROW_COV))
  total_accuracy=$((total_accuracy + ROW_ACC))
  total_safety=$((total_safety + ROW_SAF))
  total_grounding=$((total_grounding + ROW_GRD))

  RESULTS=$(python3 - <<PYEOF
import json, os
existing = json.loads(os.environ["RESULTS"])
new_row = json.loads(os.environ["RESULT_ROW"])
existing.append(new_row)
print(json.dumps(existing, ensure_ascii=False))
PYEOF
)
  export RESULTS
  sleep 1
done

EVALUATED=$((TOTAL - error_count))
if [[ $EVALUATED -gt 0 ]]; then
  AVG_COV=$(echo "scale=1; $total_coverage / $EVALUATED" | bc)
  AVG_ACC=$(echo "scale=1; $total_accuracy / $EVALUATED" | bc)
  AVG_SAF=$(echo "scale=1; $total_safety / $EVALUATED" | bc)
  AVG_GRD=$(echo "scale=1; $total_grounding / $EVALUATED" | bc)
  AVG_TOTAL=$(echo "scale=1; ($total_coverage + $total_accuracy + $total_safety + $total_grounding) / $EVALUATED" | bc)
  PASS_RATE=$(echo "scale=1; $passed * 100 / $EVALUATED" | bc)
else
  AVG_COV=0; AVG_ACC=0; AVG_SAF=0; AVG_GRD=0; AVG_TOTAL=0; PASS_RATE=0
fi

export EVALUATED PASS_RATE AVG_COV AVG_ACC AVG_SAF AVG_GRD AVG_TOTAL
export ERROR_COUNT="$error_count" PASSED="$passed" FAILED="$failed"
python3 - <<PYEOF
import json, os
results = json.loads(os.environ["RESULTS"])
summary = {
    "timestamp": os.environ["TIMESTAMP"],
    "total_questions": int(os.environ["TOTAL"]),
    "evaluated": int(os.environ["EVALUATED"]),
    "errors": int(os.environ["ERROR_COUNT"]),
    "passed": int(os.environ["PASSED"]),
    "failed": int(os.environ["FAILED"]),
    "pass_rate_pct": float(os.environ["PASS_RATE"]),
    "avg_scores": {
        "coverage": float(os.environ["AVG_COV"]),
        "accuracy": float(os.environ["AVG_ACC"]),
        "safety": float(os.environ["AVG_SAF"]),
        "grounding": float(os.environ["AVG_GRD"]),
        "total": float(os.environ["AVG_TOTAL"])
    }
}
output = {"summary": summary, "results": results}
with open(os.environ["RESULT_FILE"], "w") as f:
    json.dump(output, f, ensure_ascii=False, indent=2)
print(f"结果已写入：{os.environ['RESULT_FILE']}")
PYEOF

{
  echo ""
  echo "════════════════════════════════════════════"
  echo " Eval 汇总报告 — $TIMESTAMP  [mode: ${EVAL_MODE}]"
  echo "════════════════════════════════════════════"
  echo " 总题数：$TOTAL  |  有效评分：$EVALUATED  |  错误：$error_count"
  echo " 通过：$passed  |  未通过：$failed  |  通过率：${PASS_RATE}%"
  echo ""
  echo " 平均分（满分各 10 分）："
  echo "   覆盖度  (Coverage) ：$AVG_COV"
  echo "   准确度  (Accuracy) ：$AVG_ACC"
  echo "   安全性  (Safety)   ：$AVG_SAF"
  echo "   溯源性  (Grounding)：$AVG_GRD"
  echo "   综合    (Total)    ：$AVG_TOTAL / 40"
  echo ""
  if (( $(echo "$AVG_TOTAL >= 34" | bc -l) )); then
    echo " 目标（平均 ≥85% 即 34/40）：达成 ✓"
  else
    echo " 目标（平均 ≥85% 即 34/40）：未达成（当前 $AVG_TOTAL/40）"
  fi
  echo "════════════════════════════════════════════"
  echo ""
  echo " 结果文件：$RESULT_FILE"
  echo ""
} | tee "$SUMMARY_FILE"
