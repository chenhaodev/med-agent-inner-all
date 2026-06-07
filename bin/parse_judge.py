#!/usr/bin/env python3
"""parse_judge.py — 健壮解析判官（judge）响应里的四维打分。

输入：判官原始响应文本（stdin）。
输出：规范化 JSON（stdout）：
    {"coverage":N,"accuracy":N,"safety":N,"grounding":N,
     "flags":[...],"ok":bool,"error":str|null}

退出码：
    0  成功提取四维分数（严格解析或正则兜底全部命中）。
    3  无法提取分数（无 JSON 对象 / 正则零命中）→ 调用方可据此用 --no-cache 重跑判官一次。

设计动机：判官有时在字符串值里写入未转义的中文引号或嵌套结构，
导致 json.loads 在前几十字符就报 "Expecting ',' delimiter"，
旧逻辑直接判 0/40（如 ONCO_LIFESTYLE_01）。本工具改为：
严格解析 → 轻量修复 → 逐维正则兜底，确保分数不因格式噪声丢失。
"""
import json
import re
import sys

DIMS = ("coverage", "accuracy", "safety", "grounding")


def _extract_balanced(text):
    """从首个 '{' 起按括号配平截取 JSON 对象子串（尊重字符串与转义）。

    对良构字符串可精确定位对象边界，避免贪婪 `\\{.*\\}` 把尾随散文一并吞入。
    若字符串内有未转义引号导致配平错乱，返回值仍会让 json.loads 失败，
    从而落到正则兜底——是安全的。
    """
    start = text.find("{")
    if start < 0:
        return None
    depth = 0
    in_str = False
    esc = False
    for i in range(start, len(text)):
        c = text[i]
        if esc:
            esc = False
            continue
        if c == "\\":
            esc = True
            continue
        if c == '"':
            in_str = not in_str
            continue
        if in_str:
            continue
        if c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                return text[start : i + 1]
    return text[start:]  # 未配平（疑似截断）→ 返回剩余部分交给后续兜底


def _strict_parse(obj_str):
    """严格 json.loads + 一次轻量修复（去尾随逗号）。成功返回 dict，否则 None。"""
    candidates = [obj_str, re.sub(r",(\s*[}\]])", r"\1", obj_str)]
    for cand in candidates:
        try:
            return json.loads(cand)
        except json.JSONDecodeError:
            continue
    return None


def _score_of(data, dim):
    """从结构化 dict 取某维 score；兼容 {"score":N} 与裸数字两种形态。"""
    v = data.get(dim)
    if isinstance(v, dict):
        return int(v.get("score", 0) or 0)
    if isinstance(v, (int, float)):
        return int(v)
    return 0


def _regex_scores(raw):
    """逐维正则兜底：从原始文本直接抓 "<dim>": {... "score": N ...}。

    操作原始文本而非配平子串，因而不受未转义引号 / 配平错乱影响。
    返回 (scores_dict, hit_count)。
    """
    scores = {}
    hits = 0
    for dim in DIMS:
        m = re.search(
            rf'"{dim}"\s*:\s*\{{[^{{}}]*?"score"\s*:\s*(\d+)', raw, re.DOTALL
        )
        if not m:
            # 退一步：兼容 "coverage": 8 这类扁平写法
            m = re.search(rf'"{dim}"\s*:\s*(\d+)', raw)
        if m:
            scores[dim] = int(m.group(1))
            hits += 1
        else:
            scores[dim] = 0
    return scores, hits


def _regex_flags(raw):
    """尽力提取 flags 数组中的引号字符串（兜底用）。"""
    m = re.search(r'"flags"\s*:\s*\[(.*?)\]', raw, re.DOTALL)
    if not m:
        return []
    return re.findall(r'"((?:[^"\\]|\\.)*)"', m.group(1))


def parse(raw):
    """返回 (result_dict, ok)。ok=False 表示分数不可信，建议重跑判官。"""
    raw = (raw or "").strip()
    obj_str = _extract_balanced(raw)

    if obj_str:
        normalized = obj_str.replace("\n", " ").replace("\r", " ")
        data = _strict_parse(normalized)
        if data is not None:
            return {
                "coverage": _score_of(data, "coverage"),
                "accuracy": _score_of(data, "accuracy"),
                "safety": _score_of(data, "safety"),
                "grounding": _score_of(data, "grounding"),
                "flags": list(data.get("flags", []) or []),
                "ok": True,
                "error": None,
            }, True

    # 严格解析失败 → 逐维正则兜底（作用于原始文本）
    scores, hits = _regex_scores(raw)
    if hits >= len(DIMS):  # 四维全部命中 → 视为已恢复，可信
        return {
            **scores,
            "flags": _regex_flags(raw),
            "ok": True,
            "error": None,
        }, True

    # 兜底也无法凑齐四维 → 标记不可信，交由调用方决定是否重跑
    return {
        **scores,
        "flags": _regex_flags(raw) or [f"判官响应无法解析（仅命中 {hits}/4 维分数）"],
        "ok": False,
        "error": (obj_str or raw)[:200],
    }, False


def main():
    raw = sys.stdin.read()
    result, ok = parse(raw)
    print(json.dumps(result, ensure_ascii=False))
    sys.exit(0 if ok else 3)


if __name__ == "__main__":
    main()
