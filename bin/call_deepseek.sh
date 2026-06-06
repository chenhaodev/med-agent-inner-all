#!/usr/bin/env bash
# call_deepseek.sh — 调用 DeepSeek API
# 用法：echo '<json_payload>' | ./bin/call_deepseek.sh
# 输出：模型回复的文本内容（纯文本，不含 JSON 包装）

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(dirname "$SCRIPT_DIR")"

if [[ -f "$ROOT_DIR/.env" ]]; then
  source "$ROOT_DIR/.env"
fi

DEEPSEEK_API_KEY="${DEEPSEEK_API_KEY:-}"
DEEPSEEK_MODEL="${DEEPSEEK_MODEL:-deepseek-chat}"
DEEPSEEK_TIMEOUT="${DEEPSEEK_TIMEOUT:-60}"
DEEPSEEK_MAX_RETRIES="${DEEPSEEK_MAX_RETRIES:-3}"
API_URL="https://api.deepseek.com/v1/chat/completions"

if [[ -z "$DEEPSEEK_API_KEY" ]]; then
  echo "错误：未设置 DEEPSEEK_API_KEY。请复制 .env.example 为 .env 并填入 key。" >&2
  exit 1
fi

PAYLOAD="$(cat)"

if [[ -z "$PAYLOAD" ]]; then
  echo "错误：call_deepseek.sh 未收到任何 JSON payload（stdin 为空）。" >&2
  exit 1
fi

attempt=0
while true; do
  attempt=$((attempt + 1))

  HTTP_RESPONSE=$(curl -s -w "\n__HTTP_STATUS__%{http_code}" \
    --max-time "$DEEPSEEK_TIMEOUT" \
    -X POST "$API_URL" \
    -H "Content-Type: application/json" \
    -H "Authorization: Bearer $DEEPSEEK_API_KEY" \
    -d "$PAYLOAD" 2>&1) || {
    echo "错误：curl 请求失败（网络问题或超时）。" >&2
    exit 1
  }

  HTTP_BODY="$(echo "$HTTP_RESPONSE" | sed '$d')"
  HTTP_STATUS="$(echo "$HTTP_RESPONSE" | tail -1 | sed 's/__HTTP_STATUS__//')"

  if [[ "$HTTP_STATUS" == "200" ]]; then
    CONTENT=$(echo "$HTTP_BODY" | python3 -c "
import sys, json
data = json.load(sys.stdin)
content = data['choices'][0]['message']['content']
if not content or not content.strip():
    print('错误：API 返回空 content', file=sys.stderr)
    sys.exit(1)
print(content)
" 2>&1) || {
      echo "错误：解析 API 响应失败或 content 为空，将重试。" >&2
      if [[ $attempt -ge $DEEPSEEK_MAX_RETRIES ]]; then
        echo "响应：$HTTP_BODY" >&2
        exit 1
      fi
      sleep $((attempt * 2))
      continue
    }
    echo "$CONTENT"
    exit 0
  fi

  if [[ "$HTTP_STATUS" == "429" || "$HTTP_STATUS" == "500" || "$HTTP_STATUS" == "502" || "$HTTP_STATUS" == "503" ]]; then
    if [[ $attempt -ge $DEEPSEEK_MAX_RETRIES ]]; then
      echo "错误：API 返回 HTTP $HTTP_STATUS，已重试 $attempt 次，放弃。" >&2
      echo "响应：$HTTP_BODY" >&2
      exit 1
    fi
    SLEEP_SEC=$((attempt * 2))
    echo "警告：HTTP $HTTP_STATUS，${SLEEP_SEC}s 后重试（第 ${attempt}/${DEEPSEEK_MAX_RETRIES} 次）..." >&2
    sleep "$SLEEP_SEC"
    continue
  fi

  echo "错误：API 返回 HTTP $HTTP_STATUS。" >&2
  echo "响应：$HTTP_BODY" >&2
  exit 1
done
