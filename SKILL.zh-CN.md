# png2ppt 中文说明

这是 `SKILL.md` 的中文说明版本，仅供阅读和维护使用。Skills CLI 只使用根目录的 `SKILL.md` 作为技能入口，本文件不会改变 skill 的触发、安装或执行行为。

## 决策规则

本 skill 只有一种最终交付模式：**可编辑原生 PPT 重建**。

不要通过把源 PNG 作为整页图片插入 PPTX 来完成交付。整页截图层只能作为本地分析参考，最终交付前必须删除。

重建时将文字、线条、面板、卡片、表格、流程节点和其他布局几何做成可编辑 PPT 对象。图标和复杂装饰可以简化或语义替换，但不能把源 PNG 当作最终内容。

## 保真取舍

原生 PPT 重建能提升可编辑性，但字体、阴影、抗锯齿和图标细节可能与源图不同。

实践排序：

1. **必需最终模式**：用原生 PPT 形状和文本重建结构与文字。
2. **允许的快捷方式**：图标和复杂装饰可简化或语义替换。
3. **禁止的最终模式**：源 PNG 整页放入 PPT。

## 工作流程

1. 先识别源图中的文字、结构几何、图标、复杂装饰和位图区域。
2. 初始化输出目录：最终 PPTX 放在源 PNG 旁边；轮次、审计、规格、日志、预览和临时文件放在 `png2ppt/<job-name>/work/`。
3. 重建前运行 `scripts/style_profile.py`，提取背景、色板、边缘密度、线条密度、内容块、文本块和首选策略。
4. 如果存在风格记忆，使用 `style_memory.py nearest` 查找相似样例；如果存在本地资产索引，使用 `asset_index.py search` 查找可复用线形、图标和装饰资产。但不要强行套模板。
5. 锁定验证范围。若源图来自 PPTX 内嵌图片，应提取精确位图，而不是比较整页预览。
6. 重建时保留标题、文字、面板、线条、表格和流程节点为可编辑对象；图标和复杂图形可用 PNG。
7. 先重建结构，再处理图标：画布、面板、边框、分隔线、虚线、分栏，然后再放文字和语义图标。
8. 图标不需要编辑时，使用 PNG 图标库语义替换，把迭代预算花在结构和排版上。
9. 移除任何源截图层，清理 PPTX 包中的陈旧媒体和关系。
10. 运行视觉审计并迭代，直到结构指标通过，或明确说明剩余失败原因。
11. 将决策、指标和下一步改进记录到任务报告和风格记忆中。

## 本地资产索引

大型 PPT 资产库可以用于语义图标替换、线形样式、咨询风格组件和装饰图案。先建立私有本地元数据索引，再按任务需要萃取具体 parts。

```bash
python3 /path/to/png2ppt/scripts/asset_index.py build assets/raw --out assets/index
python3 /path/to/png2ppt/scripts/asset_index.py search assets/index --kind slide --tag consulting_line --limit 20
python3 /path/to/png2ppt/scripts/asset_index.py search assets/index --kind media --tag small_icon --limit 20
python3 /path/to/png2ppt/scripts/asset_index.py search assets/index --kind component --tag editable_line --limit 20
```

隐私规则：

- 用户 raw 资产 deck 是私有文件，不能提交、上传或移动到 GitHub。
- 从私有资产派生出的索引默认也是本地工作产物，除非用户明确批准，否则不要发布。
- 萃取 parts 默认留在用户项目的 `assets/` 目录。
- 只有在用户明确批准并确认可发布时，才可以把萃取 parts 提升到本 skill 的 `assets/` 目录。

## 自适应循环

不要把项目专用模板硬编码进 skill。特定项目的重建脚本、规格和坐标映射应放在项目工作目录，不放进公开 skill。

可编辑或混合重建使用以下循环：

1. **Profile**：运行 `style_profile.py`，保存到 `work/specs/style_profile.json`。
2. **Retrieve**：有风格记忆时运行 `style_memory.py nearest`。
3. **Plan**：根据风格画像和用户要求选择 `simple_native_reconstruction`、`hybrid_reconstruction`、`native_or_hybrid_reconstruction`、`consulting_blueprint_hybrid_reconstruction` 或 `texture_backed_hybrid_reconstruction`。
4. **Spec**：从图片检测到的布局创建区域/组件规格，尽量数据驱动。
5. **Render**：生成候选 PPTX 和归一化 PNG 渲染图。
6. **Audit**：运行视觉审计和 PPTX 包体检查。
7. **Improve**：优先调整几何、文字适配、线宽和结构元素，再调整图标。
8. **Remember**：记录决策、指标和下一步改进。

## 输出目录

```text
<source-dir>/
├── <job-name>.png
├── <job-name>.pptx
└── png2ppt/<job-name>/work/
    ├── rounds/
    ├── audits/
    ├── renders/
    ├── specs/
    ├── reports/
    ├── logs/
    └── tmp/
```

只有最终 PPTX 放在源 PNG 旁边。预览图、summary、报告、轮次 PPTX、渲染图、审计图片、指标 JSON、组件规格、mask、临时脚本和日志都放在 `png2ppt/<job-name>/work/`。

## 常用脚本

初始化任务目录：

```bash
python3 /path/to/png2ppt/scripts/init_job.py image1.png --root ./png2ppt
```

视觉审计：

```bash
python3 /path/to/png2ppt/scripts/visual_fidelity_audit.py \
  --reference reference.png \
  --candidate png2ppt/image1/work/renders/round_01.png \
  --out-dir png2ppt/image1/work/audits/round_01 \
  --fail-on-threshold
```

回归对比：

```bash
python3 /path/to/png2ppt/scripts/regression_compare.py \
  --baseline png2ppt/image1/work/audits/final/metrics.json \
  --candidate png2ppt/image1/work/regression/audit/metrics.json \
  --quality png2ppt/image1/work/regression/quality.json \
  --out png2ppt/image1/work/regression/regression_report.json \
  --fail-on-regression
```

风格画像：

```bash
python3 /path/to/png2ppt/scripts/style_profile.py \
  image1.png \
  --out png2ppt/image1/work/specs/style_profile.json \
  --debug-dir png2ppt/image1/work/tmp/style_profile
```

## 注意事项

- 用户说“不需要编辑图标/快速实现”时，简化图标或使用语义替换，不要插入源幻灯片 PNG。
- 用户说“高保真”时，优先提升原生结构、排版和线型几何，不要用整页 PNG 作为最终交付。
- 用户说“可编辑”时，重建关键文字和结构，复杂图形/图标可用 PNG。
- 用户不满意还原度时，先运行视觉审计，优先修结构漂移和排版，再换图标策略。
- 审计前要把 PPT 渲染图归一化到源 PNG 尺寸。
- 如需 PPT 美化，先确保结构保真，再使用设计类 skill；美化不能破坏原参考网格，除非用户允许重新设计。
