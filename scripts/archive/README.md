# scripts/archive — 一次性脚手架（已退役）

知识库构建期的一次性脚本，无任何运行时/eval 引用。归档于此保留可复现性
（重建知识库时可参考），不再随主流程运行。

| 脚本 | 历史用途 |
|------|---------|
| `apply_gap_entries.py` | 批量补知识缺口条目 |
| `fill_gaps.py` | 知识缺口填充 |
| `remap_source_page.py` | `source_page` 批量重映射 |
| `audit_eval_gold.py` | gold 集旧版审计（已被 `bin/audit_routing.py` 取代） |
| `build_mode_gold.py` | 双模式 gold 生成 |

当前活跃的审计门禁见 `bin/audit_routing.py` / `bin/audit_grounding.py` /
`bin/audit_schema.py`；知识摄取见 `bin/ingest.py`（依赖 `bin/build_chapter_map.py`，仍在 bin/）。
