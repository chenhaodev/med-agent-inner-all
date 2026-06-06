#!/usr/bin/env bash
# build_prompt.sh — 拼装多源知识栈的 DeepSeek API JSON payload
# 用法：./bin/build_prompt.sh [--naive] [--reroll] "specialty:disease [...]" "问题文本"
#
# 标志（必须在位置参数之前）：
#   --naive    跳过 YAML/指南知识注入（诊断用，输出不含知识片段的裸 payload）
#   --reroll   回炉模式：在 user 消息中注入 VERIFY_FAILED 列表（从 $_VERIFY_JSON 读取）
#
# 输出：JSON payload（stdout）

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(dirname "$SCRIPT_DIR")"
PROMPTS_DIR="$ROOT_DIR/prompts"
KNOWLEDGE_DIR="$ROOT_DIR/knowledge"

# ─── 模式标志解析（在位置参数之前） ──────────────────────────
NAIVE=false
REROLL=false

while [[ $# -gt 0 ]]; do
  case "$1" in
    --naive)  NAIVE=true;  shift ;;
    --reroll) REROLL=true; shift ;;
    *)        break ;;
  esac
done

if [[ $# -lt 2 ]]; then
  echo "用法：./bin/build_prompt.sh [--naive] [--reroll] \"specialty:disease\" \"问题文本\"" >&2
  exit 1
fi

DOMAINS="$1"
QUESTION="$2"

if [[ -f "$ROOT_DIR/.env" ]]; then
  source "$ROOT_DIR/.env" 2>/dev/null || true
fi
DEEPSEEK_MODEL="${DEEPSEEK_MODEL:-deepseek-chat}"

# ─── 读取基础 prompt 文件 ─────────────────────────────────────
SYSTEM_BASE=$(cat "$PROMPTS_DIR/system_base.md")
OUTPUT_SCHEMA=$(cat "$PROMPTS_DIR/output_schema.md")

# ─── 知识片段注入（naive 模式跳过）──────────────────────────
SECTIONS_CONTENT=""
SEEN_SPECIALTIES=""

if [[ "$NAIVE" == "false" ]]; then
  for domain_tag in $DOMAINS; do
    SPECIALTY="${domain_tag%%:*}"     # "cardiology:hypertension" → "cardiology"
    DISEASE="${domain_tag##*:}"       # "cardiology:hypertension" → "hypertension"

    # 专科 section（每专科只加载一次）
    if ! echo " $SEEN_SPECIALTIES " | grep -qF " $SPECIALTY "; then
      SEEN_SPECIALTIES="$SEEN_SPECIALTIES $SPECIALTY"
      SECTION_FILE="$PROMPTS_DIR/sections/${SPECIALTY}.md"
      if [[ -f "$SECTION_FILE" ]]; then
        SECTIONS_CONTENT="${SECTIONS_CONTENT}

---

$(cat "$SECTION_FILE")"
      else
        echo "警告：找不到 section 文件 $SECTION_FILE，跳过。" >&2
      fi
    fi

    # ── 多源知识栈注入 ────────────────────────────────────────
    # 层 1：教材基线 YAML
    DISEASE_YAML="$KNOWLEDGE_DIR/${SPECIALTY}/${DISEASE}.yaml"
    if [[ -f "$DISEASE_YAML" ]]; then
      YAML_CONTENT=$(python3 -c "
import yaml, sys
with open(sys.argv[1]) as f:
    data = yaml.safe_load(f)
# 格式化为可读文本注入
lines = []
lines.append(f'# 知识栈：{data.get(\"specialty_zh\", \"\")}/{data.get(\"disease_zh\", \"\")}')
lines.append(f'## 来源基线（教材）：{data.get(\"source\", \"\")}')
for entry in data.get('entries', []):
    lines.append(f'')
    lines.append(f'### {entry.get(\"title\", \"\")}')
    lines.append(f'来源页：第 {entry.get(\"source_page\", \"?\")} 页 | 证据质量：{entry.get(\"evidence_level\", \"\")} | 推荐强度：{entry.get(\"recommendation\", \"\")}')
    for kp in entry.get('key_points', []):
        lines.append(f'- {kp}')
print('\n'.join(lines))
" "$DISEASE_YAML" 2>/dev/null)
      SECTIONS_CONTENT="${SECTIONS_CONTENT}

---

${YAML_CONTENT}"
    fi

    # 层 2：指南叠加 YAML（目录内所有 .yaml 按年份排序注入）
    GUIDELINES_DIR="$KNOWLEDGE_DIR/${SPECIALTY}/guidelines"
    if [[ -d "$GUIDELINES_DIR" ]]; then
      for GL_FILE in $(ls "$GUIDELINES_DIR"/*.yaml 2>/dev/null | sort); do
        GL_CONTENT=$(python3 -c "
import yaml, sys
with open(sys.argv[1]) as f:
    data = yaml.safe_load(f)

# 检查是否与请求疾病相关
disease = sys.argv[2]
scope = data.get('scope', [])
if scope and disease not in scope and 'all' not in scope:
    sys.exit(1)

lines = []
lines.append(f'## 指南叠加：{data.get(\"guideline_name\", \"\")} ({data.get(\"year\", \"\")})')
lines.append(f'※ 与教材冲突时，以本指南为准（更新于 {data.get(\"year\", \"\")}）')
for entry in data.get('entries', []):
    lines.append(f'')
    lines.append(f'### {entry.get(\"title\", \"\")}')
    lines.append(f'来源：{data.get(\"guideline_name\", \"\")} {data.get(\"year\", \"\")}年 | 证据级别：{entry.get(\"evidence_level\", \"\")} | 推荐强度：{entry.get(\"recommendation\", \"\")}')
    for kp in entry.get('key_points', []):
        lines.append(f'- {kp}')
print('\n'.join(lines))
" "$GL_FILE" "$DISEASE" 2>/dev/null) && \
        SECTIONS_CONTENT="${SECTIONS_CONTENT}

---

${GL_CONTENT}" || true
      done
    fi
  done
fi  # end NAIVE == false

# ─── 拼装 system prompt ───────────────────────────────────────
if [[ "$NAIVE" == "true" ]]; then
  SYSTEM_PROMPT="${SYSTEM_BASE}

---

${OUTPUT_SCHEMA}"
else
  SYSTEM_PROMPT="${SYSTEM_BASE}

---

${OUTPUT_SCHEMA}

---

# 当前问题相关知识片段

以下是与用户问题相关的内科教材及指南内容，你的回答必须严格基于这些内容：
${SECTIONS_CONTENT}"
fi

# ─── 生成 JSON payload ────────────────────────────────────────
export _BUILD_SYSTEM="$SYSTEM_PROMPT"
export _BUILD_QUESTION="$QUESTION"
export _BUILD_MODEL="$DEEPSEEK_MODEL"
export _BUILD_REROLL="$REROLL"

python3 - <<'PYEOF'
import json, os

system = os.environ["_BUILD_SYSTEM"]
question = os.environ["_BUILD_QUESTION"]
model = os.environ["_BUILD_MODEL"]
is_reroll = os.environ.get("_BUILD_REROLL", "false") == "true"

if is_reroll:
    verify_json_str = os.environ.get("_VERIFY_JSON", "")
    verify_data = json.loads(verify_json_str) if verify_json_str.strip() else {}
    failed = [c for c in verify_data.get("claims", []) if c["status"] == "✗"]
    failed_lines = "\n".join(
        f"- [{c['kind']}] {c['claim']} — {c['evidence']}"
        for c in failed
    )
    user_content = (
        f"原始问题：{question}\n\n"
        "VERIFY_FAILED — 以下声明在教材原文中找不到支撑，"
        "请在修订版中删除或依据注入知识片段更正：\n\n"
        f"{failed_lines}\n\n"
        "请重新生成完整的5段式回答。"
    )
else:
    user_content = question

payload = {
    "model": model,
    "temperature": 0.3,
    "max_tokens": 1500,
    "messages": [
        {"role": "system", "content": system},
        {"role": "user",   "content": user_content}
    ]
}

print(json.dumps(payload, ensure_ascii=False))
PYEOF
