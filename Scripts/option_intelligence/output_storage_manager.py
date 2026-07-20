"""AQSD Output storage reporter and safe Temp/Logs cleanup utility."""
from __future__ import annotations
import argparse
from datetime import datetime, timedelta
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[2]
OUTPUT_DIR = BASE_DIR / 'Output'
TEMP_NAMES = {'temp', 'temporary', 'cache'}
LOG_NAMES = {'log', 'logs'}

def human_size(n: int) -> str:
    value = float(n)
    for unit in ('B','KB','MB','GB','TB'):
        if value < 1024 or unit == 'TB':
            return f'{value:.2f} {unit}'
        value /= 1024
    return f'{n} B'

def summary(folder: Path) -> tuple[int,int]:
    files = size = 0
    if not folder.exists():
        return files, size
    for p in folder.rglob('*'):
        if p.is_file():
            try:
                files += 1
                size += p.stat().st_size
            except OSError:
                pass
    return files, size

def candidates(temp_days: int, log_days: int) -> list[Path]:
    result = []
    if not OUTPUT_DIR.exists():
        return result
    now = datetime.now()
    for p in OUTPUT_DIR.rglob('*'):
        if not p.is_file():
            continue
        parents = {x.name.lower() for x in p.parents}
        days = None
        if parents & TEMP_NAMES or p.suffix.lower() in {'.tmp','.temp','.bak'}:
            days = temp_days
        elif parents & LOG_NAMES or p.suffix.lower() == '.log':
            days = log_days
        if days is None:
            continue
        try:
            modified = datetime.fromtimestamp(p.stat().st_mtime)
        except OSError:
            continue
        if modified < now - timedelta(days=days):
            result.append(p)
    return sorted(result)

def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--apply', action='store_true')
    parser.add_argument('--temp-days', type=int, default=7)
    parser.add_argument('--log-days', type=int, default=30)
    args = parser.parse_args()
    if args.temp_days < 1 or args.log_days < 1:
        raise SystemExit('Retention days must be at least 1.')
    before_files, before_size = summary(OUTPUT_DIR)
    items = candidates(args.temp_days, args.log_days)
    recoverable = sum(p.stat().st_size for p in items if p.exists())
    print('\n' + '=' * 72)
    print('AQSD OUTPUT STORAGE REPORT')
    print('=' * 72)
    print(f'Folder      : {OUTPUT_DIR}')
    print(f'Files       : {before_files}')
    print(f'Storage     : {human_size(before_size)}')
    print(f'Candidates  : {len(items)}')
    print(f'Recoverable : {human_size(recoverable)}')
    if not args.apply:
        print('\nREPORT ONLY — nothing deleted.')
        print('Use --apply to delete eligible Temp/Logs files.')
        return
    deleted = recovered = 0
    for p in items:
        try:
            size = p.stat().st_size
            p.unlink()
            deleted += 1
            recovered += size
            print(f'DELETED: {p}')
        except OSError as error:
            print(f'SKIPPED: {p} | {error}')
    _, final_size = summary(OUTPUT_DIR)
    print('\n' + '=' * 72)
    print('CLEANUP COMPLETED')
    print('=' * 72)
    print(f'Deleted   : {deleted}')
    print(f'Recovered : {human_size(recovered)}')
    print(f'New size  : {human_size(final_size)}')

if __name__ == '__main__':
    main()
