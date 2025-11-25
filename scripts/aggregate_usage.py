#!/usr/bin/env python3
"""
Aggregate Claude Code usage data from multiple devices.
Reads JSONL files from data/ directory and outputs CSV for dashboard.
"""

import json
import os
import csv
from datetime import datetime, timedelta
from pathlib import Path
from collections import defaultdict
import glob


def parse_jsonl_file(file_path):
    """Parse a single JSONL file and extract usage data."""
    usage_records = []

    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    record = json.loads(line)

                    # Extract usage data from assistant messages
                    if record.get('type') == 'assistant' and 'message' in record:
                        message = record['message']
                        usage = message.get('usage', {})

                        if usage:
                            timestamp = record.get('timestamp')
                            model = message.get('model', 'unknown')

                            usage_records.append({
                                'timestamp': timestamp,
                                'model': model,
                                'input_tokens': usage.get('input_tokens', 0),
                                'output_tokens': usage.get('output_tokens', 0),
                                'cache_creation_input_tokens': usage.get('cache_creation_input_tokens', 0),
                                'cache_read_input_tokens': usage.get('cache_read_input_tokens', 0),
                            })
                except json.JSONDecodeError:
                    continue
    except Exception as e:
        print(f"Error reading {file_path}: {e}")

    return usage_records


