# PDF to Markdown Converter

基于 [marker](https://github.com/VikParuchuri/marker) 的批量 PDF 转 Markdown 工具，为 `review-writing-harness` 综述工作流的前置步骤。

## 功能

- 批量转换整个目录的 PDF 论文
- 保留原文标题层级、段落结构、表格和关键数值
- 分批处理，避免 GPU/CPU 内存溢出
- 自动跳过已转换文件，支持断点续转
- 支持 CUDA GPU 加速和纯 CPU 两种模式

## 安装

```bash
# 1. 安装依赖
pip install -r requirements.txt

# 2. (可选) 设置模型缓存目录，避免占用系统盘
export MARKER_MODEL_DIR=/your/data/drive/marker_models   # Linux / macOS
set MARKER_MODEL_DIR=D:\data\marker_models               # Windows
```

## 模型下载

首次运行时，marker 会自动下载所需的模型文件。

| 模型 | 大小 | 用途 |
|------|------|------|
| surya_detection | ~200 MB | 文档布局检测 |
| surya_layout | ~300 MB | 版面分析 |
| surya_recognition | ~250 MB | 文本识别 (OCR) |
| surya_table_rec | ~200 MB | 表格识别 |
| texify | ~500 MB | 公式识别 |

**总计约 3-5 GB**（启用量化后约 2-3 GB）。下载后缓存在 `MARKER_MODEL_DIR` 目录中。

> **网络问题**：模型托管在 Hugging Face Hub。如果下载速度慢，可以使用 HF 镜像：
> ```bash
> export HF_ENDPOINT=https://hf-mirror.com
> ```

如果希望手动预下载模型（避免首次运行的等待）：

```bash
python -c "
import os
os.environ['MODEL_CACHE_DIR'] = '/your/path/marker_models'
from marker.models import create_model_dict
models = create_model_dict()  # 触发下载
print(f'Downloaded {len(models)} models')
"
```

## 使用

```bash
# 基本用法
python batch_convert.py --input ./papers --output ./md_papers

# 指定每批处理数量（内存充足时可增大）
python batch_convert.py --input ./papers --output ./md_papers --batch-size 10

# 使用 CPU（没有 GPU 时）
python batch_convert.py --input ./papers --output ./md_papers --device cpu

# 指定模型缓存目录
python batch_convert.py --input ./papers --output ./md_papers --model-dir /data/models
```

### 参数说明

| 参数 | 简写 | 必需 | 默认值 | 说明 |
|------|------|------|--------|------|
| `--input` | `-i` | 是 | - | PDF 论文目录 |
| `--output` | `-o` | 是 | - | Markdown 输出目录 |
| `--batch-size` | - | 否 | 5 | 每批处理文件数 |
| `--batch-delay` | - | 否 | 10 | 批次间隔秒数 |
| `--device` | - | 否 | cuda | 计算设备 (cuda/cpu) |
| `--model-dir` | - | 否 | ~/.cache/marker | 模型缓存路径 |
| `--no-quantize` | - | 否 | false | 禁用模型量化 |

## 输出结构

```
md_papers/
├── Paper_Title_1/
│   └── Paper_Title_1.md     # 转换后的 Markdown 正文
├── Paper_Title_2/
│   └── Paper_Title_2.md
└── ...
```

每个 PDF 对应一个子文件夹，内含 `.md` 文件。

## 接入综述工作流

转换完成后，将 Markdown 输出目录作为 `--corpus` 参数传入 review-writing-harness：

```bash
# 步骤 1：PDF → Markdown
python pdf_to_md/batch_convert.py --input ./papers --output ./md_papers

# 步骤 2：启动综述工作流
python nature-writing/scripts/prepare_local_md_review.py \
  --framework ./local_framework.md \
  --corpus ./md_papers
```

## 系统要求

- Python 3.10+
- GPU 模式：NVIDIA GPU + CUDA 12.x（推荐 8GB+ 显存）
- CPU 模式：16GB+ RAM（速度较慢，但可运行）
- 磁盘空间：模型 ~5GB，输出文件视论文数量而定

## 常见问题

**Q: 转换速度慢？**
- 增大 `--batch-size`（充分利用 GPU）
- 确保 `--device cuda` 生效：`python -c "import torch; print(torch.cuda.is_available())"`
- 使用量化（默认开启）：`FOUNDATION_MODEL_QUANTIZE=true`

**Q: 内存不足？**
- 减小 `--batch-size`（如 2-3）
- 增大 `--batch-delay`（如 30 秒，让系统充分释放内存）
- 使用 `--no-quantize` 的反面：确保量化已启用（默认）
- 使用 CPU 模式（更慢但更稳定）：`--device cpu`

**Q: 公式或表格识别不准确？**
- marker 的公式和表格识别在复杂排版上仍有局限
- 建议人工抽查关键论文的转换质量
- 公式密集的论文可在综述中标注"原文公式见 PDF"

**Q: 转换后的 Markdown 文件很大？**
- 这是正常的，marker 保留了完整文档结构
- 综述工作流的 doctor 代理会自动处理大文件
- 如果某文件超过 200KB，doctor 会分段阅读

## 许可

本脚本为 MIT 许可。底层 marker 库使用其自身许可，详见 https://github.com/VikParuchuri/marker
