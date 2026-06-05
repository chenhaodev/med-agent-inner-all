#!/usr/bin/env python3
"""
ingest.py — PDF → 章节 Markdown（按专科切分，保留页码标注）

用法：
  python3 bin/ingest.py --specialty cardiology
  python3 bin/ingest.py --specialty all
  python3 bin/ingest.py --list-specialties

输出：source/chapters/{specialty}/{chapter_slug}.md
      每段文字前标注 [p.{页码}]
"""

import argparse
import re
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).parent.parent

try:
    import fitz  # PyMuPDF
except ImportError:
    print("错误：需要 pymupdf。运行 pip install pymupdf", file=sys.stderr)
    sys.exit(1)

# ─── 专科→PDF 部分/页范围映射 ─────────────────────────────────────────────────
# 根据《西氏内科学精要》（Cecil Essentials）上下卷目录实际页范围填写
# 上卷：西氏内科学精要-上卷.pdf（约 637页，PDF页从1起）
# 下卷：西氏内科学精要-下卷.pdf（约 632页）
# 注：页码为 PDF 文件内页（非书页码），请根据实际目录调整

CHAPTER_MAP = {
    # 上卷各部分
    "cardiology": {
        "pdf": "西氏内科学精要-上卷.pdf",
        "chapters": [
            # Ch12 血管疾病和高血压 (p189-211), Ch5 心力衰竭与心肌病 (p79-91),
            # Ch8 冠状动脉性心脏病 (p113-136), Ch9 心律失常 (p137-163)
            {"slug": "hypertension",  "title": "血管疾病和高血压",       "pages": (189, 211)},
            {"slug": "heart_failure", "title": "心力衰竭与心肌病",       "pages": (79,  91)},
            {"slug": "cad",          "title": "冠状动脉性心脏病",       "pages": (113, 136)},
            {"slug": "arrhythmia",   "title": "心律失常",               "pages": (137, 163)},
        ]
    },
    "respiratory": {
        "pdf": "西氏内科学精要-上卷.pdf",
        "chapters": [
            # Ch16 阻塞性肺疾病（含COPD+哮喘）(p240-255), Ch21 肺部感染 (p289-301)
            {"slug": "copd",      "title": "阻塞性肺疾病（COPD与哮喘）", "pages": (240, 255)},
            {"slug": "asthma",    "title": "阻塞性肺疾病（哮喘部分）",   "pages": (240, 255)},
            {"slug": "pneumonia", "title": "肺部感染性疾病",             "pages": (289, 301)},
        ]
    },
    "renal": {
        "pdf": "西氏内科学精要-上卷.pdf",
        "chapters": [
            # Ch32 慢性肾脏病 (p406-414), Ch28 肾小球疾病 (p353-368)
            {"slug": "ckd",       "title": "慢性肾脏病",   "pages": (406, 414)},
            {"slug": "nephritis", "title": "肾小球疾病",   "pages": (353, 368)},
        ]
    },
    "digestive": {
        "pdf": "西氏内科学精要-上卷.pdf",
        "chapters": [
            # Ch41+43 肝炎+肝硬化 (p500-522), Ch36 胃与十二指肠 (p451-466), Ch37 IBD (p467-476)
            {"slug": "liver", "title": "急性与慢性肝炎及肝硬化",   "pages": (500, 522)},
            {"slug": "gi",    "title": "胃与十二指肠疾病",          "pages": (451, 466)},
            {"slug": "ibd",   "title": "炎性肠病",                  "pages": (467, 476)},
        ]
    },
    "hematology": {
        "pdf": "西氏内科学精要-上卷.pdf",
        "chapters": [
            # Ch47 红细胞相关疾病（贫血）(p558-570)
            {"slug": "anemia", "title": "红细胞相关疾病（贫血）", "pages": (558, 570)},
        ]
    },
    # 下卷各部分
    "endocrine": {
        "pdf": "西氏内科学精要-下卷.pdf",
        "chapters": [
            # Ch66 糖尿病 (p99-117), Ch63 甲状腺 (p73-82),
            # Ch69 脂代谢紊乱 (p133-142), Ch67 肥胖 (p118-125)
            {"slug": "diabetes_t2",  "title": "糖尿病与低血糖症",   "pages": (99,  117)},
            {"slug": "thyroid",      "title": "甲状腺疾病",          "pages": (73,  82)},
            {"slug": "dyslipidemia", "title": "脂代谢紊乱",          "pages": (133, 142)},
            {"slug": "gout",         "title": "晶体性关节炎：痛风",  "pages": (255, 260)},
            {"slug": "obesity",      "title": "肥胖症",              "pages": (118, 125)},
        ]
    },
    "rheumatology": {
        "pdf": "西氏内科学精要-下卷.pdf",
        "chapters": [
            # Ch77 类风湿 (p223-228), Ch79 SLE (p234-241), Ch75 骨质疏松 (p207-215)
            {"slug": "ra",           "title": "类风湿关节炎",    "pages": (223, 228)},
            {"slug": "sle",          "title": "系统性红斑狼疮",  "pages": (234, 241)},
            {"slug": "osteoporosis", "title": "骨质疏松症",      "pages": (207, 215)},
        ]
    },
    "infectious": {
        "pdf": "西氏内科学精要-下卷.pdf",
        "chapters": [
            # Ch88 发热 (p294-305), Ch89 菌血症 (p306-313), Ch92 下呼吸道感染 (p336-340),
            # Ch98 尿路感染 (p378-380), Ch101 HIV (p398-414)
            {"slug": "general", "title": "感染性疾病（发热/脓毒症/下呼吸道/尿路/HIV）",
             "pages": (294, 430)},
        ]
    },
}


