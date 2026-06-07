#!/usr/bin/env python3
"""
audit_eval_gold.py — eval/gold.yaml ↔ source/chapters 静态对齐审计（无 LLM 调用）

对 gold.yaml 每道题的 must_warn 和 expected_topics，检查各条声明：
  ✓ both        — 源章节 + YAML key_points 均含足够 token（理想态）
  ⚠ yaml-only   — YAML 有但源章节找不到（YAML 次生证据，可能有误）
  ⚠ source-only — 源章节有但 YAML 未覆盖（知识缺口，参考 COPD_REHAB 模式）
  ✗ neither     — 两边都找不到（eval gold 标注可能有误，或源未提及）

用法：
  python3 bin/audit_eval_gold.py                   # 所有题目
  python3 bin/audit_eval_gold.py --id RESP_COPD_01 # 指定题目
  python3 bin/audit_eval_gold.py --json            # 结尾追加 JSON
  python3 bin/audit_eval_gold.py --only neither    # 仅显示某象限
"""

import json
import re
import sys
import yaml
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
EVAL_GOLD = ROOT / "eval" / "gold.yaml"
SRC = ROOT / "source" / "chapters"
KN = ROOT / "knowledge"

CJK = r"一-鿿"
# Max 4 chars so long phrases break into findable substrings:
# "不可自行停药" → ["不可自行","停药"]  "血氧饱和度" → ["血氧饱和","度"→skip]
TOKEN_RE = re.compile(rf"[{CJK}]{{2,4}}|[A-Za-z][A-Za-z0-9\-]{{2,}}|\d+(?:\.\d+)?(?:%|mmHg|mg|g|ml)?")
STOP = set(
    "患者疾病治疗症状建议医生就医注意可能没有需要进行通过"
    "包括以及如果出现这是什么日常常见误区依据管理控制增加"
    "降低正常异常情况问题方法检查评估应该应当应注意时间".split()
)


def extract_tokens(text: str) -> set:
    out = set()
    for m in TOKEN_RE.findall(text):
        if m not in STOP and len(m) >= 2:
            out.add(m)
    return out


def load_source_text(domains: list) -> tuple:
    """Returns (combined_src_text, combined_yaml_kp_text, domains_status)."""
    src_parts, yaml_parts, statuses = [], [], []
    for domain in domains:
        if ":" not in domain:
            continue
        spec, disease = domain.split(":", 1)
        src_path = SRC / spec / f"{disease}.md"
        yaml_path = KN / spec / f"{disease}.yaml"

        if src_path.exists():
            src_parts.append(src_path.read_text(encoding="utf-8"))
            statuses.append(f"{spec}/{disease} ✓")
        else:
            statuses.append(f"{spec}/{disease} (src missing)")

        if yaml_path.exists():
            data = yaml.safe_load(yaml_path.read_text(encoding="utf-8")) or {}
            for e in data.get("entries", []):
                yaml_parts.extend(e.get("key_points", []))
                yaml_parts.extend(e.get("must_warn", []))
                yaml_parts.append(e.get("title", ""))

    return " ".join(src_parts), " ".join(yaml_parts), statuses


