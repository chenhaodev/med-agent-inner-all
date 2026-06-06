#!/usr/bin/env python3
"""
build_mode_gold.py — 为 eval/gold.yaml 生成 patient_must_not_phrases 草稿

逻辑：
  对每道题命中的 YAML 条目，找出 evidence_level=低 的条目
  → 提取源章节中出现的"活动词汇白名单"（散步/游泳/太极等）
  → 生成"patient_must_not_phrases"草稿：
    白名单内活动词 → 不列（允许出现）
    常见医学临床活动词 → 若源中找不到，列入黑名单草稿
  同时列出 doctor_must_have_tags（低证据条目必须有此标注）

用法：
  python3 bin/build_mode_gold.py                    # 所有题，打印草稿
  python3 bin/build_mode_gold.py --id NEURO_DEMENTIA_01
  python3 bin/build_mode_gold.py --apply            # 直接写入 gold.yaml（谨慎！）
  python3 bin/build_mode_gold.py --dry-run          # 仅打印，不写（默认）
"""

import re
import sys
import yaml
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
EVAL_GOLD = ROOT / "eval" / "gold.yaml"
SRC = ROOT / "source" / "chapters"
KN = ROOT / "knowledge"

# 常见"可能被编造"的活动/运动词汇
COMMON_ACTIVITY_WORDS = [
    "散步", "步行", "快走", "慢跑", "跑步", "游泳",
    "太极", "太极拳", "瑜伽", "气功", "八段锦",
    "原地踏步", "坐姿操", "体操", "广场舞",
    "骑车", "自行车", "爬山", "爬楼梯",
    "阻力训练", "力量训练", "哑铃", "弹力带",
    "普拉提", "健身", "有氧操",
    "伸展", "拉伸", "关节活动",
]

# 常见"编造频率"的模式（正则）
FABRICATED_FREQ_PATTERNS = [
    r"每天\s*\d+[-~]\d+\s*分钟",
    r"每周\s*\d+\s*次",
    r"每次\s*\d+\s*分钟",
    r"\d+[-~]\d+\s*分钟",
]


def load_source_text(domains: list) -> str:
    parts = []
    for domain in domains:
        if ":" not in domain:
            continue
        spec, disease = domain.split(":", 1)
        src = SRC / spec / f"{disease}.md"
        if src.exists():
            parts.append(src.read_text(encoding="utf-8"))
    return " ".join(parts)


def load_low_evidence_entries(domains: list) -> list:
    """Return YAML entries with evidence_level = 低."""
    entries = []
    for domain in domains:
        if ":" not in domain:
            continue
        spec, disease = domain.split(":", 1)
        yaml_path = KN / spec / f"{disease}.yaml"
        if not yaml_path.exists():
            continue
        data = yaml.safe_load(yaml_path.read_text(encoding="utf-8")) or {}
        for e in data.get("entries", []):
            if e.get("evidence_level") == "低":
                entries.append(e)
    return entries


EXERCISE_KEYWORDS = re.compile(
    r"运动|锻炼|体育|有氧|步行|散步|太极|瑜伽|体操|活动能力|运动耐量|康复|体力"
)


def entries_are_exercise_related(low_entries: list) -> bool:
    """Return True only when the low-evidence entries are about exercise/activity."""
    for e in low_entries:
        text = " ".join(e.get("key_points", [])) + " " + e.get("title", "")
        if EXERCISE_KEYWORDS.search(text):
            return True
    return False


def build_patient_blacklist(source_text: str, low_entries: list) -> list:
    """Activity words common in medicine but NOT in source → blacklist.

    Only relevant when low-evidence entries discuss exercise/physical activity.
    """
    if not entries_are_exercise_related(low_entries):
        return []

    blacklist = []
    for word in COMMON_ACTIVITY_WORDS:
        if word not in source_text:
            blacklist.append(word)
    # Frequency fabrication patterns (string fragments, readable in gold.yaml)
    blacklist.extend([
        "每天10", "每天15", "每天20", "每天30",
        "每周3次", "每周5次",
    ])
    return sorted(set(blacklist))


