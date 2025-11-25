# Claude Session Dashboard

Aggregate Claude Code usage data from multiple devices and visualize with Datawrapper.

## Architecture

```
┌─────────────────────┐     ┌─────────────────────┐
│  Device 1 (Mac)     │     │  Device 2 (Windows) │
│  ~/.claude/projects │     │  ~/.claude/projects │
└─────────┬───────────┘     └─────────┬───────────┘
          │                           │
          ▼                           ▼
   extract_local.py             extract_local.py
          │                           │
          ▼                           ▼
   data/mac-work/              data/windows/
   aggregated_data.csv         aggregated_data.csv
          │                           │
          └───────────┬───────────────┘
                      │ git push
                      ▼
              ┌───────────────┐
              │ GitHub Actions │
              │ (aggregate)    │
              └───────┬───────┘
                      │
                      ▼
              output/daily_summary.csv
                      │
                      ▼
              ┌───────────────┐
              │  Datawrapper  │
              │  Dashboard    │
              └───────────────┘
```

## Structure

```
├── data/
│   ├── mac-work/
│   │   └── aggregated_data.csv    # Output from Device 1
│   └── windows/
│       └── aggregated_data.csv    # Output from Device 2
├── output/
│   ├── all_usage.csv              # Combined from all devices
│   ├── daily_summary.csv          # Daily totals
│   └── summary.csv                # Overall statistics
├── scripts/
│   ├── extract_local.py           # Run on each device
│   └── aggregate_all_devices.py   # Runs on GitHub Actions
```

## Setup

### 1. Clone the repo on each device

```bash
git clone git@github.com:koreahong/claude-session-dashboard.git
cd claude-session-dashboard
```

### 2. Extract and push data from each device

Run this manually when you want to update:

```bash
# Extract usage data (reads ~/.claude/projects/)
python scripts/extract_local.py --device <your-device-name>

# Push to repo
git add data/<your-device-name>/
git commit -m "Update usage data from <device-name>"
git push
```

Example device names: `mac-work`, `mac-home`, `windows-pc`, `linux-server`

### 3. GitHub Actions

When you push, GitHub Actions automatically:
1. Aggregates all device CSVs
2. Generates combined output files
3. (Optional) Pushes to Datawrapper

## CSV Columns

### aggregated_data.csv (per device)

| Column | Description |
|--------|-------------|
| device | Device name |
| block_start | 5-hour block start time (ISO format) |
| input_tokens | Input tokens in this block |
| output_tokens | Output tokens in this block |
| cache_creation_tokens | Cache creation tokens |
| cache_read_tokens | Cache read tokens |
| total_tokens | Sum of all tokens |
| usage_percentage | % of estimated limit used |
| estimated_limit | Estimated token limit |
| models | Models used (comma-separated) |

### daily_summary.csv (aggregated)

| Column | Description |
|--------|-------------|
| date | YYYY-MM-DD |
| total_tokens | Total tokens across all devices |
| block_count | Number of 5-hour blocks |
| device_count | Number of devices active |
| devices | Device names (comma-separated) |

## Datawrapper Integration

1. Create a chart at [Datawrapper](https://www.datawrapper.de/)
2. Use GitHub raw URL:
   ```
   https://raw.githubusercontent.com/koreahong/claude-session-dashboard/main/output/daily_summary.csv
   ```
3. Or set up API push (see workflow file)

## Notes

- **No secrets are pushed** - Only aggregated CSV data is stored in the repo
- **Usage percentage** is estimated based on historical max usage
- **5-hour blocks** match Claude's rate limit windows
