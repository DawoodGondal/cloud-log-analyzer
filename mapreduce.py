import re
import os
from multiprocessing import Pool
from collections import defaultdict

# ── helpers ──────────────────────────────────────────────────────────────────

LOG_PATTERN = re.compile(
    r'(?P<ip>\S+) \S+ \S+ \[(?P<time>[^\]]+)\] '
    r'"(?P<method>\S+) (?P<path>\S+) \S+" '
    r'(?P<status>\d{3}) (?P<size>\S+)'
)

ERROR_CODES = {'400', '401', '403', '404', '500', '502', '503'}

def parse_line(line):
    """Return (status_code, hour) or None if line doesn't match."""
    m = LOG_PATTERN.match(line)
    if not m:
        return None
    status = m.group('status')
    # time format: 01/Jan/2024:14:32:01 +0000
    try:
        hour = m.group('time').split(':')[1]   # '14'
        hour = f"Hour_{int(hour):02d}"
    except Exception:
        hour = 'Hour_00'
    return status, hour

# ── MapReduce stages ──────────────────────────────────────────────────────────

def split_chunk(lines):
    """SPLIT — one chunk of raw log lines."""
    return lines

def map_chunk(lines):
    """MAP — emit (key, 1) pairs for each line."""
    pairs = []
    for line in lines:
        result = parse_line(line)
        if result is None:
            continue
        status, hour = result
        if status in ERROR_CODES:
            pairs.append((f'ERROR_{status}', 1))
        pairs.append((hour, 1))
    return pairs

def shuffle_and_sort(all_pairs):
    """SHUFFLE & SORT — group values by key."""
    grouped = defaultdict(list)
    for key, value in all_pairs:
        grouped[key].append(value)
    return dict(sorted(grouped.items()))

def reduce_group(item):
    """REDUCE — sum values for one key (used with Pool.map)."""
    key, values = item
    return key, sum(values)

# ── Main entry point ──────────────────────────────────────────────────────────

def run_mapreduce(filepath, num_workers=4):
    """
    Full pipeline: Split → Map → Shuffle → Reduce
    Returns dict with 'errors' and 'traffic' sub-dicts.
    """
    # Read file
    with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
        lines = f.readlines()

    if not lines:
        return {'errors': {}, 'traffic': {}}

    # SPLIT — divide lines into chunks
    chunk_size = max(1, len(lines) // num_workers)
    chunks = [lines[i:i + chunk_size] for i in range(0, len(lines), chunk_size)]

    # MAP — process chunks in parallel
    with Pool(processes=num_workers) as pool:
        mapped_results = pool.map(map_chunk, chunks)

    # Flatten all (key, value) pairs
    all_pairs = [pair for chunk_pairs in mapped_results for pair in chunk_pairs]

    # SHUFFLE & SORT
    grouped = shuffle_and_sort(all_pairs)

    # REDUCE — aggregate counts in parallel
    with Pool(processes=num_workers) as pool:
        reduced = pool.map(reduce_group, list(grouped.items()))

    # Separate errors vs hourly traffic
    errors = {}
    traffic = {}
    for key, count in reduced:
        if key.startswith('ERROR_'):
            errors[key.replace('ERROR_', '')] = count
        elif key.startswith('Hour_'):
            traffic[key.replace('Hour_', '')] = count

    # Sort traffic by hour
    traffic = dict(sorted(traffic.items()))

    return {'errors': errors, 'traffic': traffic}