def build_doctor_must_have_tags(low_entries: list) -> list:
    """Tags doctor output must contain.

    '证据等级' is universal — doctor schema requires evidence-level annotations on
    every management point.  Low-evidence entries additionally require the
    fine-grained labels so the deterministic check fires.
    """
    tags = ["证据等级"]
    if low_entries:
        tags += ["低级别证据", "临床常用"]
    return tags


def process_question(q: dict, apply: bool) -> dict:
    qid = q.get("id", "?")
    domains = q.get("expected_domain", [])

    source_text = load_source_text(domains)
    low_entries = load_low_evidence_entries(domains)

    blacklist = build_patient_blacklist(source_text, low_entries) if low_entries else []
    must_have = build_doctor_must_have_tags(low_entries)  # always at least ['证据等级']

    if not low_entries:
        return {"id": qid, "has_low_evidence": False,
                "patient_must_not_phrases": [], "doctor_must_have_tags": must_have}

    return {
        "id": qid,
        "has_low_evidence": True,
        "low_evidence_entry_ids": [e.get("id", "?") for e in low_entries],
        "patient_must_not_phrases": blacklist,
        "doctor_must_have_tags": must_have,
    }


def print_result(r: dict) -> None:
    if not r["has_low_evidence"]:
        print(f"  [{r['id']}] 无低证据条目  doctor_tags={r['doctor_must_have_tags']}")
        return
    print(f"\n  [{r['id']}]  低证据条目: {', '.join(r['low_evidence_entry_ids'])}")
    print(f"  patient_must_not_phrases ({len(r['patient_must_not_phrases'])} 条):")
    for p in r["patient_must_not_phrases"]:
        print(f"    - {p}")
    print(f"  doctor_must_have_tags: {r['doctor_must_have_tags']}")


def apply_to_gold(results: list) -> None:
    """Write patient_must_not_phrases and doctor_must_have_tags into gold.yaml."""
    text = EVAL_GOLD.read_text(encoding="utf-8")
    data = yaml.safe_load(text)
    questions = data.get("questions", [])
    by_id = {r["id"]: r for r in results}  # include all questions, not only low-evidence

    changed = 0
    for q in questions:
        qid = q.get("id")
        if qid not in by_id:
            continue
        r = by_id[qid]
        if r["patient_must_not_phrases"]:
            q["patient_must_not_phrases"] = r["patient_must_not_phrases"]
        if r["doctor_must_have_tags"]:
            q["doctor_must_have_tags"] = r["doctor_must_have_tags"]
        changed += 1

    if changed:
        EVAL_GOLD.write_text(
            yaml.dump(data, allow_unicode=True, default_flow_style=False,
                      sort_keys=False, width=120),
            encoding="utf-8",
        )
        print(f"\n已更新 {changed} 道题的 gold.yaml 字段。")
    else:
        print("\n没有需要更新的题目。")


def main() -> int:
    args = sys.argv[1:]
    filter_id = None
    apply_flag = False

    i = 0
    while i < len(args):
        if args[i] == "--id" and i + 1 < len(args):
            filter_id = args[i + 1]; i += 2
        elif args[i] == "--apply":
            apply_flag = True; i += 1
        elif args[i] == "--dry-run":
            i += 1
        else:
            i += 1

    data = yaml.safe_load(EVAL_GOLD.read_text(encoding="utf-8"))
    questions = data.get("questions", [])
    if filter_id:
        questions = [q for q in questions if q.get("id") == filter_id]

    print("=" * 60)
    print("  build_mode_gold — patient_must_not_phrases 草稿生成")
    print(f"  题目数: {len(questions)}")
    print("=" * 60)

    results = []
    low_count = 0
    for q in questions:
        r = process_question(q, apply_flag)
        results.append(r)
        if r["has_low_evidence"]:
            low_count += 1
        print_result(r)

    print(f"\n汇总：{low_count}/{len(questions)} 道题含低证据条目（幻觉高风险区）")
    print(f"全部 {len(questions)} 道题将写入 doctor_must_have_tags=['证据等级', ...]")

    if apply_flag:
        print("\n写入 gold.yaml...")
        apply_to_gold(results)
    else:
        print("\n（草稿模式，加 --apply 写入 gold.yaml）")

    return 0


if __name__ == "__main__":
    sys.exit(main())