def classify(claim: str, src_text: str, yaml_text: str) -> dict:
    toks = extract_tokens(claim)
    if not toks:
        return {"quadrant": "skip", "tokens": [], "missing_src": [], "missing_yaml": []}

    src_hits = {t for t in toks if t in src_text}
    yaml_hits = {t for t in toks if t in yaml_text}

    # Require ≥ ceil(n/2) tokens to count as "found" (handles 1-token claims too)
    threshold = max(1, (len(toks) + 1) // 2)
    src_found = len(src_hits) >= threshold
    yaml_found = len(yaml_hits) >= threshold

    if src_found and yaml_found:
        quadrant = "both"
    elif yaml_found and not src_found:
        quadrant = "yaml-only"
    elif src_found and not yaml_found:
        quadrant = "source-only"
    else:
        quadrant = "neither"

    return {
        "quadrant": quadrant,
        "tokens": sorted(toks),
        "src_hits": sorted(src_hits),
        "yaml_hits": sorted(yaml_hits),
        "missing_src": sorted(toks - src_hits),
        "missing_yaml": sorted(toks - yaml_hits),
    }


def audit_question(q: dict) -> dict:
    qid = q.get("id", "?")
    question = q.get("question", "")
    domains = q.get("expected_domain", [])
    must_warns = q.get("must_warn", [])
    expected_topics = q.get("expected_topics", [])

    src_text, yaml_text, domain_status = load_source_text(domains)

    items = []
    for field, claims in [("must_warn", must_warns), ("expected_topics", expected_topics)]:
        for claim in claims:
            info = classify(claim, src_text, yaml_text)
            items.append({"field": field, "claim": claim, **info})

    return {
        "id": qid,
        "question": question,
        "domains": domains,
        "domain_status": domain_status,
        "items": items,
    }


SYMBOL = {"both": "✓", "yaml-only": "⚠", "source-only": "⚠", "neither": "✗", "skip": "·"}
FLAG_LABEL = {
    "both": "both       ",
    "yaml-only": "yaml-only  ",
    "source-only": "SOURCE-ONLY",
    "neither": "NEITHER    ",
    "skip": "skip       ",
}


def print_result(result: dict, only: str | None = None) -> None:
    items = result["items"]
    if only:
        items = [i for i in items if i["quadrant"] == only]
    if not items and only:
        return

    has_issues = any(i["quadrant"] in ("source-only", "neither") for i in result["items"])
    marker = " ←" if has_issues else ""
    print(f"\n[{result['id']}] {result['question'][:45]}{marker}")
    if result["domain_status"]:
        print(f"  域: {', '.join(result['domain_status'])}")

    for item in items:
        q = item["quadrant"]
        sym = SYMBOL.get(q, "?")
        flag = FLAG_LABEL.get(q, q)
        field = "W" if item["field"] == "must_warn" else "T"
        claim = item["claim"][:55]
        missing_src = item.get("missing_src", [])
        detail = f"  (src缺: {missing_src})" if q in ("neither", "yaml-only") and missing_src else ""
        print(f"  {sym} [{field}] {flag}  {claim}{detail}")


def main() -> int:
    args = sys.argv[1:]
    filter_id = None
    output_json = False
    only_quad = None

    i = 0
    while i < len(args):
        if args[i] == "--id" and i + 1 < len(args):
            filter_id = args[i + 1]
            i += 2
        elif args[i] == "--json":
            output_json = True
            i += 1
        elif args[i] == "--only" and i + 1 < len(args):
            only_quad = args[i + 1]
            i += 2
        else:
            i += 1

    data = yaml.safe_load(EVAL_GOLD.read_text(encoding="utf-8"))
    questions = data.get("questions", [])
    if filter_id:
        questions = [q for q in questions if q.get("id") == filter_id]

    print("=" * 62)
    print(f"  audit_eval_gold — eval/gold.yaml ↔ source 对齐审计")
    print(f"  题目总数：{len(questions)}")
    print("=" * 62)
    print("  象限说明：")
    print("    ✓ both        — 源 + YAML 均有证据（理想）")
    print("    ⚠ yaml-only   — YAML 有但源找不到（YAML 可能错误）")
    print("    ⚠ source-only — 源有但 YAML 未覆盖（缺口，考虑补 YAML）")
    print("    ✗ neither     — 两边都无（eval gold 可能标错）")
    print("  字段：W=must_warn  T=expected_topics")

    all_results = []
    counts: dict = {"both": 0, "yaml-only": 0, "source-only": 0, "neither": 0, "skip": 0}
    neither_list = []
    source_only_list = []

    for q in questions:
        r = audit_question(q)
        all_results.append(r)
        print_result(r, only=only_quad)
        for item in r["items"]:
            quad = item["quadrant"]
            counts[quad] = counts.get(quad, 0) + 1
            if quad == "neither":
                neither_list.append((r["id"], item["field"], item["claim"]))
            elif quad == "source-only":
                source_only_list.append((r["id"], item["field"], item["claim"]))

    total = sum(counts[k] for k in ("both", "yaml-only", "source-only", "neither"))
    pct = lambda n: f"{100 * n // max(total, 1):3d}%"

    print("\n" + "=" * 62)
    print("  汇总（声明级）")
    print("=" * 62)
    print(f"  ✓ both        {counts['both']:3d}  {pct(counts['both'])}")
    print(f"  ⚠ yaml-only   {counts['yaml-only']:3d}  {pct(counts['yaml-only'])}")
    print(f"  ⚠ source-only {counts['source-only']:3d}  {pct(counts['source-only'])}")
    print(f"  ✗ neither     {counts['neither']:3d}  {pct(counts['neither'])}")
    print(f"  · skip        {counts['skip']:3d}")
    print(f"  合计声明数    {total:3d}")

    if source_only_list:
        print("\n─── ⚠ source-only：源有但 YAML 未覆盖，建议补 YAML ───")
        for qid, field, claim in source_only_list:
            print(f"  [{qid}] {field}: {claim}")

    if neither_list:
        print("\n─── ✗ neither：两边都找不到，eval gold 可能标错 ───")
        for qid, field, claim in neither_list:
            print(f"  [{qid}] {field}: {claim}")

    if output_json:
        out_path = ROOT / "eval" / "results" / "audit_gold_latest.json"
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump({"results": all_results, "counts": counts}, f, ensure_ascii=False, indent=2)
        print(f"\n  JSON 已写入：{out_path}")

    # Non-zero exit if there are "neither" items (possible gold errors)
    return 1 if neither_list else 0


if __name__ == "__main__":
    sys.exit(main())
