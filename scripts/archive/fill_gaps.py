#!/usr/bin/env python3
"""
fill_gaps.py — 自动填补 COVERAGE_GAP：读源文 → 找 folio → 提取上下文 → 写入 YAML

用法：
  python3 bin/fill_gaps.py                # 处理所有 gaps
  python3 bin/fill_gaps.py --dry-run      # 只打印，不写文件
  python3 bin/fill_gaps.py cardiology/heart_failure  # 指定章节
"""

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "bin"))

import yaml
from folio_map import build_folio_map

# ── Header/formatting line patterns to skip ───────────────────
SKIP_RE = re.compile(
    r"^\s*$"                        # blank
    r"|^\s*\d{1,4}\s*$"            # standalone page number
    r"|.*[│┤├─].*"                  # table / chapter header box
    r"|^#+\s"                       # markdown heading
    r"|^\[p\."                      # page marker
    r"|^第\s*\d+\s*[章部节]"        # chapter/section titles
)

# ── Sentence-split helpers ────────────────────────────────────
def clean_lines(text: str, keyword: str) -> list[str]:
    """Return cleaned lines from a page text block."""
    out = []
    for line in text.splitlines():
        line = line.strip()
        if not line or SKIP_RE.match(line):
            continue
        out.append(line)
    return out


def extract_context(text: str, keyword: str, max_lines: int = 6) -> list[str]:
    """Find lines containing keyword and surrounding context."""
    lines = clean_lines(text, keyword)
    if not lines:
        return []

    # Gather indices of lines containing the keyword
    kw_indices = [i for i, l in enumerate(lines) if keyword in l]
    if not kw_indices:
        # keyword might be in original text but split across lines — return first N lines
        return lines[:max_lines]

    # Collect window around first occurrence
    best_i = kw_indices[0]
    window = set(range(max(0, best_i - 1), min(len(lines), best_i + 3)))
    # Also pull adjacent keyword lines
    for i in kw_indices[1:3]:
        window.update(range(max(0, i - 1), min(len(lines), i + 2)))

    collected = [lines[i] for i in sorted(window)][:max_lines]
    return collected


def find_best_page_for_keyword(
    md_path: Path, keyword: str, folio_map: dict[int, int]
) -> tuple[int | None, int | None, str]:
    """Return (folio, phys_page, text_block) for the page with most keyword hits."""
    text = md_path.read_text(encoding="utf-8")
    PAGE_RE = re.compile(r"^\[p\.(\d+)", re.MULTILINE)

    # Split into page blocks
    blocks = []
    positions = [(m.start(), int(m.group(1))) for m in PAGE_RE.finditer(text)]
    for idx, (pos, phys) in enumerate(positions):
        end = positions[idx + 1][0] if idx + 1 < len(positions) else len(text)
        block_text = text[pos:end]
        count = block_text.count(keyword)
        if count > 0:
            blocks.append((count, phys, block_text))

    if not blocks:
        return None, None, ""

    blocks.sort(reverse=True)
    _, best_phys, best_text = blocks[0]
    folio = folio_map.get(best_phys)
    return folio, best_phys, best_text


def make_key_points(context_lines: list[str], keyword: str) -> list[str]:
    """Turn context lines into 2-3 patient-facing key_points."""
    kps = []
    for line in context_lines:
        # Merge short consecutive lines (OCR line-wrap artifacts)
        cleaned = re.sub(r"\s+", "", line)  # remove whitespace for length check
        if len(cleaned) < 8:
            continue
        # Trim to ≤60 chars for readability
        if len(line) > 65:
            # Try to cut at a natural pause
            for sep in ["，", "。", "；", "、"]:
                idx = line.find(sep, 20)
                if 20 <= idx <= 65:
                    line = line[: idx + 1]
                    break
            else:
                line = line[:65]
        kps.append(line)
        if len(kps) >= 3:
            break

    if not kps:
        kps = [f"详见教材相关章节"]
    return kps


# ── YAML append helper ────────────────────────────────────────

