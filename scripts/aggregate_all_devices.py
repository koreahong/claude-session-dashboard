#!/usr/bin/env python3
"""
Aggregate usage data from all devices.
This runs on GitHub Actions to combine all device CSVs.
"""

import csv
import os
from datetime import datetime, timezone
from pathlib import Path
from collections import defaultdict


def read_device_csv(csv_path):
    """Read aggregated data from a device CSV."""
    records = []
    try:
        with open(csv_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                records.append(row)
    except Exception as e:
        print(f"Error reading {csv_path}: {e}")
    return records


def aggregate_devices(data_dir):
    """Find and aggregate all device CSVs."""
    
    data_path = Path(data_dir)
    device_csvs = list(data_path.glob('*/aggregated_data.csv'))
    
    print(f"Found {len(device_csvs)} device CSV files")
    
    all_records = []
    devices = set()
    
    for csv_path in device_csvs:
        device_name = csv_path.parent.name
        devices.add(device_name)
        records = read_device_csv(csv_path)
        all_records.extend(records)
        print(f"  - {device_name}: {len(records)} blocks")
    
    return all_records, devices


def write_combined_csv(records, output_path):
    """Write all records to combined CSV."""
    
    if not records:
        print("No records to write")
        return
    
    fieldnames = ['device', 'block_start', 'input_tokens', 'output_tokens',
                  'cache_creation_tokens', 'cache_read_tokens',
                  'total_tokens', 'usage_percentage', 'estimated_limit', 'models']
    
    with open(output_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        
        # Sort by block_start
        sorted_records = sorted(records, key=lambda r: r.get('block_start', ''))
        for record in sorted_records:
            writer.writerow(record)
    
    print(f"Written combined data to {output_path}")


def write_daily_summary(records, output_path):
    """Write daily summary CSV."""
    
    daily = defaultdict(lambda: {
        'total_tokens': 0,
        'input_tokens': 0,
        'output_tokens': 0,
        'blocks': 0,
        'devices': set(),
    })
    
    for record in records:
        block_start = record.get('block_start', '')
        if not block_start:
            continue
        
        date = block_start.split('T')[0]
        device = record.get('device', 'unknown')
        
        daily[date]['total_tokens'] += int(record.get('total_tokens', 0))
        daily[date]['input_tokens'] += int(record.get('input_tokens', 0))
        daily[date]['output_tokens'] += int(record.get('output_tokens', 0))
        daily[date]['blocks'] += 1
        daily[date]['devices'].add(device)
    
    with open(output_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(['date', 'total_tokens', 'input_tokens', 'output_tokens', 
                        'block_count', 'device_count', 'devices'])
        
        for date in sorted(daily.keys()):
            data = daily[date]
            writer.writerow([
                date,
                data['total_tokens'],
                data['input_tokens'],
                data['output_tokens'],
                data['blocks'],
                len(data['devices']),
                ','.join(sorted(data['devices'])),
            ])
    
    print(f"Written daily summary to {output_path}")


def write_summary(records, devices, output_path):
    """Write summary statistics."""
    
    total_tokens = sum(int(r.get('total_tokens', 0)) for r in records)
    total_blocks = len(records)
    
    with open(output_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(['metric', 'value'])
        writer.writerow(['total_tokens', total_tokens])
        writer.writerow(['total_blocks', total_blocks])
        writer.writerow(['device_count', len(devices)])
        writer.writerow(['devices', ','.join(sorted(devices))])
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
    
    # Aggregate
    records, devices = aggregate_devices(data_dir)
    
    if not records:
        print("No data found!")
        return
    
    print()
    
    # Write outputs
    write_combined_csv(records, output_dir / 'all_usage.csv')
    write_daily_summary(records, output_dir / 'daily_summary.csv')
    write_summary(records, devices, output_dir / 'summary.csv')
    
    print()
    print("Aggregation complete!")


if __name__ == '__main__':
    main()