def extract_pages(pdf_path: Path, start_page: int, end_page: int) -> list[tuple[int, str]]:
    """从 PDF 中提取指定页范围的文本，返回 [(页码, 文本)] 列表。"""
    doc = fitz.open(str(pdf_path))
    total = len(doc)
    result = []
    for pn in range(start_page - 1, min(end_page, total)):
        page = doc[pn]
        text = page.get_text("text")
        if text.strip():
            result.append((pn + 1, text))
    doc.close()
    return result


def pages_to_markdown(pages: list[tuple[int, str]], title: str) -> str:
    """将页面文本列表转为带页码标注的 Markdown。"""
    lines = [f"# {title}\n"]
    for page_num, text in pages:
        lines.append(f"\n[p.{page_num}]\n")
        # 清理多余空行
        cleaned = re.sub(r'\n{3,}', '\n\n', text.strip())
        lines.append(cleaned)
    return "\n".join(lines)


def ingest_specialty(specialty: str) -> None:
    if specialty not in CHAPTER_MAP:
        print(f"错误：未知专科 '{specialty}'。可用：{list(CHAPTER_MAP.keys())}", file=sys.stderr)
        sys.exit(1)

    config = CHAPTER_MAP[specialty]
    pdf_path = ROOT_DIR / "pdfs" / config["pdf"]

    if not pdf_path.exists():
        print(f"错误：PDF 文件不存在：{pdf_path}", file=sys.stderr)
        print("请将 PDF 放入 pdfs/ 目录（该目录已 git-ignored）。", file=sys.stderr)
        sys.exit(1)

    out_dir = ROOT_DIR / "source" / "chapters" / specialty
    out_dir.mkdir(parents=True, exist_ok=True)

    for ch in config["chapters"]:
        slug = ch["slug"]
        title = ch["title"]
        start, end = ch["pages"]

        print(f"  [{specialty}/{slug}] 提取 p.{start}-{end} ...")
        pages = extract_pages(pdf_path, start, end)

        if not pages:
            print(f"    警告：未提取到任何文本，跳过。")
            continue

        md = pages_to_markdown(pages, title)
        out_file = out_dir / f"{slug}.md"
        out_file.write_text(md, encoding="utf-8")
        print(f"    → {out_file}  ({len(pages)} 页, {len(md)} 字符)")


def main() -> None:
    parser = argparse.ArgumentParser(description="PDF → 章节 Markdown 抽取工具")
    parser.add_argument("--specialty", default="all", help="专科名称，或 'all' 处理全部")
    parser.add_argument("--list-specialties", action="store_true", help="列出所有可用专科")
    args = parser.parse_args()

    if args.list_specialties:
        for sp in CHAPTER_MAP:
            chs = CHAPTER_MAP[sp]["chapters"]
            print(f"  {sp}: {[c['slug'] for c in chs]}")
        return

    if args.specialty == "all":
        specialties = list(CHAPTER_MAP.keys())
    else:
        specialties = [args.specialty]

    print(f"开始 ingest：{specialties}")
    for sp in specialties:
        print(f"\n专科：{sp}")
        ingest_specialty(sp)

    print("\n完成。请检查 source/chapters/ 目录。")


if __name__ == "__main__":
    main()