def load_yaml(path: Path) -> dict:
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def save_yaml(path: Path, data: dict) -> None:
    """Write YAML preserving structure; entries use block style."""
    # We write manually to preserve list style and avoid yaml.dump quoting issues
    lines = []
    # Top-level scalars
    for key in ("specialty", "specialty_zh", "disease", "disease_zh", "source"):
        if key in data:
            lines.append(f"{key}: {data[key]}")
    lines.append("entries:")

    for entry in data.get("entries", []):
        lines.append(f"- id: {entry['id']}")
        lines.append(f"  title: {entry['title']}")
        lines.append(f"  source_page: {entry['source_page']}")
        lines.append(f"  evidence_level: {entry.get('evidence_level', '未注明')}")
        lines.append(f"  recommendation: {entry.get('recommendation', '未注明')}")
        lines.append("  key_points:")
        for kp in entry.get("key_points", []):
            lines.append(f"  - {kp}")
        if "pdf_page" in entry:
            lines.append(f"  pdf_page: {entry['pdf_page']}")
        if "must_warn" in entry:
            lines.append("  must_warn:")
            for w in entry["must_warn"]:
                lines.append(f"  - {w}")

    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def entry_id_exists(data: dict, entry_id: str) -> bool:
    return any(e.get("id") == entry_id for e in data.get("entries", []))


def keyword_covered(data: dict, keyword: str) -> bool:
    """Check if keyword already appears in any key_point or title."""
    for e in data.get("entries", []):
        text = e.get("title", "") + " ".join(e.get("key_points", []))
        if keyword in text:
            return True
    return False


# ── Gap definitions ───────────────────────────────────────────
# Each tuple: (specialty, disease, [keywords])
GAPS: list[tuple[str, str, list[str]]] = [
    ("bone_mineral", "metabolic_bone",    ["体力活动"]),
    ("bone_mineral", "osteoporosis",      ["体力活动", "生活方式"]),
    ("cardiology",   "arrhythmia",        ["运动"]),
    ("cardiology",   "cad",               ["体力活动", "康复"]),
    ("cardiology",   "heart_failure",     ["体力活动", "饮食"]),
    ("digestive",    "gi",                ["运动"]),
    ("digestive",    "liver",             ["运动", "饮食", "康复"]),
    ("endocrine",    "obesity",           ["锻炼", "体力活动"]),
    ("endocrine",    "thyroid",           ["运动", "饮食"]),
    ("geriatrics",   "elderly_care",      ["运动", "饮食", "生活方式", "康复", "居家护理"]),
    ("infectious",   "general",           ["运动", "康复"]),
    ("mens_health",  "mens_health",       ["运动", "饮食"]),
    ("neurology",    "epilepsy",          ["饮食", "戒酒", "康复"]),
    ("neurology",    "headache_pain",     ["运动"]),
    ("neurology",    "movement_disorders",["体力活动"]),
    ("neurology",    "stroke",            ["体力活动", "康复"]),
    ("palliative",   "palliative_care",   ["运动", "饮食", "康复", "家庭护理"]),
    ("perioperative","periop_management", ["康复"]),
    ("renal",        "ckd",               ["运动", "戒烟", "康复"]),
    ("renal",        "nephritis",         ["运动"]),
    ("respiratory",  "asthma",            ["戒烟", "康复"]),
    ("respiratory",  "copd",              ["运动"]),
    ("respiratory",  "pneumonia",         ["运动"]),
    ("rheumatology", "osteoporosis",      ["体力活动", "生活方式"]),
    ("rheumatology", "sle",               ["运动", "体力活动"]),
    ("substance_use","alcohol_drugs",     ["运动", "饮食", "戒酒", "康复"]),
    ("womens_health","womens_health",     ["运动", "饮食", "戒烟"]),
]

# ── Keyword → entry ID suffix and title template ─────────────
KW_META = {
    "运动":   ("EXERCISE",    "{disease_zh}运动指导"),
    "锻炼":   ("EXERCISE",    "{disease_zh}锻炼建议"),
    "体力活动":("EXERCISE",   "{disease_zh}体力活动建议"),
    "饮食":   ("DIET",        "{disease_zh}饮食管理"),
    "生活方式":("LIFESTYLE",  "{disease_zh}生活方式管理"),
    "康复":   ("REHAB",       "{disease_zh}康复指导"),
    "戒烟":   ("SMOKING",     "{disease_zh}戒烟建议"),
    "戒酒":   ("ALCOHOL",     "{disease_zh}戒酒建议"),
    "居家护理":("HOME_CARE",  "{disease_zh}居家护理要点"),
    "家庭护理":("HOME_CARE",  "{disease_zh}家庭护理要点"),
}

# ── Keyword groups: related keywords share one entry ─────────
# Keys that collapse into a single entry for a chapter
KW_GROUPS = [
    {"运动", "锻炼", "体力活动"},   # → EXERCISE entry
    {"饮食", "生活方式"},            # → DIET/LIFESTYLE entry (lifestyle covers diet)
    {"康复"},
    {"戒烟"},
    {"戒酒"},
    {"居家护理", "家庭护理"},
]


