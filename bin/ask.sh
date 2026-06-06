#!/usr/bin/env bash
# ask.sh — 西氏内科学精要 家属问答 Agent 入口
# 用法：./bin/ask.sh "问题文本"
#       ./bin/ask.sh "我爸有高血压，平时饮食要注意什么？"
#
# 可选参数：
#   --debug         打印路由和 payload 信息（写入 stderr）
#   --deep          原子声明 grep 核验 + 必要时回炉自纠（降低幻觉率）
#   --domain XXX    强制指定领域，跳过自动路由（例如 --domain cardiology:hypertension）

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(dirname "$SCRIPT_DIR")"

# ─── 参数解析 ────────────────────────────────────────────────
DEBUG=false
DEEP=false
FORCE_DOMAIN=""
QUESTION=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --debug)
      DEBUG=true
      shift
      ;;
    --deep)
      DEEP=true
      shift
      ;;
    --domain)
      FORCE_DOMAIN="$2"
      shift 2
      ;;
    *)
      QUESTION="$1"
      shift
      ;;
  esac
done

if [[ -z "$QUESTION" ]]; then
  echo "用法：./bin/ask.sh \"问题文本\"" >&2
  echo "示例：./bin/ask.sh \"我爸有高血压，平时饮食要注意什么？\"" >&2
  echo "" >&2
  echo "可选参数：" >&2
  echo "  --debug           打印路由调试信息" >&2
  echo "  --deep            开启原子声明核验 + 回炉自纠（降低幻觉率）" >&2
  echo "  --domain DOMAIN   强制使用指定领域（跳过自动路由）" >&2
  exit 1
fi

# ─── 0. 越界检测（确定性拦截）────────────────────────────────
OOB_RESULT=$("$SCRIPT_DIR/oob_check.sh" "$QUESTION" 2>/dev/null || echo "in_scope")
[[ "$DEBUG" == "true" ]] && echo "[DEBUG] OOB 检测 → $OOB_RESULT" >&2

if [[ "$OOB_RESULT" != "in_scope" ]]; then
  OOB_TYPE=$(echo "$OOB_RESULT" | cut -d: -f2-)
  export ROOT_DIR OOB_TYPE QUESTION

  OOB_REPLY=$(python3 - <<'PYEOF'
import re, os, sys

templates_file = os.path.join(os.environ["ROOT_DIR"], "prompts/oob_templates.md")
oob_type = os.environ["OOB_TYPE"]
question = os.environ["QUESTION"]

with open(templates_file) as f:
    content = f.read()

pattern = rf"## {re.escape(oob_type)}\n(.*?)(?=\n## |\Z)"
match = re.search(pattern, content, re.DOTALL)
if match:
    template = match.group(1).strip()
    print(template)
else:
    print("很抱歉，您的问题超出了本系统依据《西氏内科学精要》的覆盖范围，建议咨询专科医生。")
PYEOF
)

  echo ""
  echo "═══════════════════════════════════════════════════════"
  echo "$OOB_REPLY"
  echo "═══════════════════════════════════════════════════════"
  echo ""
  exit 0
fi

# ─── 1. 路由：确定专科:疾病 ──────────────────────────────────
if [[ -n "$FORCE_DOMAIN" ]]; then
  DOMAINS="$FORCE_DOMAIN"
  [[ "$DEBUG" == "true" ]] && echo "[DEBUG] 强制路由 → $DOMAINS" >&2
else
  DOMAINS=$("$SCRIPT_DIR/router.sh" "$QUESTION" 2>&1) || {
    echo "警告：路由失败，使用默认领域 cardiology:general。" >&2
    DOMAINS="cardiology:general"
  }
  [[ "$DEBUG" == "true" ]] && echo "[DEBUG] 自动路由 → $DOMAINS" >&2
fi

# ─── 2. 构建 prompt payload ──────────────────────────────────
[[ "$DEBUG" == "true" ]] && echo "[DEBUG] 正在构建 prompt (领域: $DOMAINS)..." >&2

PAYLOAD=$("$SCRIPT_DIR/build_prompt.sh" "$DOMAINS" "$QUESTION") || {
  echo "错误：构建 prompt 失败。" >&2
  exit 1
}

if [[ "$DEBUG" == "true" ]]; then
  PAYLOAD_SIZE=$(echo "$PAYLOAD" | wc -c)
  echo "[DEBUG] Payload 大小：${PAYLOAD_SIZE} 字节" >&2
fi

# ─── 3. 调用 DeepSeek API ────────────────────────────────────
[[ "$DEBUG" == "true" ]] && echo "[DEBUG] 正在调用 DeepSeek API..." >&2

RESPONSE=$(echo "$PAYLOAD" | "$SCRIPT_DIR/call_deepseek.sh") || {
  echo "错误：API 调用失败。" >&2
  exit 1
}

