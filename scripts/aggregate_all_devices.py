#!/usr/bin/env python3
"""
Aggregate usage data from all devices.
Runs on GitHub Actions to combine all device CSVs.
"""

import csv
import os
from datetime import datetime, timezone
from pathlib import Path
from collections import defaultdict


def read_csv(csv_path):
    """Read CSV file."""
    records = []
    try:
        with open(csv_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                records.append(row)
    except Exception as e:
        print(f"Error reading {csv_path}: {e}")
    return records


def aggregate_sessions(data_dir):
    """Aggregate session CSVs from all devices."""
    
    data_path = Path(data_dir)
    session_csvs = list(data_path.glob('*/session_usage.csv'))
    
    print(f"Found {len(session_csvs)} session CSV files")
    
    all_records = []
    devices = set()
    
    for csv_path in session_csvs:
        device_name = csv_path.parent.name
        devices.add(device_name)
        records = read_csv(csv_path)
        all_records.extend(records)
        print(f"  - {device_name}: {len(records)} sessions")
    
    return all_records, devices


def aggregate_weekly(data_dir):
    """Aggregate weekly CSVs from all devices."""
    
    data_path = Path(data_dir)
    weekly_csvs = list(data_path.glob('*/weekly_usage.csv'))
    
    print(f"Found {len(weekly_csvs)} weekly CSV files")
    
    all_records = []
    
    for csv_path in weekly_csvs:
        device_name = csv_path.parent.name
        records = read_csv(csv_path)
        all_records.extend(records)
        print(f"  - {device_name}: {len(records)} weeks")
    
    return all_records


def write_combined_sessions(records, output_path):
    """Write combined session data."""
    
    if not records:
        return
    
    fieldnames = ['device', 'block_start', 'total_tokens', 'sonnet_tokens',
                  'input_tokens', 'output_tokens', 'cache_creation_tokens', 'cache_read_tokens',
                  'session_usage_pct', 'session_limit', 'models']
    
    with open(output_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        
        sorted_records = sorted(records, key=lambda r: (r.get('block_start', ''), r.get('device', '')))
        for record in sorted_records:
            writer.writerow({k: record.get(k, '') for k in fieldnames})
    
    print(f"Written combined sessions to {output_path}")


def write_combined_weekly(records, output_path):
    """Write combined weekly data."""
    
    if not records:
        return
    
    fieldnames = ['device', 'week_start', 'total_tokens', 'sonnet_tokens',
                  'weekly_all_pct', 'weekly_sonnet_pct', 'weekly_limit', 'days_active', 'models']
    
    with open(output_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        
        sorted_records = sorted(records, key=lambda r: (r.get('week_start', ''), r.get('device', '')))
        for record in sorted_records:
            writer.writerow({k: record.get(k, '') for k in fieldnames})
    
    print(f"Written combined weekly to {output_path}")


def write_daily_summary(session_records, output_path):
    """Write daily summary from session records."""
    
    daily = defaultdict(lambda: {
        'total_tokens': 0,
        'sonnet_tokens': 0,
        'session_count': 0,
        'devices': set(),
        'max_session_pct': 0,
    })
    
    for record in session_records:
        block_start = record.get('block_start', '')
        if not block_start:
            continue
        
        date = block_start.split('T')[0]
        device = record.get('device', 'unknown')
        
        daily[date]['total_tokens'] += int(record.get('total_tokens', 0))
        daily[date]['sonnet_tokens'] += int(record.get('sonnet_tokens', 0))
        daily[date]['session_count'] += 1
        daily[date]['devices'].add(device)
        
        session_pct = float(record.get('session_usage_pct', 0))
        if session_pct > daily[date]['max_session_pct']:
            daily[date]['max_session_pct'] = session_pct
    
    with open(output_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(['date', 'total_tokens', 'sonnet_tokens', 'session_count', 
                        'max_session_pct', 'device_count', 'devices'])
        
        for date in sorted(daily.keys()):
            data = daily[date]
            writer.writerow([
                date,
                data['total_tokens'],
                data['sonnet_tokens'],
                data['session_count'],
                round(data['max_session_pct'], 2),
                len(data['devices']),
                ','.join(sorted(data['devices'])),
            ])
    
    print(f"Written daily summary to {output_path}")


def write_summary(session_records, weekly_records, devices, output_path):
    """Write overall summary."""
    
    total_tokens = sum(int(r.get('total_tokens', 0)) for r in session_records)
    total_sessions = len(session_records)
    total_weeks = len(weekly_records)
    
    # Get current week stats
    current_week = None
    if weekly_records:
        sorted_weekly = sorted(weekly_records, key=lambda r: r.get('week_start', ''), reverse=True)
        current_week = sorted_weekly[0] if sorted_weekly else None
    
    with open(output_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(['metric', 'value'])
        writer.writerow(['total_tokens', total_tokens])
        writer.writerow(['total_sessions', total_sessions])
        writer.writerow(['total_weeks', total_weeks])
        writer.writerow(['device_count', len(devices)])
        writer.writerow(['devices', ','.join(sorted(devices))])
        
        if current_week:
            writer.writerow(['current_week', current_week.get('week_start', '')])
            writer.writerow(['current_week_all_pct', current_week.get('weekly_all_pct', '')])
            writer.writerow(['current_week_sonnet_pct', current_week.get('weekly_sonnet_pct', '')])
        
        writer.writerow(['last_updated', datetime.now(timezone.utc).isoformat()])
    
    print(f"Written summary to {output_path}")


def main():
    script_dir = Path(__file__).parent
    repo_root = script_dir.parent
    data_dir = repo_root / 'data'
    output_dir = repo_root / 'output'
    
    output_dir.mkdir(exist_ok=True)
    
    print(f"Scanning: {data_dir}")
    print()
    
    # Aggregate sessions
    session_records, devices = aggregate_sessions(data_dir)
    
    # Aggregate weekly
    print()
    weekly_records = aggregate_weekly(data_dir)
    
    if not session_records:
        print("\nNo session data found!")
        return
    
    print()
    
    # Write outputs
    write_combined_sessions(session_records, output_dir / 'all_sessions.csv')
    write_combined_weekly(weekly_records, output_dir / 'all_weekly.csv')
    write_daily_summary(session_records, output_dir / 'daily_summary.csv')
    write_summary(session_records, weekly_records, devices, output_dir / 'summary.csv')
    
    print()
    print("Aggregation complete!")


if __name__ == '__main__':
    main()
