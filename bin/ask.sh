#!/usr/bin/env bash
# ask.sh — 西氏内科学精要 家属问答 Agent 入口
# 用法：./bin/ask.sh "问题文本"
#       ./bin/ask.sh "我爸有高血压，平时饮食要注意什么？"
#
# 可选参数：
#   --debug         打印路由和 payload 信息（写入 stderr）
#   --domain XXX    强制指定领域，跳过自动路由（例如 --domain cardiology:hypertension）

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(dirname "$SCRIPT_DIR")"

# ─── 参数解析 ────────────────────────────────────────────────
DEBUG=false
FORCE_DOMAIN=""
QUESTION=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --debug)
      DEBUG=true
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
