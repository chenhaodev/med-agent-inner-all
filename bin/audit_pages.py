#!/usr/bin/env python3
"""审计 knowledge YAML 的 source_page 是否与 source/chapters 的实际页码一致。

方法：对每个 entry 从 title+key_points 抽取"锚点词"（CJK 片段/药名/数字），
统计每个 [p.NN] 页块包含多少锚点词，找出最匹配页(best)，与 YAML 声称页比较。

输出每个 entry：claimed 页命中数 vs best 页命中数 —— 用于人工复核。
不修改任何文件。
"""
import sys, re, yaml
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
KN = ROOT / "knowledge"
SRC = ROOT / "source" / "chapters"

PAGE_RE = re.compile(r"^\[p\.(\d+)\]\s*$")
# 抽锚点：长度≥2 的 CJK 串，或 数字(+单位)，或 拉丁药名/缩写
CJK = r"一-鿿"
TOKEN_RE = re.compile(rf"[{CJK}]{{2,8}}|[A-Za-z][A-Za-z0-9\-]{{2,}}|\d+(?:\.\d+)?")

# 停用词：太常见，不具区分度
STOP = set("患者疾病治疗症状建议医生就医注意可能没有需要进行通过包括以及如果出现这是什么日常常见误区依据管理控制增加降低正常异常情况问题方法检查评估".split())

def tokens(text):
    out = set()
    for m in TOKEN_RE.findall(text):
        if m in STOP:
            continue
        if re.fullmatch(rf"[{CJK}]{{2,8}}", m):
            # 进一步切：把长串也加入 + 2gram 提高命中
            out.add(m)
        else:
            out.add(m)
    return out

def load_pages(md_path):
    """返回 [(page_no, text_block)]，按出现顺序。"""
    pages = []
    cur_page, buf = None, []
    for line in md_path.read_text(encoding="utf-8").splitlines():
        m = PAGE_RE.match(line.strip())
        if m:
            if cur_page is not None:
                pages.append((cur_page, "\n".join(buf)))
            cur_page, buf = int(m.group(1)), []
        else:
            buf.append(line)
    if cur_page is not None:
        pages.append((cur_page, "\n".join(buf)))
    return pages

def best_pages(anchor, pages):
    scored = []
    for pno, txt in pages:
        hits = sum(1 for a in anchor if a in txt)
        scored.append((hits, pno))
    scored.sort(reverse=True)
    return scored

def audit_disease(spec, disease):
    yaml_path = KN / spec / f"{disease}.yaml"
    md_path = SRC / spec / f"{disease}.md"
    if not yaml_path.exists() or not md_path.exists():
        return
    data = yaml.safe_load(yaml_path.read_text(encoding="utf-8"))
    pages = load_pages(md_path)
    page_nums = [p for p, _ in pages]
    pmin, pmax = min(page_nums), max(page_nums)
    page_text = {p: t for p, t in pages}
    print(f"\n===== {spec}/{disease}  (PDF p.{pmin}-{pmax}, {len(pages)}页) =====")
    for e in data.get("entries", []):
        claimed = e.get("source_page")
        anchor = set()
        anchor |= tokens(e.get("title", ""))
        for kp in e.get("key_points", []):
            anchor |= tokens(kp)
        anchor = {a for a in anchor if len(a) >= 2}
        scored = best_pages(anchor, pages)
        best_hits, best_pno = scored[0] if scored else (0, None)
        claimed_hits = sum(1 for a in anchor if a in page_text.get(claimed, ""))
        # 也看 claimed±1 页（内容常跨页）
        neigh_hits = max(
            (sum(1 for a in anchor if a in page_text.get(claimed + d, "")) for d in (-1, 0, 1)),
            default=0,
        )
        flag = ""
        if claimed not in page_nums:
            flag = "‼ claimed页不在本章范围"
        elif neigh_hits == 0:
            flag = "‼ claimed页±1零命中"
        elif best_hits >= claimed_hits + 3 and abs(best_pno - claimed) > 1:
            flag = f"⚠ best=p.{best_pno}({best_hits}) 远高于 claimed"
        top3 = " ".join(f"p.{p}:{h}" for h, p in scored[:3])
        if flag:
            print(f"  [{e.get('id'):24}] claimed p.{claimed}(命中{claimed_hits},邻{neigh_hits}) | top: {top3}  {flag}")
        else:
            print(f"  [{e.get('id'):24}] claimed p.{claimed}(命中{claimed_hits}) ✓ | top: {top3}")

TARGETS = [
    ("digestive", ["gi", "ibd", "liver"]),
    ("endocrine", ["diabetes_t2", "dyslipidemia", "gout", "obesity", "thyroid"]),
    ("hematology", ["anemia"]),
    ("infectious", ["general"]),
    ("renal", ["ckd", "nephritis"]),
    ("respiratory", ["asthma", "copd", "pneumonia"]),
    ("rheumatology", ["osteoporosis", "ra", "sle"]),
]

if __name__ == "__main__":
    for spec, diseases in TARGETS:
        for d in diseases:
            audit_disease(spec, d)
