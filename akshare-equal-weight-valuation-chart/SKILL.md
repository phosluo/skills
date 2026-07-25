---
name: akshare-equal-weight-valuation-chart
description: Use when the user wants to generate or refresh the latest monthly long-cycle chart for 全部A股 equal-weight PE/PB from AKShare, especially when they want the output image saved in the current workspace.
---

# AKShare Equal-Weight Valuation Chart

Use this skill to generate the latest monthly long-cycle valuation chart for:

- `全部A股-等权重市盈率` from `ak.stock_a_ttm_lyr()`
- `全部A股-等权重市净率` from `ak.stock_a_all_pb()`

The bundled script writes a two-panel line chart in the current working directory. It uses monthly sampling, no point markers, and yearly ticks on the x-axis.

## When To Use

Use this skill when the user asks to:

- refresh the latest 全部 A 股等权 PE/PB chart
- regenerate the chart in a new workspace
- update the image with the newest AKShare data
- change the start date or output filename for the same chart workflow

Do not use this skill for:

- custom factor research
- rebuilding the valuation methodology from raw stock-level data
- comparing unrelated third-party Excel sources unless the user explicitly asks

## Default Workflow

1. Confirm the current working directory is where the user wants the output image.
2. Resolve `scripts/generate_chart.py` relative to this `SKILL.md`, then run it with the user's target directory as the working directory:

```bash
python3 <skill-directory>/scripts/generate_chart.py
```

3. Verify the PNG exists in the working directory.
4. Report the output path and the data sources used.

## Optional Arguments

Use these when the user wants a different range or filename:

```bash
python3 <skill-directory>/scripts/generate_chart.py \
  --start-date 2010-01-01 \
  --output custom-name.png
```

Defaults:

- `--start-date 2005-01-01`
- `--output all_a_equal_weight_pe_pb_since_2005_monthly.png`

## Notes

- The script uses:
  - `averagePETTM` as equal-weight PE
  - `equalWeightAveragePB` as equal-weight PB
- If Python dependencies are missing, install:

```bash
python3 -m pip install --user akshare pandas matplotlib
```

- The script prints the actual returned date range so the user can see whether AKShare starts later than requested.

## What To Report Back

Keep it short:

1. the output file path
2. the actual data range returned
3. the source interfaces used