def group_keywords(kws: list[str]) -> list[list[str]]:
    """Group related keywords so they produce one entry per group."""
    remaining = set(kws)
    groups = []
    for g in KW_GROUPS:
        hit = remaining & g
        if hit:
            groups.append(sorted(hit))
            remaining -= hit
    for kw in sorted(remaining):
        groups.append([kw])
    return groups


# ── Main processing ───────────────────────────────────────────

def process_chapter(
    specialty: str, disease: str, keywords: list[str], dry_run: bool
) -> int:
    """Process one chapter. Returns number of entries added."""
    yaml_path = ROOT / "knowledge" / specialty / f"{disease}.yaml"
    md_path   = ROOT / "source" / "chapters" / specialty / f"{disease}.md"

    if not yaml_path.exists():
        print(f"  SKIP {specialty}/{disease}: YAML not found")
        return 0
    if not md_path.exists():
        print(f"  SKIP {specialty}/{disease}: source md not found")
        return 0

    data = load_yaml(yaml_path)
    fm   = build_folio_map(md_path)
    disease_zh = data.get("disease_zh", disease)

    # Determine entry prefix from specialty
    prefix = {
        "bone_mineral": "BM", "cardiology": "CARD", "digestive": "DIG",
        "endocrine": "ENDO", "geriatrics": "GER", "hematology": "HEM",
        "infectious": "INF", "mens_health": "MH", "neurology": "NEURO",
        "oncology": "ONC", "palliative": "PAL", "perioperative": "PERI",
        "renal": "REN", "respiratory": "RESP", "rheumatology": "RHE",
        "substance_use": "SUB", "womens_health": "WH",
    }.get(specialty, specialty[:4].upper())

    added = 0
    kw_groups = group_keywords(keywords)

    for grp in kw_groups:
        # Pick primary keyword for this group
        primary = grp[0]
        meta = KW_META.get(primary, ("LIFESTYLE", f"{disease_zh}生活方式建议"))
        suffix, title_tmpl = meta
        title = title_tmpl.format(disease_zh=disease_zh)

        entry_id = f"{prefix}_{disease.upper()[:8]}_{suffix}"

        # Skip if already covered
        if entry_id_exists(data, entry_id):
            print(f"  SKIP (id exists)  {entry_id}")
            continue
        if all(keyword_covered(data, kw) for kw in grp):
            print(f"  SKIP (covered)    {grp} in {specialty}/{disease}")
            continue

        # Find best folio for any keyword in the group
        best_folio, best_phys, best_text = None, None, ""
        for kw in grp:
            f, p, t = find_best_page_for_keyword(md_path, kw, fm)
            if f is not None and best_folio is None:
                best_folio, best_phys, best_text = f, p, t

        if best_folio is None:
            # fallback: use last known folio of chapter
            if fm:
                best_phys = max(fm, key=fm.get)
                best_folio = fm[best_phys]
                best_text = ""
            else:
                print(f"  ERROR no folio found for {specialty}/{disease} {grp}")
                continue

        # Extract context lines combining all group keywords
        all_context = []
        for kw in grp:
            ctx = extract_context(best_text, kw, max_lines=4)
            for line in ctx:
                if line not in all_context:
                    all_context.append(line)
        kps = make_key_points(all_context, primary)

        entry = {
            "id":              entry_id,
            "title":           title,
            "source_page":     best_folio,
            "evidence_level":  "未注明",
            "recommendation":  "未注明",
            "key_points":      kps,
            "pdf_page":        best_phys,
        }

        print(f"  ADD {entry_id}  folio={best_folio}  kps={kps}")

        if not dry_run:
            data["entries"].append(entry)
            added += 1

    if added > 0 and not dry_run:
        save_yaml(yaml_path, data)
        print(f"  Saved {yaml_path.name} ({added} new entries)")

    return added


def main() -> None:
    dry_run = "--dry-run" in sys.argv
    filter_arg = next((a for a in sys.argv[1:] if "/" in a), None)

    total = 0
    for specialty, disease, keywords in GAPS:
        tag = f"{specialty}/{disease}"
        if filter_arg and filter_arg != tag:
            continue
        print(f"\n── {tag}  gaps={keywords}")
        n = process_chapter(specialty, disease, keywords, dry_run)
        total += n

    print(f"\n{'DRY RUN — ' if dry_run else ''}共添加 {total} 条新 entries")


if __name__ == "__main__":
    main()
