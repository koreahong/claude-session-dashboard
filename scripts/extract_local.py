#!/usr/bin/env python3
"""
Extract Claude Code usage data from local ~/.claude/projects/ 
and output aggregated CSV for the dashboard.

Run this script manually on each device, then push the CSV to the repo.

Usage:
    python scripts/extract_local.py --device mac-work
    python scripts/extract_local.py --device mac-home
"""

import json
import os
import csv
import argparse
from datetime import datetime, timezone
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


def get_5hour_block_start(timestamp_str):
    """Get the 5-hour block start time for a given timestamp."""
    try:
        if 'T' in timestamp_str:
            dt = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
        else:
            dt = datetime.strptime(timestamp_str, '%Y-%m-%d %H:%M:%S')
        
        # Remove timezone info for consistent grouping
        if dt.tzinfo:
            dt = dt.replace(tzinfo=None)

        # Calculate 5-hour block
        hour_block = (dt.hour // 5) * 5
        block_start = dt.replace(hour=hour_block, minute=0, second=0, microsecond=0)
        return block_start
    except:
        return None


def extract_usage(claude_dir):
    """Extract usage data from all JSONL files."""
    
    projects_dir = Path(claude_dir) / 'projects'
    jsonl_files = list(projects_dir.glob('**/*.jsonl'))
    
    print(f"Found {len(jsonl_files)} JSONL files")

    # Aggregate by 5-hour block
    block_usage = defaultdict(lambda: {
        'input_tokens': 0,
        'output_tokens': 0,
        'cache_creation_tokens': 0,
        'cache_read_tokens': 0,
        'total_tokens': 0,
        'models': set(),
    })

    for jsonl_file in jsonl_files:
        records = parse_jsonl_file(jsonl_file)

        for record in records:
            timestamp = record.get('timestamp')
            if not timestamp:
                continue

            block_start = get_5hour_block_start(timestamp)
            if not block_start:
                continue

            model = record.get('model', 'unknown')
            input_tokens = record.get('input_tokens', 0)
            output_tokens = record.get('output_tokens', 0)
            cache_creation = record.get('cache_creation_input_tokens', 0)
            cache_read = record.get('cache_read_input_tokens', 0)
            total = input_tokens + output_tokens + cache_creation + cache_read

            block_usage[block_start]['input_tokens'] += input_tokens
            block_usage[block_start]['output_tokens'] += output_tokens
            block_usage[block_start]['cache_creation_tokens'] += cache_creation
            block_usage[block_start]['cache_read_tokens'] += cache_read
            block_usage[block_start]['total_tokens'] += total
            block_usage[block_start]['models'].add(model)

    return block_usage


def calculate_usage_percentage(block_usage):
    """Calculate usage percentage for each 5-hour block."""
    
    # Estimate limit based on max usage (P90-like approach)
    if not block_usage:
        return {}
    
    all_totals = [b['total_tokens'] for b in block_usage.values()]
    # Use the maximum as an estimate of the limit (similar to ccusage)
    estimated_limit = max(all_totals) * 1.2 if all_totals else 77_000_000
    estimated_limit = max(estimated_limit, 77_000_000)  # Minimum for Max plan

    result = {}
    for block_start, data in block_usage.items():
        percentage = (data['total_tokens'] / estimated_limit) * 100
        result[block_start] = {
            **data,
            'usage_percentage': round(percentage, 2),
            'estimated_limit': int(estimated_limit),
        }
    
    return result


def write_aggregated_csv(block_usage, output_path, device_name):
    """Write aggregated data to CSV."""
    
    with open(output_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow([
            'device', 'block_start', 'input_tokens', 'output_tokens',
            'cache_creation_tokens', 'cache_read_tokens',
            'total_tokens', 'usage_percentage', 'estimated_limit', 'models'
        ])

        for block_start in sorted(block_usage.keys()):
            data = block_usage[block_start]
            writer.writerow([
                device_name,
                block_start.isoformat(),
                data['input_tokens'],
                data['output_tokens'],
                data['cache_creation_tokens'],
                data['cache_read_tokens'],
                data['total_tokens'],
                data['usage_percentage'],
                data['estimated_limit'],
                ','.join(sorted(data['models'])),
            ])

    print(f"Written aggregated data to {output_path}")


def main():
    parser = argparse.ArgumentParser(description='Extract Claude Code usage data')
    parser.add_argument('--device', required=True, help='Device name (e.g., mac-work, mac-home)')
    parser.add_argument('--claude-dir', default=os.path.expanduser('~/.claude'), 
                        help='Claude data directory (default: ~/.claude)')
    parser.add_argument('--output-dir', default=None,
                        help='Output directory (default: repo/data/<device>/)')
    args = parser.parse_args()

    # Determine output directory
    script_dir = Path(__file__).parent
    repo_root = script_dir.parent
    
    if args.output_dir:
        output_dir = Path(args.output_dir)
    else:
        output_dir = repo_root / 'data' / args.device
    
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / 'aggregated_data.csv'

    print(f"Device: {args.device}")
    print(f"Claude directory: {args.claude_dir}")
    print(f"Output: {output_path}")
    print()

    # Extract and process
    block_usage = extract_usage(args.claude_dir)
    print(f"Found {len(block_usage)} 5-hour blocks")

    block_usage_with_percentage = calculate_usage_percentage(block_usage)

    # Write output
    write_aggregated_csv(block_usage_with_percentage, output_path, args.device)

    print()
    print("Done! Now you can:")
    print(f"  git add data/{args.device}/")
    print(f"  git commit -m 'Update usage data from {args.device}'")
    print("  git push")


if __name__ == '__main__':
    main()
