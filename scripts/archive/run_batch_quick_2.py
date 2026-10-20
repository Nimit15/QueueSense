import os
os.chdir('D:/QueueSense')
exec(open('run_benchmark_batched.py').read().replace('results/benchmark',
    'results/benchmark_valid'))
" --batch_name 'batch1' --scenarios 'light bottleneck' --seeds '42 43 44 45' --output-dir 'results/benchmark_valid' 2>&1 | tail -40