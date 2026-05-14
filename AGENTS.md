# png2ppt Skill Maintenance

This repository is the source of truth for the `png2ppt` Codex skill.

## Rules

- Keep the skill PNG-only unless the user explicitly changes the product scope.
- Keep final user deliverables outside this repository, next to their source PNG files.
- Keep intermediate run artifacts under each job's `png2ppt/<job>/work/` directory, not in this repository.
- Do not add project-specific slide rebuilders to the published skill. Put one-off templates and coordinates in the user's project work directory.
- Prefer data-driven profiling, render/audit loops, and regression comparison over subjective visual judgment.
- When evolving the skill, update this GitHub repository first, then install or sync the skill from the repository.

## Validation

Run these checks before committing skill changes:

```bash
python3 -m py_compile scripts/*.py
python3 /Users/hawk/.codex/skills/.system/skill-creator/scripts/quick_validate.py .
```

For reconstruction behavior changes, also rerun at least one saved sample and compare:

```bash
python3 scripts/regression_compare.py \
  --baseline <job>/work/audits/final/metrics.json \
  --candidate <job>/work/regression/audit/metrics.json \
  --quality <job>/work/regression/quality.json \
  --fail-on-regression
```
