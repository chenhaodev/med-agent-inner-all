#!/usr/bin/env python3
"""
remap_source_page.py — 将所有 knowledge YAML 的 source_page 从 PDF 物理页改写为印刷页码(folio)。

逻辑：
  1. 扫描 knowledge/**/*.yaml（跳过 chapters.yaml 和 guidelines/）
  2. 对每个文件，从 source/chapters/<specialty>/<slug>.md 建立 {物理页: folio} 映射
  3. 将每条 entry 的 source_page（物理页）改为 folio，并将原值写入 pdf_page 备查
  4. 跳过已有 pdf_page 的条目（已迁移）

用法：
  python3 bin/remap_source_page.py              # 就地改写所有 YAML
  python3 bin/remap_source_page.py --dry-run    # 只打印，不改写
  python3 bin/remap_source_page.py knowledge/neurology/dementia.yaml  # 指定文件
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "bin"))

try:
    from folio_map import build_folio_map
except ImportError:
    print("错误：需要 bin/folio_map.py", file=sys.stderr)
    sys.exit(1)

try:
    import yaml
except ImportError:
    print("错误：需要 pyyaml。pip install pyyaml", file=sys.stderr)
    sys.exit(1)


def remap_yaml(yaml_path: Path, dry_run: bool = False) -> int:
    """就地改写 source_page→folio。返回改写的条目数。"""
    rel = yaml_path.relative_to(ROOT / "knowledge")
    md_path = ROOT / "source" / "chapters" / rel.with_suffix(".md")

    if not md_path.exists():
        print(f"  SKIP (source md 不存在: {md_path.relative_to(ROOT)})")
        return 0

    folio_map = build_folio_map(md_path)
    if not folio_map:
        print(f"  SKIP (空 folio map)")
        return 0

    raw = yaml_path.read_text(encoding="utf-8")
    data = yaml.safe_load(raw)
    entries = data.get("entries", [])
    remapped = 0
    new_entries = []

    for entry in entries:
        if "pdf_page" in entry:
            new_entries.append(entry)
            continue

        phys = entry.get("source_page")
        if phys is None:
            new_entries.append(entry)
            continue

        folio = folio_map.get(int(phys))
        if folio is None:
            print(f"    ⚠  {entry.get('id', '?'):28s} phys {phys} 不在 folio map 范围 "
                  f"({min(folio_map)}-{max(folio_map)})，跳过")
            new_entries.append(entry)
            continue

        if folio == phys:
            new_entries.append(entry)
            continue

        print(f"    {entry.get('id', '?'):28s} phys {phys:4d} → folio {folio}")
        new_entry = dict(entry)
        new_entry["source_page"] = folio
        new_entry["pdf_page"] = phys
        new_entries.append(new_entry)
        remapped += 1

    if remapped > 0 and not dry_run:
        new_data = dict(data)
        new_data["entries"] = new_entries
        with yaml_path.open("w", encoding="utf-8") as f:
            yaml.dump(new_data, f, allow_unicode=True, default_flow_style=False, sort_keys=False)

    return remapped


def main() -> None:
    dry_run = "--dry-run" in sys.argv
    args = [a for a in sys.argv[1:] if not a.startswith("-")]

    if args:
        targets = [ROOT / a if not Path(a).is_absolute() else Path(a) for a in args]
    else:
        targets = sorted((ROOT / "knowledge").rglob("*.yaml"))
        targets = [
            t for t in targets
            if t.name != "chapters.yaml" and "guidelines" not in str(t)
        ]

    total = 0
    for p in targets:
        if not p.exists():
            print(f"SKIP {p}: not found")
            continue
        print(f"\n─── {p.relative_to(ROOT)} ───")
        n = remap_yaml(p, dry_run=dry_run)
        if n:
            print(f"    → {n} 条目已{'(dry-run)' if dry_run else ''}改写")
        total += n

    mode = " [DRY RUN]" if dry_run else ""
    print(f"\n完成{mode}：共改写 {total} 条目的 source_page → folio")


if __name__ == "__main__":
    main()
