
import asyncio
from backend.api import run_pipeline, state

async def main():
    await asyncio.to_thread(run_pipeline)
    c = state.cost_data
    b = c['baseline_cost']
    n = c['naive_optimal']['total_cost']
    t = c['tiered_optimal']['total_cost']
    print(f'Baseline: {b}')
    print(f'Naive: {n}')
    print(f'Tiered: {t}')
    print(f'Savings vs Baseline: {100 - (t/b)*100:.2f}%')
    print(f'Savings vs Naive: {100 - (t/n)*100:.2f}%')

asyncio.run(main())

