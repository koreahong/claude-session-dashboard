#!/usr/bin/env python3
"""
Extract Claude Code usage data from local ~/.claude/projects/ 
and output aggregated CSV for the dashboard.

Tracks:
1. 5-hour session usage percentage (all models)
2. Weekly usage percentage (all models)

Usage:
    python scripts/extract_local.py --device mac-work
    python scripts/extract_local.py --device mac-work --plan max5
"""

import json
import os
import csv
import argparse
from datetime import datetime, timedelta
from pathlib import Path
from collections import defaultdict


# Plan limits (estimated based on Anthropic documentation)
PLAN_LIMITS = {
    'pro': {
        'session_tokens': 44_000_000,
        'weekly_tokens': 300_000_000,
    },
    'max5': {
        'session_tokens': 88_000_000,
        'weekly_tokens': 600_000_000,
    },
    'max20': {
        'session_tokens': 220_000_000,
        'weekly_tokens': 1_500_000_000,
    },
}


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

                    if record.get('type') == 'assistant' and 'message' in record:
                        message = record['message']
                        usage = message.get('usage', {})

                        if usage:
                            timestamp = record.get('timestamp')

                            usage_records.append({
                                'timestamp': timestamp,
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


def parse_timestamp(timestamp_str):
    """Parse timestamp string to datetime."""
    try:
        if 'T' in timestamp_str:
            dt = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
        else:
            dt = datetime.strptime(timestamp_str, '%Y-%m-%d %H:%M:%S')
        
        if dt.tzinfo:
            dt = dt.replace(tzinfo=None)
        return dt
    except:
        return None


def get_5hour_block_start(dt):
    """Get the 5-hour block start time."""
    hour_block = (dt.hour // 5) * 5
    return dt.replace(hour=hour_block, minute=0, second=0, microsecond=0)


def get_week_start(dt):
    """Get the start of the week (Monday 00:00)."""
    days_since_monday = dt.weekday()
    week_start = dt - timedelta(days=days_since_monday)
    return week_start.replace(hour=0, minute=0, second=0, microsecond=0)


def extract_usage(claude_dir):
    """Extract usage data from all JSONL files."""
    
    projects_dir = Path(claude_dir) / 'projects'
    jsonl_files = list(projects_dir.glob('**/*.jsonl'))
    
    print(f"Found {len(jsonl_files)} JSONL files")

    all_records = []

    for jsonl_file in jsonl_files:
        records = parse_jsonl_file(jsonl_file)
        for record in records:
            timestamp = record.get('timestamp')
            if not timestamp:
                continue
            
            dt = parse_timestamp(timestamp)
            if not dt:
                continue
            
            record['datetime'] = dt
            all_records.append(record)

    return all_records


def aggregate_by_5hour_block(records, plan_limits):
    """Aggregate by 5-hour session blocks."""
    
    block_usage = defaultdict(lambda: {'total_tokens': 0})

    for record in records:
        dt = record.get('datetime')
        if not dt:
            continue

        block_start = get_5hour_block_start(dt)
        
        input_tokens = record.get('input_tokens', 0)
        output_tokens = record.get('output_tokens', 0)
        cache_creation = record.get('cache_creation_input_tokens', 0)
        cache_read = record.get('cache_read_input_tokens', 0)
        total = input_tokens + output_tokens + cache_creation + cache_read

        block_usage[block_start]['total_tokens'] += total

    # Calculate percentages
    session_limit = plan_limits['session_tokens']
    
    result = {}
    for block_start, data in block_usage.items():
        session_pct = (data['total_tokens'] / session_limit) * 100
        result[block_start] = {
            'total_tokens': data['total_tokens'],
            'session_usage_pct': round(session_pct, 2),
        }
    
    return result


def aggregate_by_week(records, plan_limits):
    """Aggregate by week for weekly limits."""
    
    week_usage = defaultdict(lambda: {'total_tokens': 0, 'days_active': set()})

    for record in records:
        dt = record.get('datetime')
        if not dt:
            continue

        week_start = get_week_start(dt)
        
        input_tokens = record.get('input_tokens', 0)
        output_tokens = record.get('output_tokens', 0)
        cache_creation = record.get('cache_creation_input_tokens', 0)
        cache_read = record.get('cache_read_input_tokens', 0)
        total = input_tokens + output_tokens + cache_creation + cache_read

        week_usage[week_start]['total_tokens'] += total
        week_usage[week_start]['days_active'].add(dt.date())

    # Calculate percentages
    weekly_limit = plan_limits['weekly_tokens']
    
    result = {}
    for week_start, data in week_usage.items():
        weekly_pct = (data['total_tokens'] / weekly_limit) * 100
        
        result[week_start] = {
            'total_tokens': data['total_tokens'],
            'weekly_usage_pct': round(weekly_pct, 2),
            'days_active': len(data['days_active']),
        }
    
    return result


def write_session_csv(block_usage, output_path, device_name):
    """Write 5-hour session data to CSV."""
    
    with open(output_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(['device', 'block_start', 'total_tokens', 'session_usage_pct'])

        for block_start in sorted(block_usage.keys()):
            data = block_usage[block_start]
            writer.writerow([
                device_name,
                block_start.isoformat(),
                data['total_tokens'],
                data['session_usage_pct'],
            ])

    print(f"Written session data to {output_path}")


def write_weekly_csv(week_usage, output_path, device_name):
    """Write weekly usage data to CSV."""
    
    with open(output_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(['device', 'week_start', 'total_tokens', 'weekly_usage_pct', 'days_active'])

        for week_start in sorted(week_usage.keys()):
            data = week_usage[week_start]
            writer.writerow([
                device_name,
                week_start.strftime('%Y-%m-%d'),
                data['total_tokens'],
                data['weekly_usage_pct'],
                data['days_active'],
            ])

    print(f"Written weekly data to {output_path}")


def main():
    parser = argparse.ArgumentParser(description='Extract Claude Code usage data')
    parser.add_argument('--device', required=True, help='Device name (e.g., mac-work)')
    parser.add_argument('--plan', default='max5', choices=['pro', 'max5', 'max20'],
                        help='Claude plan for limit calculation (default: max5)')
    parser.add_argument('--claude-dir', default=os.path.expanduser('~/.claude'), 
                        help='Claude data directory (default: ~/.claude)')
    parser.add_argument('--output-dir', default=None,
                        help='Output directory (default: repo/data/<device>/)')
    args = parser.parse_args()

    plan_limits = PLAN_LIMITS[args.plan]

    script_dir = Path(__file__).parent
    repo_root = script_dir.parent
    
    if args.output_dir:
        output_dir = Path(args.output_dir)
    else:
        output_dir = repo_root / 'data' / args.device
    
    output_dir.mkdir(parents=True, exist_ok=True)

    print(f"Device: {args.device}")
    print(f"Plan: {args.plan}")
    print(f"  Session limit: {plan_limits['session_tokens']:,} tokens")
    print(f"  Weekly limit: {plan_limits['weekly_tokens']:,} tokens")
    print()

    # Extract all records
    records = extract_usage(args.claude_dir)
    print(f"Total records: {len(records)}")
    print()

    # Aggregate
    block_usage = aggregate_by_5hour_block(records, plan_limits)
    print(f"5-hour blocks: {len(block_usage)}")

    week_usage = aggregate_by_week(records, plan_limits)
    print(f"Weeks: {len(week_usage)}")
    print()

    # Write outputs
    write_session_csv(block_usage, output_dir / 'session_usage.csv', args.device)
    write_weekly_csv(week_usage, output_dir / 'weekly_usage.csv', args.device)

    # Show current status
    print()
    print("=" * 50)
    print("CURRENT STATUS")
    print("=" * 50)
    
    now = datetime.now()
    current_block = get_5hour_block_start(now)
    current_week = get_week_start(now)
    
    if current_block in block_usage:
        data = block_usage[current_block]
        print(f"Current Session ({current_block.strftime('%H:%M')}):")
        print(f"  Usage: {data['session_usage_pct']:.1f}%")
    
    if current_week in week_usage:
        data = week_usage[current_week]
        print(f"\nWeekly Limit (week of {current_week.strftime('%Y-%m-%d')}):")
        print(f"  Usage: {data['weekly_usage_pct']:.1f}%")

    print()
    print(f"git add data/{args.device}/ && git commit -m 'Update {args.device}' && git push")


if __name__ == '__main__':
    main()
