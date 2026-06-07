# 下步计划 / Roadmap

> 状态快照：2026-06-07。基于对当前仓库 + 最近一次 eval 结果（`eval/results/2026-06-07_09-*`）的审视。

---

## ⚠️ 首要问题：v3 指标是过期的

README / CHANGELOG 公布的 v3 指标（patient 38.9·99.1% / doctor 37.2·88.1%）测的是**修复前**的代码：

| 时间 | 事件 |
|------|------|
| 09:45 / 09:55 | patient / doctor eval 跑完 → 即当前公布的数字 |
| 10:53–11:43 | PE 路由、癌痛路由、gold 标签自然化、9 个契约缺陷、YAML 去重 **全部在 eval 之后才提交** |
| 11:57 | CHANGELOG 将这些数字作为 v3 发布指标 |

现场验证（当前 router 行为已变）：

- `肺栓塞` → `hematology:thrombosis` ✓（eval 时为 respiratory:general，该题失败）
- `癌痛` → `oncology:tumor_complications` ✓（eval 时为 oncology:general，该题失败）

**结论**：重跑后 doctor 通过率大概率高于 88.1%，当前数字低估 v3。发布说明的数字在重跑前站不住。

---

## P0 — 重跑 eval，刷新真实 v3 指标

```bash
python3 bin/audit_routing.py        # 门禁：0 ERROR / 0 WARN 才继续
./bin/eval.sh --mode both           # ~30 min
```

完成后用真实数字更新 README「性能指标」表与 CHANGELOG v3「指标」表。

---

## P1 — 两个具体 bug（重跑时一并确认是否已随修复消失）

| ID | 现象 | 判断 |
|----|------|------|
| `AKI_MONITOR_01` | 仅得 10/40，回答被截断（"仅开头部分，缺少多个必要段落"） | 疑似 max_tokens 或流中断的生成 bug；单题即拉低整体均分。若可复现是真 bug，查 `call_deepseek.sh` 的 max_tokens / 重试逻辑 |
| `造影剂` / `经验性抗生素` | 仍路由到 `renal:general` / `infectious:general` 兜底 | 核对 gold 原文；`renal/` 无 general.yaml → 可能仍是"知识静默跳过"残留。`infectious/general.yaml` 存在，非静默跳过 |

---

## P2 — 系统性质量短板：证据等级标注（doctor 最大失分点）

> **已建框架**：[docs/quality-method.md](quality-method.md) 把此类问题制度化。`bin/audit_grounding.py` 作为第二道门禁，基线已通过 G1/G3，G2 在 Part-C（降模板+定映射）完成后通过。


13 道失败题中 ≥9 道栽在证据等级，是 doctor grounding=9.0（四维最低）的主因。两种失效形态：

1. **整段缺标**：部分回答 `【循证管理】` 各条无任何证据等级（PE_ANTICOAG / ONCO_CANCER_PAIN / INFEC_ATB）
2. **偷懒同质化**：全部标"中级别证据"，与教材实际等级不符（HEMA_ANEMIA / RHEU_OSTEO / CARD_VALVE：I 类适应证被标为中级别）
3. **汇总表缺失或条目数与正文不一致**（ONCO_LIFESTYLE：汇总 3 条 vs 正文 4 条）

这是 prompt/schema 问题，非知识问题。候选动作：

- 强化 `prompts/output_schema_doctor.md`：加正/反 few-shot，演示"同一回答内不同条目应有不同证据等级"
- 扩展 `bin/audit_routing.py` 的 `[TAG]` 检查：检测"全同证据等级"作为静态 WARN（零成本前移拦截）
- 可选：`postprocess.sh` 加证据等级标注存在性校验

---

## P3 — 仓库整理（低风险）

5 个一次性脚手架脚本，无任何运行时/文档引用，~50KB：

| 脚本 | 用途（历史） |
|------|------|
| `bin/apply_gap_entries.py` (27KB) | 批量补知识缺口条目 |
| `bin/fill_gaps.py` (14KB) | 知识缺口填充 |
| `bin/remap_source_page.py` | source_page 批量重映射 |
| `bin/audit_eval_gold.py` | gold 集旧版审计（已被 audit_routing 取代？） |
| `bin/build_mode_gold.py` | 双模式 gold 生成 |

> `bin/build_chapter_map.py` 被 `ingest.py` 引用，**保留**。

建议归档到 `scripts/archive/`（保留可复现性）或直接删除（git 历史已留存）。

---

## P4 — agent-os 前向（"正在建立"）

补齐 `docs/agent-os.md` 已记录的两个限制，便于 agent 消费方集成：

- **`--json` 输出模式**：结构化 envelope（mode / domains / oob_type / answer / sources），替代当前人类可读文本
- **OOB 独立退出码**：当前 OOB 与正常回答同为 exit 0，靠 stdout `═══` 区分；改为独立 exit code（如 2）更利于 pipeline 判别

---

## 建议执行顺序

`P0 + P1`（一次重跑同时刷新真实数字 + 验证两个 bug）→ 据结果决定 `P2` 投入 → `P3` 随手清理 → `P4` 作为下一个 feature 里程碑。
