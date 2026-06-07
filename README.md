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
```

---

## 性能指标（v3）

| 模式 | 题数 | 平均分 / 40 | 通过率（≥34） | OOB 拦截 |
|------|------|------------|--------------|---------|
| patient | 112 | 39.0 | 100% | 100% |
| doctor | 110 | 38.3 | 96.3% | 100% |

gold.yaml 147 题，覆盖 Tier1/2/3 全部病种（97 个 YAML）。

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
- 依赖：`bash ≥4.0` / `python3 ≥3.8` / `curl` / `pyyaml` / `pymupdf` / DeepSeek API key
