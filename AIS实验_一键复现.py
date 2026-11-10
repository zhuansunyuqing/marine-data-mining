"""在新目录中重跑三个主实验和三个独立核验，仅使用 Python 标准库。

运行：python -X utf8 AIS实验_一键复现.py --output-dir 复现输出
输出目录必须尚不存在，防止旧结果被当作本次结果或被覆盖。
"""
from pathlib import Path
from datetime import datetime
import argparse
import hashlib
import json
import os
import platform
import shutil
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parent
MAIN = (
    'AIS缺测阈值_小规模穷举.py',
    'AIS时间分辨率_船时对照.py',
    'AIS缺测模型_删减检查.py',
)
VERIFY = (
    '.report_build/verify_simulation.py',
    '.report_build/verify_time_resolution.py',
    '.report_build/verify_presence_audit.py',
)


def read_json(path):
    return json.loads(path.read_text(encoding='utf-8'))


def write_json(path, obj):
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding='utf-8')


def main():
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', default='复现输出', help='项目目录下的新目录，亦可为绝对路径')
    args = parser.parse_args()
    if sys.flags.optimize:
        parser.error('请勿使用 -O 或 -OO，实验需要启用内置断言。')
    dest = Path(args.output_dir)
    if not dest.is_absolute():
        dest = ROOT / dest
    dest = dest.resolve()
    if dest.exists():
        parser.error('输出目录已经存在；请换用一个新名称，例如 --output-dir 复现输出_第二次。')
    for rel in MAIN + VERIFY:
        if not (ROOT / rel).is_file():
            parser.error('缺少脚本：' + rel)
    dest.mkdir(parents=True)
    (dest / '.report_build').mkdir()
    (dest / 'logs').mkdir()
    record = {
        'status': 'running', 'started_at': datetime.now().astimezone().isoformat(),
        'python_version': platform.python_version(), 'python_executable': sys.executable,
        'platform': platform.platform(), 'output_directory': str(dest),
        'runner_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        'source_sha256': {}, 'runs': [], 'checks': [],
    }
    record_path = dest / '复现核对记录.json'
    for rel in MAIN + VERIFY:
        source = ROOT / rel
        record['source_sha256'][rel] = hashlib.sha256(source.read_bytes()).hexdigest()
        shutil.copy2(source, dest / rel)

    def check(label, actual, expected):
        passed = actual == expected
        record['checks'].append({'item': label, 'actual': actual, 'expected': expected, 'passed': passed})
        if not passed:
            raise RuntimeError(f'{label}: 实际 {actual!r}，预期 {expected!r}')

    started = time.perf_counter()
    try:
        for rel in MAIN + VERIFY:
            command = [sys.executable, '-X', 'utf8', str(dest / rel)]
            env = os.environ.copy()
            env['PYTHONUTF8'] = '1'
            env['PYTHONIOENCODING'] = 'utf-8'
            step_start = time.perf_counter()
            completed = subprocess.run(command, cwd=dest, env=env, capture_output=True,
                                       encoding='utf-8', errors='strict')
            log = dest / 'logs' / (Path(rel).stem + '.txt')
            log.write_text(completed.stdout + ('\nSTDERR\n' + completed.stderr if completed.stderr else ''),
                           encoding='utf-8')
            record['runs'].append({'script': rel, 'command': command,
                                   'exit_code': completed.returncode,
                                   'seconds': round(time.perf_counter() - step_start, 3),
                                   'log': str(log.relative_to(dest))})
            if completed.returncode:
                raise RuntimeError('脚本运行失败，请检查日志：' + str(log))
            if rel == VERIFY[0]:
                write_json(dest / '.report_build/verify_simulation_results.json',
                           json.loads(completed.stdout))
            print('完成 ' + rel, flush=True)

        sim = read_json(dest / 'AIS缺测阈值_模拟结果.json')
        timing = read_json(dest / 'AIS时间分辨率_船时结果.json')
        audit = read_json(dest / 'AIS缺测模型_检查结果.json')
        independent = read_json(dest / '.report_build/verify_simulation_results.json')
        independent_time = read_json(dest / '.report_build/verify_time_resolution_results.json')
        independent_audit = read_json(dest / '.report_build/verify_presence_audit_results.json')
        model_keys = ('free', 'one_block', 'two_blocks')
        primary_thresholds = [sim['models'][k]['threshold'] for k in model_keys]
        check('表4-2 自由 单块 双块阈值', primary_thresholds, [4, 6, 4])
        check('表4-2 主实验枚举总数', sim['enumerated_configurations'], 3003)
        check('表4-2 合法配置数 含全零', [sim['models'][k]['admissible_count'] for k in model_keys], [3003, 248, 418])
        check('表4-2 最优解数', [sim['models'][k]['optimal_count'] for k in model_keys], [9, 10, 1])
        ikeys = ('free', 'exactly_one_block_min_duration_2', 'at_most_two_blocks_min_duration_2')
        check('独立核验 原实验阈值', [independent['results'][k]['minimum_mass'] for k in ikeys], primary_thresholds)
        check('独立单块合法数 加入全零后对齐',
              independent['results'][ikeys[1]]['legal_allocations_with_mass_at_most_6'] + 1,
              sim['models']['one_block']['admissible_count'])
        scale_thresholds = []
        for row in timing['results']:
            values = [str(row['models'][k]['threshold_vessel_hours'])
                      for k in ('free', 'full_bin_positive', 'outage_region')]
            scale_thresholds.append([row['h_minutes']] + values)
            check(f"表5-1 {row['h_minutes']}分钟船时阈值", values, ['4', '6', '4'])
            check(f"表5-1 {row['h_minutes']}分钟观测船时",
                  row['observed_months_vessel_hours'], ['4', '2', '2', '4'])
        for row in independent_time['by_h']:
            check('独立聚合核验 片长' + row['h_hours'],
                  [row['free']['threshold_ship_hours'], row['A_full_bin_rule']['threshold_ship_hours'],
                   row['B_mask_fixed_atomic_grid']['threshold_ship_hours']], ['4', '6', '4'])
        growth = audit['new_growth_example']
        growth_thresholds = [growth['models'][k]['threshold'] for k in ('A', 'B')]
        check('表6-3 三海区A B阈值', growth_thresholds, [6, 2])
        check('表6-3 三海区枚举总数', growth['enumerated'], 924)
        check('表6-3 三海区最优解数', [len(growth['models'][k]['optimal']) for k in ('A', 'B')], [1, 21])
        check('表6-2 展示的B补法属于最优解', growth['actual_hidden_early'] in growth['models']['B']['optimal'], True)
        totals = []
        for early in (True, False):
            observed = sum(map(sum, growth['observed_early' if early else 'observed_late']))
            truth = sum(map(sum, growth['truth_each_period']))
            add_a = sum(growth['models']['A']['optimal'][0]) if early else 0
            add_b = sum(growth['actual_hidden_early']) if early else 0
            totals.append([truth, observed, truth-observed, add_a, observed+add_a, add_b, observed+add_b])
        check('表6-2 两期合计 真值 观测 实漏 A补 A后 B补 B后', totals,
              [[10, 8, 2, 6, 14, 2, 10], [10, 10, 0, 0, 10, 0, 10]])
        ia = independent_audit['new_three_region_total_activity_example']
        check('独立核验 三海区阈值', [ia['models'][k]['minimum_ship_hours'] for k in ('A', 'B')], growth_thresholds)
        check('表6-1 原例条件下界', [audit['old_cross_period_mask_4_cells'][k]['conditional_minimum_in_box'] for k in ('A', 'B')], [1, 0])
        check('表6-3 新例中区条件下界', [audit['new_first_period_mask_6_cells'][k]['conditional_minimum_in_box'] for k in ('A', 'B')], [2, 0])
        for key, source in (('AIS缺测阈值_模拟结果.json', sim),
                            ('AIS时间分辨率_船时结果.json', timing),
                            ('AIS缺测模型_检查结果.json', audit)):
            reference = ROOT / key
            if reference.is_file():
                check('重新生成结果与报告原始结果逐字段一致 ' + key,
                      source == read_json(reference), True)
            else:
                record.setdefault('optional_reference_comparisons_skipped', []).append(key)
        record['summary'] = {'original_thresholds': primary_thresholds,
                             'time_resolution_thresholds': scale_thresholds,
                             'new_growth_thresholds': growth_thresholds,
                             'all_checks_passed': True}
        record['status'] = 'passed'
        print('PASS 原始计数阈值: 4, 6, 4')
        print('PASS 60/30/15分钟船时阈值: 每行4, 6, 4')
        print('PASS 三海区总量阈值: 6, 2')
    except Exception as error:
        record['status'] = 'failed'
        record['error'] = str(error)
        raise
    finally:
        record['finished_at'] = datetime.now().astimezone().isoformat()
        record['elapsed_seconds'] = round(time.perf_counter() - started, 3)
        write_json(record_path, record)
    print('核对记录：' + str(record_path))


if __name__ == '__main__':
    main()
