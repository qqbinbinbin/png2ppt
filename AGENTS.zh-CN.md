# png2ppt Skill 维护说明

本仓库是 `png2ppt` Codex skill 的源头。后续能力进化应先在这个 GitHub 仓库中完成、验证、提交和推送，再同步到本地使用环境。

## 规则

- 除非用户明确改变产品范围，否则保持 PNG-only，不扩展到 SVG 等其他输入。
- 最终用户交付物不要放进本仓库，应放在源 PNG 文件旁边。
- 中间过程文件放在任务目录的 `png2ppt/<job>/work/`，不要放进本仓库。
- 不要把项目专用的幻灯片重建脚本放进公开 skill。一次性的模板、坐标和页面脚本应放在用户项目工作目录。
- 优先使用数据驱动的风格画像、渲染/审计循环和回归对比，不依赖主观肉眼判断。
- skill 进化时，先更新 GitHub 仓库，再从仓库安装或同步 skill。
- 不要把用户私有资产源文件（例如 `assets/raw/*.pptx`）提交到本仓库。
- 从用户私有 PPT 资产中萃取出的本地 parts，默认只能放在用户项目的 `assets/` 目录，不应放进本 skill 仓库。
- 只有在用户明确指示，并且确认该资产可以公开发布时，才可以把萃取 parts 移动到 skill 的 `assets/` 目录。
- 对大型私有 PPTX 资产库，先建立渐进式元数据索引，再按任务需要萃取具体 parts。
- 从私有资产派生的索引也视为本地工作产物，除非用户明确批准，否则不要发布。

## 验证

提交 skill 变更前运行：

```bash
python3 -m py_compile scripts/*.py
npx skills add . --list
```

如果变更影响重建行为，还要至少重跑一个已保存样例并做回归对比：

```bash
python3 scripts/regression_compare.py \
  --baseline <job>/work/audits/final/metrics.json \
  --candidate <job>/work/regression/audit/metrics.json \
  --quality <job>/work/regression/quality.json \
  --fail-on-regression
```

## 中文文档说明

`README.zh-CN.md`、`SKILL.zh-CN.md` 和 `AGENTS.zh-CN.md` 只是中文阅读版本。功能入口仍然是 `SKILL.md`，不要把中文文档当成新的 skill 入口。
