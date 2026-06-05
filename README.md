[![中文](https://img.shields.io/badge/语言-中文-red)](README.md) [![English](https://img.shields.io/badge/Language-English-blue)](README_EN.md)

# Review Writing Harness（综述写作框架）

基于本地 Markdown 论文语料库的 synthesis-first 多智能体文献综述写作工作流。作为 Claude Code 中 `nature-writing` 技能的增强扩展。

## 解决的问题

传统文献综述工作流产出的往往是**"逐篇罗列"式文本**："Smith 等人提出 X，准确率 92%。Jones 等人提出 Y，准确率 88%。Lee 等人提出 Z……"——每个段落是一篇论文的孤立摘要，缺少跨论文横向比较、缺少性能范围综合、缺少不可比性警告、缺少结构化比较表格。

更致命的是，直接让大语言模型（LLM）"写一篇综述"会产生严重的**幻觉问题**：模型会凭空编造不存在的论文标题、虚构作者姓名、捏造实验数据和性能指标——这些虚构内容混入学术写作后极难被察觉，可能导致严重的学术不端后果。`review-writing-harness` 通过两层硬约束从根本上杜绝幻觉：（1）**框架约束**——所有论述必须严格对应 `local_framework.md` 中预定义的 H1/H2 标题结构，模型不得自行扩展或偏离；（2）**本地论文阅读**——所有引用证据必须来自用户提供的本地 Markdown 论文语料库，doctor 子代理逐篇阅读并提取含精确页码/段落锚点的结构化证据，禁止引用任何训练数据中的"记忆知识"。框架是骨架，本地论文是血肉——两者共同构成一个封闭的证据系统，使幻觉在源头就被阻断。

```
                          ┌──────────────────────────┐
                          │   local_framework.md     │
                          │   (用户预定义 H1/H2 结构)  │
                          └────────────┬─────────────┘
                                       │ 硬约束：所有论述必须在此框架内
                                       ▼
┌─────────────────────────────────────────────────────────────┐
│                    review-writing-harness                    │
│                                                             │
│  Prepare ──▶ Doctors ──▶ Voters ──▶ Expert ──▶ Synthesizers│
│     │            │           │          │            │       │
│     │      逐篇阅读     2-of-3    去重排序    每H1生成比较表  │
│     │      提取证据     多数决    构建映射    +范围+模式+警告 │
│     │            │           │          │            │       │
│     ▼            ▼           ▼          ▼            ▼       │
│  ┌──────────────────────────────────────────────────────┐    │
│  │              封闭证据系统（零幻觉）                    │    │
│  │  • 所有引用均来自本地 MD 论文 + 精确段落锚点           │    │
│  │  • 禁止引用训练数据中的"记忆知识"                     │    │
│  │  • 每条证据含 12 维结构化 comparative_dimensions      │    │
│  └──────────────────────────────────────────────────────┘    │
│                                                             │
│  Main Writer ──▶ Validate                                   │
│       │               │                                     │
│   synthesis-first  字数/表格覆盖/综合密度/不可比性检查        │
│   4层写作协议                                                │
└─────────────────────────────────────────────────────────────┘
                                       │
                                       ▼
                          ┌──────────────────────────┐
                          │   literature_review.md   │
                          │   (含比较表 + 性能范围    │
                          │    + 不可比警告 + 参考文献)│
                          └──────────────────────────┘
```

## 我们的方案

`review-writing-harness` 为本地 Markdown 综述流程引入了三项核心创新：

### 1. Synthesis-First 写作协议

每个 H2 节按强制性的 4 层顺序撰写：
- **第一层（30-40%）**：综合优先——以观察到的*结果范围*开头，而非逐个论文的孤立数值
- **第二层（40-50%）**：方法论分组——按共享方法将论文聚类，在组内进行比较与对比
- **第三层（10-20%）**：个别深挖——仅限每个 H2 最多 2 篇里程碑式论文，需明确说明深挖理由
- **第四层（10%）**：关键缺口/不可比性分析——哪些比较维度缺失？哪些比较因方法不兼容而失效？

### 2. Table-First 综合阶段

在证据收集与正文撰写之间新增合成器子代理阶段。每个 H1 节分配一个专用合成器，产出：
- **比较表**：跨越全部论文，含 12 个结构化维度（设备类型、模态、样本量、人群、分类数、标签标准、验证协议、kappa、准确率、模型类别、参数量）
- **性能范围摘要**（上界、下界、主流聚类、离群值及其因果解释）
- **不可比性警告**（不应直接比较的论文对，附原因说明）
- **跨论文综合模式**（3-5 个横跨 ≥2 篇论文的模式）

### 3. 结构化比较维度

证据 schema 扩展了 `comparative_dimensions` 字段，要求 doctor 代理必须填充：`device_type`、`modalities`、`sample_size`、`population`、`n_classes`、`label_standard`、`validation`、`primary_metric`、`model_class`、`parameter_count`。这使得自动生成比较表和系统化跨研究分析成为可能。

## 工作流架构

```
Prepare → Doctors(×N) → Voters(×3) → Expert Merge → Synthesizers(×M) → Main Writer → Validate
```

| 阶段 | 代理数 | 功能 |
|------|--------|------|
| Prepare | 1 脚本 | 解析框架、分批论文、生成全部提示词 |
| Doctors | ≤6 并发 | 阅读论文，提取含 comparative_dimensions 的证据 |
| Voters | 3（2-of-3 多数决） | 投票决定论文-H2 分配 |
| Expert Merge | 1 | 去重、排序、构建证据映射 |
| **Synthesizers** | **每 H1 节一个** | **生成比较表、范围、模式、不可比警告** |
| Main Writer | 1 | 按 synthesis-first 协议撰写综述 |
| Validate | 1 脚本 | 检查字数、表格覆盖、综合密度 |

## 禁止模式（自动拒绝）

- 连续多个段落以作者名开头
- 孤立出现"X 达到准确率 Y%"而无与其他论文比较的句子
- 连续两句以上以作者名开头
- 仅列出论文标题和一个指标的比较表（换汤不换药的逐篇罗列）

## 文件结构

```
nature-writing/
├── SKILL.md                          # 技能路由
├── manifest.yaml                     # 轴检测清单
├── scripts/
│   ├── prepare_local_md_review.py    # 准备脚本 + 全部提示词生成
│   ├── validate_word_count.py        # 字数验证
│   └── validate_citation_order.py    # 引用一致性验证
├── references/
│   ├── local-md-review.md            # 完整工作流规范
│   └── ...                           # 各章节撰写参考
├── static/                           # 版本化内容片段
│   ├── core/                         # 核心立场、工作流、输出格式
│   └── fragments/                    # 按轴切片的片段（paper_type/section/language/journal）
└── agents/                           # 代理配置
```

## 快速开始

```bash
# 1. 将你的框架文件命名为 local_framework.md 放入论文目录
# 2. 运行准备脚本
python scripts/prepare_local_md_review.py \
  --framework /path/to/local_framework.md \
  --corpus /path/to/markdown/papers

# 3. 按生成的提示词依次执行工作流：
#    Doctor → Voter → Expert → Synthesizer → Main Writer → Validate
```

### 框架格式

```markdown
# 1 引言
## 1.1 研究背景与动机
## 1.2 综述范围与组织结构

# 2 核心方法
## 2.1 方法类别A
## 2.2 方法类别B

# 3 挑战与未来方向

# 4 总结

总体字数：6000
```

## 验证关卡

| 关卡 | 检查项 | 阈值 |
|------|--------|------|
| 字数 | 中文字符数在目标范围内 | ±10% |
| 表格覆盖 | 每个 ≥4 条证据的 H1 至少 1 张表 | 跨度 ≥3 篇论文 × ≥3 个维度 |
| 综合密度 | 跨论文比较句 / 总句数 | ≥0.25 |
| 不可比性 | 不同标签标准或验证协议的论文不得直接比较性能数值 | 零违规 |
| 禁止模式 | 无作者名流水账 | 零违规 |

## 与原版 nature-writing 的主要差异

| 原版 | 增强版 |
|------|--------|
| 逐篇引用式写作 | Synthesis-first 四层协议 |
| 无比较表要求 | 强制 12 维度比较表 |
| 无结构化比较维度 | 每条证据含 `comparative_dimensions` 字段 |
| 无综合阶段 | Table-first 合成器阶段（每 H1） |
| 基础验证（仅字数） | 表格覆盖、综合密度、不可比性检查 |
| "每个主张挂引用" | "先分组、再比较、后引用"，支持多引用语法 `[@a; @b]` |

## 设计理念

本工作流的核心设计原则是：**证据的原子单位应当从 `(论文, 章节, 主张)` 转换为 `(章节, 比较维度, 范围)`，在代理写出第一个字之前完成这一"转置"操作。** 这是区分"真正综合"与"高级流水账"的根本差异。

## 许可证

MIT

## 引用

如果在你的研究中使用本工作流，请引用：

```bibtex
@software{review_writing_harness,
  author = {Yu Bai and Anthropic},
  title = {Review Writing Harness: Synthesis-First Multi-Agent Literature Review},
  year = {2026},
  url = {https://github.com/YuBai630/review-writing-harness}
}
```