def get_5hour_block(timestamp_str):
    """Get the 5-hour block start time for a given timestamp."""
    try:
        # Parse ISO format timestamp
        if 'T' in timestamp_str:
            dt = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
        else:
            dt = datetime.strptime(timestamp_str, '%Y-%m-%d %H:%M:%S')

        # Calculate 5-hour block (0-5, 5-10, 10-15, 15-20, 20-24+)
        hour_block = (dt.hour // 5) * 5
        block_start = dt.replace(hour=hour_block, minute=0, second=0, microsecond=0)
        return block_start.isoformat()
    except:
        return None


def aggregate_usage(data_dir):
    """Aggregate usage from all JSONL files in data directory."""

    # Find all JSONL files
    jsonl_files = glob.glob(f"{data_dir}/**/projects/**/*.jsonl", recursive=True)

    if not jsonl_files:
        # Try alternate structure
        jsonl_files = glob.glob(f"{data_dir}/**/*.jsonl", recursive=True)

    print(f"Found {len(jsonl_files)} JSONL files")

    # Aggregate by date
    daily_usage = defaultdict(lambda: {
        'input_tokens': 0,
        'output_tokens': 0,
        'cache_creation_tokens': 0,
        'cache_read_tokens': 0,
        'total_tokens': 0,
        'models': set(),
        'sessions': set(),
    })

    # Aggregate by 5-hour block
    block_usage = defaultdict(lambda: {
        'input_tokens': 0,
        'output_tokens': 0,
        'cache_creation_tokens': 0,
        'cache_read_tokens': 0,
        'total_tokens': 0,
        'models': set(),
    })

    # Aggregate by model
    model_usage = defaultdict(lambda: {
        'input_tokens': 0,
        'output_tokens': 0,
        'total_tokens': 0,
    })

    # Track devices
    devices = set()

    for jsonl_file in jsonl_files:
        # Extract device name from path
        path_parts = Path(jsonl_file).parts
        for i, part in enumerate(path_parts):
            if part == 'data' and i + 1 < len(path_parts):
                devices.add(path_parts[i + 1])
                break

        session_id = Path(jsonl_file).stem
        records = parse_jsonl_file(jsonl_file)

        for record in records:
            timestamp = record.get('timestamp')
            if not timestamp:
                continue

            # Extract date
            try:
                if 'T' in timestamp:
                    date = timestamp.split('T')[0]
                else:
                    date = timestamp.split(' ')[0]
            except:
                continue

            model = record.get('model', 'unknown')
            input_tokens = record.get('input_tokens', 0)
            output_tokens = record.get('output_tokens', 0)
            cache_creation = record.get('cache_creation_input_tokens', 0)
            cache_read = record.get('cache_read_input_tokens', 0)
            total = input_tokens + output_tokens + cache_creation + cache_read

            # Daily aggregation
            daily_usage[date]['input_tokens'] += input_tokens
            daily_usage[date]['output_tokens'] += output_tokens
            daily_usage[date]['cache_creation_tokens'] += cache_creation
            daily_usage[date]['cache_read_tokens'] += cache_read
            daily_usage[date]['total_tokens'] += total
            daily_usage[date]['models'].add(model)
            daily_usage[date]['sessions'].add(session_id)

            # 5-hour block aggregation
            block = get_5hour_block(timestamp)
            if block:
                block_usage[block]['input_tokens'] += input_tokens
                block_usage[block]['output_tokens'] += output_tokens
                block_usage[block]['cache_creation_tokens'] += cache_creation
                block_usage[block]['cache_read_tokens'] += cache_read
                block_usage[block]['total_tokens'] += total
                block_usage[block]['models'].add(model)

            # Model aggregation
            model_usage[model]['input_tokens'] += input_tokens
            model_usage[model]['output_tokens'] += output_tokens
            model_usage[model]['total_tokens'] += total

    return {
        'daily': daily_usage,
        'blocks': block_usage,
        'models': model_usage,
        'devices': devices,
        'total_files': len(jsonl_files),
    }


def write_daily_csv(daily_usage, output_path):
    """Write daily usage to CSV."""
    with open(output_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow([
            'date', 'input_tokens', 'output_tokens',
            'cache_creation_tokens', 'cache_read_tokens',
            'total_tokens', 'models', 'session_count'
        ])

        for date in sorted(daily_usage.keys()):
            data = daily_usage[date]
            writer.writerow([
                date,
                data['input_tokens'],
                data['output_tokens'],
                data['cache_creation_tokens'],
                data['cache_read_tokens'],
                data['total_tokens'],
                ','.join(sorted(data['models'])),
                len(data['sessions']),
            ])

    print(f"Written daily usage to {output_path}")


def write_blocks_csv(block_usage, output_path):
    """Write 5-hour block usage to CSV."""

    # Estimate limit based on max usage (like ccusage does)
    max_tokens = max((b['total_tokens'] for b in block_usage.values()), default=1)
    # Use a reasonable estimate for Max plan limit
    estimated_limit = max(max_tokens * 1.5, 77_000_000)  # ~77M for Max plan

    with open(output_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow([
            'block_start', 'input_tokens', 'output_tokens',
            'cache_creation_tokens', 'cache_read_tokens',
            'total_tokens', 'usage_percentage', 'models'
        ])

        for block in sorted(block_usage.keys()):
            data = block_usage[block]
            percentage = (data['total_tokens'] / estimated_limit) * 100
            writer.writerow([
                block,
                data['input_tokens'],
                data['output_tokens'],
                data['cache_creation_tokens'],
                data['cache_read_tokens'],
                data['total_tokens'],
                f"{percentage:.2f}",
                ','.join(sorted(data['models'])),
            ])

    print(f"Written block usage to {output_path}")


def write_models_csv(model_usage, output_path):
    """Write model usage to CSV."""
    with open(output_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(['model', 'input_tokens', 'output_tokens', 'total_tokens'])

        for model in sorted(model_usage.keys()):
            data = model_usage[model]
            writer.writerow([
                model,
                data['input_tokens'],
                data['output_tokens'],
                data['total_tokens'],
            ])

    print(f"Written model usage to {output_path}")


def write_summary_csv(aggregated, output_path):
    """Write summary statistics to CSV."""
    daily = aggregated['daily']

    total_tokens = sum(d['total_tokens'] for d in daily.values())
    total_input = sum(d['input_tokens'] for d in daily.values())
    total_output = sum(d['output_tokens'] for d in daily.values())
    total_sessions = sum(len(d['sessions']) for d in daily.values())

    with open(output_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(['metric', 'value'])
        writer.writerow(['total_tokens', total_tokens])
        writer.writerow(['total_input_tokens', total_input])
        writer.writerow(['total_output_tokens', total_output])
        writer.writerow(['total_sessions', total_sessions])
        writer.writerow(['total_days', len(daily)])
        writer.writerow(['devices', len(aggregated['devices'])])
        writer.writerow(['jsonl_files_processed', aggregated['total_files']])
        writer.writerow(['last_updated', datetime.utcnow().isoformat()])

    print(f"Written summary to {output_path}")


def main():
    # Paths
    script_dir = Path(__file__).parent
    repo_root = script_dir.parent
    data_dir = repo_root / 'data'
    output_dir = repo_root / 'output'

    # Create output directory
    output_dir.mkdir(exist_ok=True)

    print(f"Scanning data directory: {data_dir}")

    # Aggregate usage
    aggregated = aggregate_usage(str(data_dir))

    print(f"Devices found: {aggregated['devices']}")
    print(f"Days with data: {len(aggregated['daily'])}")

    # Write CSV files
    write_daily_csv(aggregated['daily'], output_dir / 'daily_usage.csv')
    write_blocks_csv(aggregated['blocks'], output_dir / 'block_usage.csv')
    write_models_csv(aggregated['models'], output_dir / 'model_usage.csv')
    write_summary_csv(aggregated, output_dir / 'summary.csv')

    print("\nAggregation complete!")


if __name__ == '__main__':
    main()
