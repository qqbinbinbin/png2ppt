# png2ppt

`png2ppt` 是一个 Codex skill，用于把 PNG 图片转换成 PowerPoint，或把 PNG 截图重建为可编辑的 PPT 内容。

它支持两种常用模式：

- **保真优先的 PNG 放置**：速度最快，同屏视觉还原度最高。
- **可编辑/混合重建**：将文字、线条、面板、卡片、表格、流程结构重建为原生 PPT 对象，图标或复杂图形可使用 PNG 资产替代。

这个 skill 的核心不是一次性猜测，而是可验证迭代：先分析源图，再生成候选 PPTX，渲染成图片，与源 PNG 做视觉审计，最后用基线指标判断是否退化。

## 安装

从 GitHub 直接安装。即使 `skills.sh` 搜索暂时还没有收录仓库，这条命令也可以使用：

```bash
npx skills add qqbinbinbin/png2ppt --skill png2ppt -y
```

全局安装：

```bash
npx skills add qqbinbinbin/png2ppt --skill png2ppt -g -y
```

只查看仓库中可安装的 skill，不安装：

```bash
npx skills add qqbinbinbin/png2ppt --list
```

## 适用场景

适合在以下场景使用：

- 将 PNG 截图或幻灯片图片转换为 `.pptx`。
- 将关键页面内容重建为可编辑的 PowerPoint 对象。
- 优先保留布局、线条、卡片、面板、表格和流程图结构。
- 重建蓝色咨询风格 PPT 页面，包括章节徽章、卡片、流程步骤、箭头和底部结论条。
- 图标不需要编辑时，使用 PNG 图标库做语义替换。
- 用视觉审计和回归对比证明一次迭代没有退化。

如果目标是“看起来完全一样”，优先把 PNG 放入 PPTX。如果目标是“可编辑”，使用混合重建，并用渲染/审计指标验证效果。

## 输出目录

最终交付物放在源图片旁边：

```text
source-dir/
├── image1.png
├── image1.pptx
└── png2ppt/image1/work/
    ├── audits/
    ├── logs/
    ├── renders/
    ├── reports/
    ├── rounds/
    ├── specs/
    └── tmp/
```

源图目录下只放最终 `.pptx`。预览图、报告、中间轮次、审计图片、指标 JSON、组件规格和临时文件都放在 `png2ppt/<job>/work/`。

## 核心脚本

创建标准任务目录：

```bash
python3 scripts/init_job.py image1.png --root ./png2ppt
```

创建一个简单的图片型 PPTX：

```bash
python3 scripts/images_to_ppt.py --output image1.pptx --fit contain image1.png
```

重建前分析图片风格和结构：

```bash
python3 scripts/style_profile.py \
  image1.png \
  --out png2ppt/image1/work/specs/style_profile.json
```

对候选渲染图做视觉审计：

```bash
python3 scripts/visual_fidelity_audit.py \
  --reference image1.png \
  --candidate png2ppt/image1/work/renders/round_01.png \
  --out-dir png2ppt/image1/work/audits/round_01
```

对比重跑结果和已保存基线：

```bash
python3 scripts/regression_compare.py \
  --baseline png2ppt/image1/work/audits/final/metrics.json \
  --candidate png2ppt/image1/work/regression/audit/metrics.json \
  --quality png2ppt/image1/work/regression/quality.json \
  --fail-on-regression
```

## 质量标准

这个 skill 把视觉质量作为可度量对象：

- 判断前先把候选 PPTX 渲染成 PNG。
- 将渲染图尺寸归一化到源 PNG。
- 检查像素差异、边缘/线型 IoU、缺失结构、额外结构和 PPTX 包体卫生。
- 修改脚本或重建策略后，运行回归对比。

这不等于保证原生 PPT 重建可以完美复刻源图。PowerPoint 的文字渲染、抗锯齿、阴影、渐变和图标细节都可能与源图不同。这个流程的价值是让差异可见、可测、可迭代。

## 仓库维护

提交前运行：

```bash
python3 -m py_compile scripts/*.py
npx skills add . --list
```

不要提交用户交付物、样例工作目录、渲染预览或项目专用重建脚本。可复用流程放在本仓库，一次性的页面坐标和模板脚本放在用户项目工作区。
