"""AQSD analytics-only refresh runner. Does not open the dashboard."""
from __future__ import annotations
import subprocess, sys, time
from dataclasses import dataclass
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[2]

@dataclass(frozen=True)
class Step:
    number: int
    title: str
    module: str

STEPS = (
    Step(1, 'Live Decision Engine', 'Scripts.option_intelligence.live_decision_runner'),
    Step(2, 'Live IV Surface', 'Scripts.option_intelligence.live_iv_surface_runner'),
    Step(3, 'Live Volatility Analytics', 'Scripts.option_intelligence.live_volatility_analytics_runner'),
    Step(4, 'Live Probability V2', 'Scripts.option_intelligence.live_probability_v2_runner'),
)

def run_step(step: Step) -> None:
    print('\n' + '=' * 78, flush=True)
    print(f'STEP {step.number} : {step.title}', flush=True)
    print('=' * 78, flush=True)
    started = time.perf_counter()
    result = subprocess.run([sys.executable, '-u', '-m', step.module], cwd=BASE_DIR, check=False)
    if result.returncode != 0:
        raise RuntimeError(f'{step.title} failed with return code {result.returncode}.')
    print(f'SUCCESS ({time.perf_counter() - started:.1f} sec)', flush=True)

def main() -> None:
    started = time.perf_counter()
    print('\n' + '=' * 78, flush=True)
    print('AQSD OPTION INTELLIGENCE ANALYTICS REFRESH', flush=True)
    print('DASHBOARD WILL NOT BE OPENED', flush=True)
    print('=' * 78, flush=True)
    try:
        for step in STEPS:
            run_step(step)
    except (OSError, RuntimeError, subprocess.SubprocessError) as error:
        print('\nANALYTICS REFRESH FAILED', flush=True)
        print(str(error), flush=True)
        raise SystemExit(1) from error
    print('\n' + '=' * 78, flush=True)
    print('ALL ANALYTICS MODULES COMPLETED SUCCESSFULLY', flush=True)
    print(f'Total time: {time.perf_counter() - started:.1f} sec', flush=True)
    print('Use the DASHBOARD button to open the dashboard.', flush=True)
    print('=' * 78, flush=True)

if __name__ == '__main__':
    main()
