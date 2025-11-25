# Claude Session Dashboard

Aggregate Claude Code usage data from multiple devices and visualize with Datawrapper.

## Structure

```
├── data/
│   ├── device-1/projects/     # JSONL files from device 1
│   ├── device-2/projects/     # JSONL files from device 2
│   └── ...
├── output/
│   ├── daily_usage.csv        # Daily aggregated usage
│   ├── block_usage.csv        # 5-hour block usage
│   ├── model_usage.csv        # Usage by model
│   └── summary.csv            # Summary statistics
├── scripts/
│   ├── aggregate_usage.py     # Aggregation script
│   └── sync_device.sh         # Device sync helper
└── .github/workflows/
    └── aggregate.yml          # GitHub Actions workflow
```

## Setup

### 1. Clone the repo on each device

```bash
git clone git@github.com:koreahong/claude-session-dashboard.git
cd claude-session-dashboard
```

### 2. Push data from each device

Option A: Use the sync script
```bash
export DEVICE_NAME="mac-work"  # or mac-home, windows-pc, etc.
export REPO_PATH="$HOME/claude-session-dashboard"
./scripts/sync_device.sh
```

Option B: Manual copy
```bash
# Copy your Claude data
cp -r ~/.claude/projects data/<your-device-name>/projects/

# Commit and push
git add data/
git commit -m "Update data from <device-name>"
git push
```

### 3. GitHub Actions

The workflow runs:
- Automatically when data is pushed
- Every hour (scheduled)
- Manually via workflow_dispatch

It aggregates all device data and outputs CSV files.

## Output CSVs

### daily_usage.csv
| Column | Description |
|--------|-------------|
| date | YYYY-MM-DD |
| input_tokens | Input tokens used |
| output_tokens | Output tokens received |
| cache_creation_tokens | Tokens for cache creation |
| cache_read_tokens | Tokens read from cache |
| total_tokens | Sum of all tokens |
| models | Comma-separated model names |
| session_count | Number of sessions |

### block_usage.csv
| Column | Description |
|--------|-------------|
| block_start | 5-hour block start time |
| total_tokens | Tokens used in block |
| usage_percentage | % of estimated limit |

### model_usage.csv
| Column | Description |
|--------|-------------|
| model | Model name |
| input_tokens | Total input tokens |
| output_tokens | Total output tokens |

## Datawrapper Integration

1. Go to [Datawrapper](https://www.datawrapper.de/)
2. Create new chart
3. Use GitHub raw URL for CSV:
   ```
   https://raw.githubusercontent.com/koreahong/claude-session-dashboard/main/output/daily_usage.csv
   ```
4. Set up auto-refresh (Datawrapper polls the URL)

## Notes

- Cost values are **estimated API costs**, not actual charges (subscription users pay fixed monthly fee)
- Each device must push its own `~/.claude/projects/` data
- 5-hour blocks match Claude's rate limit windows
