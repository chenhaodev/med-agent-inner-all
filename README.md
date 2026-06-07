# 西氏内科学精要 问答 Agent

基于《西氏内科学精要》（Cecil Essentials of Medicine）的内科常见病问答系统，覆盖 17 专科，支持患者家属与临床医生两种模式。

无需 RAG / 向量库，结构化知识注入 + 确定性路由，知识来源可回溯至原书页码。

---

## 我是谁？

| 你是… | 用途 | 文档 |
|-------|------|------|
| **患者 / 家属** | 了解病情、日常护理、何时就医 | [docs/patient.md](docs/patient.md) |
| **临床医生** | 循证管理摘要、证据等级参考 | [docs/doctor.md](docs/doctor.md) |
| **Agent / 开发者** | CLI 调用接口、pipeline 集成 | [docs/agent-os.md](docs/agent-os.md) |

---

## 快速开始

```bash
cp .env.example .env                            # 填入 DEEPSEEK_API_KEY
./bin/ask.sh "我爸有高血压，平时饮食要注意什么？"
./bin/ask.sh --mode doctor "高血压血压控制目标？"
./bin/ask.sh --accurate "肺栓塞抗凝怎么做？"     # 精确模式：核验+自纠
./bin/ask.sh --stream "高血压饮食建议？"        # 流式输出（--stream 默认关）
```

重复提问走缓存（`.cache/deepseek/`），响应从 ~1.9s 降至 0.02s。
清理缓存：`rm -rf .cache/`

---

## 两种执行模式（速度 ↔ 质量）

受众模式（`--mode patient|doctor`）之外，另有一条正交的「执行模式」轴，在速度与质量间取舍：

| 模式 | 开关 | 行为 | 适用 |
|------|------|------|------|
| **Fast** | 默认 / `--fast` | 单次生成，最低延迟 | 日常交互、快速查询 |
| **Accurate** | `--accurate`（别名 `--deep`） | 原子声明 grep 核验 + 有不符则回炉自纠，~2-3 倍调用 | 临床/高风险问题、降幻觉 |

批量 eval 同理两档：`./bin/eval.sh`（Fast，裸生成，度量基线）与 `./bin/eval_deep.sh`（Accurate，verify+reroll，度量质量上限）。两条批量路径均已并发化（`--concurrency`，默认 8）。

---

## 性能指标（v3.2，2026-06-07 重跑）

| 模式 | 题数 | 平均分 / 40 | 通过率（≥34） | 溯源性 | OOB 拦截 |
|------|------|------------|--------------|--------|---------|
| patient | 112 | 38.3 | 92.0% | 10.0 | 100% |
| doctor  | 110 | 38.1 | 90.9% | 9.8  | 100% |

gold.yaml 147 题，覆盖 Tier1/2/3 全部病种（97 个 YAML）。  
eval 耗时：~13 min（并发 8，原串行 ~30–50 min）。

> v3.2 质量修复：判官 JSON 解析健壮化（消除 0/40 解析失败，两模式 error 1→0）；
> doctor 证据等级核对过程去泄漏 + 处方剂量提示；癌痛路由改投姑息（接地 0→10）。

---

## 项目结构

```
bin/        ask.sh 主入口 · eval · ingest · audit
knowledge/  97 个病种 YAML（17 专科 · Tier1/2/3）+ 指南叠加层
prompts/    system · output schema · 专科指引
eval/       gold.yaml 147 题 · judge_prompt
docs/       分受众文档（见上表）
```

---

## 参考

- [CHANGELOG.md](CHANGELOG.md) — 版本记录
- [docs/roadmap.md](docs/roadmap.md) — 下步计划与已知问题
- [docs/quality-method.md](docs/quality-method.md) — 质量方法论（分析+研究驱动的主动缺陷发现）
- [docs/knowledge.md](docs/knowledge.md) — 知识库维护、路由表、eval 方法、目录结构详解
- 依赖：`bash ≥3.2` / `python3 ≥3.8` / `curl` / `pyyaml` / `pymupdf` / DeepSeek API key
- Eval 并发：`EVAL_CONCURRENCY=8`（默认）；`./bin/eval.sh --concurrency 16 --mode both` 可调
- Eval 缓存：生成默认 `--no-cache`（保证新鲜度）；`--cache` 开启；`NO_CACHE=1` 全局绕过
