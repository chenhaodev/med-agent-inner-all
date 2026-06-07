#!/usr/bin/env python3
"""
audit_routing.py — gold.yaml 路由与标签契约审计（无 LLM 调用，<5s 跑完 147 题）

两类确定性检查，覆盖最易静默失败的两个环节：

  [ROUTE] 每题过 router.sh，断言输出 ∩ expected_domain ≠ ∅
          → 捕获"关键词漏配 → 路由到 *:general → YAML 静默跳过"类缺陷
            （如 肺栓塞 误入 respiratory:general 而非 hematology:thrombosis）

  [TAG]   doctor_must_have_tags 每个标签须能在该题命中 domain 的 YAML
          key_points 中作为子串找到 → 捕获"标签是元描述而非模型会写的具体词"
            （如 药物选择依据 / 具体阈值 这类抽象短语，模型永远不会逐字输出）

用法：
  python3 bin/audit_routing.py                # 全量
  python3 bin/audit_routing.py --only route   # 仅路由
  python3 bin/audit_routing.py --only tag      # 仅标签
  退出码 1 = 有 FAIL（可挂 CI / pre-commit）
"""

import argparse
import subprocess
import sys
import yaml
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
EVAL_GOLD = ROOT / "eval" / "gold.yaml"
KN = ROOT / "knowledge"
ROUTER = ROOT / "bin" / "router.sh"

# doctor 模板固定段落/证据分级词，非知识词，豁免接地检查
TEMPLATE_TOKENS = {
    "证据等级", "高级别证据", "中级别证据", "低级别证据", "临床常用", "指南推荐",
}


def load_gold():
    with open(EVAL_GOLD) as f:
        return yaml.safe_load(f)["questions"]


def route(question: str) -> list[str]:
    """跑 router.sh，返回 specialty:disease 标签列表。"""
    out = subprocess.run(
        ["bash", str(ROUTER), question],
        capture_output=True, text=True, timeout=30,
    )
    return out.stdout.strip().split()


def yaml_text_for(domain: str) -> str:
    """读 knowledge/<specialty>/<disease>.yaml 的全文（用于子串匹配）。"""
    try:
        specialty, disease = domain.split(":", 1)
    except ValueError:
        return ""
    path = KN / specialty / f"{disease}.yaml"
    return path.read_text(encoding="utf-8") if path.exists() else ""


def has_yaml(domain: str) -> bool:
    try:
        specialty, disease = domain.split(":", 1)
    except ValueError:
        return False
    return (KN / specialty / f"{disease}.yaml").exists()


def audit_route(questions):
    """
    返回 (errors, warns)。
      ERROR = 实际路由的标签全都没有 YAML → 知识静默跳过、回退参数记忆（PE_ANTICOAG 类真 bug）
      WARN  = 路由命中了某个有 YAML 的 disease，但与 gold expected_domain 不交集
              （多为跨专科共置，如 gout 在 endocrine 而 gold 写 rheumatology；或 gold 已过时）
    真正会拉低 grounding 的只有 ERROR；WARN 供人工复核 gold 标注是否陈旧。
    """
    errors, warns = [], []
    for q in questions:
        expected = set(q.get("expected_domain", []))
        if not expected:
            continue
        actual = route(q["question"])
        if expected & set(actual):
            continue
        if not any(has_yaml(t) for t in actual):
            errors.append((q["id"], sorted(expected), actual))
        else:
            warns.append((q["id"], sorted(expected), actual))
    return errors, warns


def audit_tags(questions):
    fails = []
    for q in questions:
        tags = q.get("doctor_must_have_tags", [])
        if not tags:
            continue
        # 标签须在 expected_domain 任一 YAML 中找到（证据等级是模板通用词，豁免）
        corpus = "".join(yaml_text_for(d) for d in q.get("expected_domain", []))
        for tag in tags:
            if tag in TEMPLATE_TOKENS:   # 模板/证据分级固定词，非知识词，豁免
                continue
            if tag not in corpus:
                fails.append((q["id"], tag, q.get("expected_domain", [])))
    return fails


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", choices=["route", "tag"])
    args = ap.parse_args()

    questions = load_gold()
    exit_code = 0

    if args.only in (None, "route"):
        print(f"[ROUTE] 检查 {len(questions)} 题路由契约 …")
        errors, warns = audit_route(questions)
        for qid, exp, act in errors:
            print(f"  ✗ ERROR {qid}: 实际 {act} 均无 YAML → 知识静默跳过（expected {exp}）")
        for qid, exp, act in warns:
            print(f"  ⚠ WARN  {qid}: 路由 {act} 有 YAML 但 ≠ gold {exp}（复核 gold 是否陈旧）")
        if errors:
            exit_code = 1
        print(f"[ROUTE] {len(errors)} ERROR / {len(warns)} WARN"
              f" {'✓' if not errors else '✗'}\n")

    if args.only in (None, "tag"):
        print("[TAG] 检查 doctor_must_have_tags 接地 …")
        fails = audit_tags(questions)
        if fails:
            exit_code = 1
            for qid, tag, doms in fails:
                print(f"  ✗ {qid}: 标签「{tag}」未出现在 {doms} 的 YAML 中（疑为元描述）")
        print(f"[TAG] {'通过 ✓' if not fails else f'{len(fails)} 个标签可疑 ✗'}")

    sys.exit(exit_code)


if __name__ == "__main__":
    main()
