#!/usr/bin/env bash
# postprocess.sh — 校验模型输出是否符合 5 段式 schema
# 用法：echo "模型回复" | ./bin/postprocess.sh
# 输出：
#   通过 → 原文输出（stdout），退出码 0
#   缺段 → stderr 输出警告，stdout 输出原始回复，退出码 1

set -euo pipefail

RESPONSE="$(cat)"

if [[ -z "$RESPONSE" ]]; then
  echo "错误：postprocess.sh 收到空响应。" >&2
  exit 1
fi

# ─── 5 段式结构检查（家属版）────────────────────────────────
REQUIRED_SECTIONS=(
  "【这是什么】"
  "【日常该怎么做】"
  "【什么情况要就医】"
  "【常见误区】"
  "【依据】"
)

MISSING=()
for section in "${REQUIRED_SECTIONS[@]}"; do
  if ! echo "$RESPONSE" | grep -qF "$section"; then
    MISSING+=("$section")
  fi
done

# ─── 安全性检查：必须包含来源引用（OOB 拒答时豁免）──────────
IS_OOB_RESPONSE=false
if echo "$RESPONSE" | grep -qE "超出.*范围|不在.*覆盖|不覆盖|超出了.*范围"; then
  IS_OOB_RESPONSE=true
fi

if [[ "$IS_OOB_RESPONSE" == "false" ]]; then
  if ! echo "$RESPONSE" | grep -qE "第[0-9]+页|p\.[0-9]+|章节|指南|《"; then
    MISSING+=("【依据】中的来源引用")
  fi
fi

# ─── 输出处理 ────────────────────────────────────────────────
if [[ ${#MISSING[@]} -eq 0 ]]; then
  echo "$RESPONSE"
  exit 0
fi

MISSING_LIST=$(printf "、%s" "${MISSING[@]}")
MISSING_LIST="${MISSING_LIST:1}"

echo "⚠️  输出结构不完整，缺少：${MISSING_LIST}" >&2
echo "$RESPONSE"
exit 1