# ─── 3b. --deep: 原子声明 grep 核验 + 必要时回炉 ────────────
if [[ "$DEEP" == "true" ]]; then
  # 定位首个 domain 对应的章节文件
  FIRST_DOMAIN=$(echo "$DOMAINS" | awk '{print $1}')
  FIRST_SP="${FIRST_DOMAIN%%:*}"
  FIRST_DS="${FIRST_DOMAIN##*:}"
  CHAPTER_FILE="$ROOT_DIR/source/chapters/${FIRST_SP}/${FIRST_DS}.md"
  YAML_FILE="$ROOT_DIR/knowledge/${FIRST_SP}/${FIRST_DS}.yaml"

  [[ "$DEBUG" == "true" ]] && \
    echo "[DEBUG --deep] 核验文件: ${FIRST_SP}/${FIRST_DS}" >&2

  # C. 运行 verify_claims.py
  set +e
  VERIFY_JSON=$(python3 "$SCRIPT_DIR/verify_claims.py" \
    --chapter "$CHAPTER_FILE" \
    --yaml "$YAML_FILE" \
    --answer "$RESPONSE")
  VERIFY_EXIT=$?
  set -e

  if [[ "$DEBUG" == "true" ]]; then
    FAIL_COUNT=$(echo "$VERIFY_JSON" | python3 -c \
      "import json,sys; d=json.load(sys.stdin); print(d.get('fail_count',0))" 2>/dev/null || echo "?")
    echo "[DEBUG --deep] 核验完成，✗ 声明数: $FAIL_COUNT" >&2
    echo "$VERIFY_JSON" | python3 -c "
import json, sys
d = json.load(sys.stdin)
for c in d.get('claims', []):
    print(f'  {c[\"status\"]} [{c[\"kind\"]}] {c[\"claim\"]} — {c[\"evidence\"]}')
" >&2 2>/dev/null || true
  fi

  # D. 有 ✗ → 回炉一次
  if [[ "$VERIFY_EXIT" == "1" ]]; then
    [[ "$DEBUG" == "true" ]] && echo "[DEBUG --deep] 发现 ✗ 声明，启动回炉..." >&2

    export _VERIFY_JSON="$VERIFY_JSON"

    set +e
    REROLL_RESPONSE=$(
      "$SCRIPT_DIR/build_prompt.sh" --reroll "$DOMAINS" "$QUESTION" \
      | "$SCRIPT_DIR/call_deepseek.sh"
    )
    REROLL_EXIT=$?
    set -e

    if [[ "$REROLL_EXIT" == "0" && -n "$REROLL_RESPONSE" ]]; then
      RESPONSE="$REROLL_RESPONSE"
      [[ "$DEBUG" == "true" ]] && echo "[DEBUG --deep] 回炉完成" >&2
    else
      [[ "$DEBUG" == "true" ]] && echo "[DEBUG --deep] 回炉失败，保留首轮回答" >&2
      # Annotate residual failures in debug output
      echo "[DEBUG --deep] RESIDUAL_UNVERIFIED: 首轮核验有 ✗ 但回炉失败，请人工复查。" >&2
    fi
  fi

  # Naive 对照（--debug --deep 时才运行，不影响最终答案）
  if [[ "$DEBUG" == "true" ]]; then
    echo "[DEBUG --deep] 运行 naive 对照（不注入知识库）..." >&2
    set +e
    NAIVE_RESPONSE=$(
      "$SCRIPT_DIR/build_prompt.sh" --naive "$DOMAINS" "$QUESTION" \
      | "$SCRIPT_DIR/call_deepseek.sh" 2>/dev/null
    )
    NAIVE_EXIT=$?
    set -e

    if [[ "$NAIVE_EXIT" == "0" && -n "$NAIVE_RESPONSE" ]]; then
      echo "" >&2
      echo "[DEBUG --deep] ══════ 【naive vs 接地】差异（- naive / + 接地）══════" >&2
      diff <(echo "$NAIVE_RESPONSE") <(echo "$RESPONSE") >&2 || true
      echo "[DEBUG --deep] ═════════════════════════════════════════════════════" >&2
    else
      echo "[DEBUG --deep] naive 调用失败，跳过 diff。" >&2
    fi
  fi
fi

# ─── 4. 后处理：校验结构 ─────────────────────────────────────
VALIDATED=$(echo "$RESPONSE" | "$SCRIPT_DIR/postprocess.sh") || {
  VALIDATED="$RESPONSE"
}

# ─── 5. 输出结果 ─────────────────────────────────────────────
echo ""
echo "═══════════════════════════════════════════════════════"
echo "$VALIDATED"
echo "═══════════════════════════════════════════════════════"
echo ""
