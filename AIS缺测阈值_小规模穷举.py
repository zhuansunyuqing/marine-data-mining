"""两个月 AIS 活动占比的确定性小规模模拟，仅使用 Python 标准库。

运行: python AIS缺测阈值_小规模穷举.py
输出: 同目录 AIS缺测阈值_模拟结果.json

输入是 2 海区 × 4 等长连续时段的计数。无逐格、逐时或总体活动容量上限。
穷举截止来自已验证可行反例的成本，并非对未知真值的容量假设。
"""
from fractions import Fraction
from itertools import combinations
from math import comb
from pathlib import Path
import json

ROOT = Path(__file__).resolve().parent
# 按时间排列，每一项为 [西侧, 东侧]；前两个时段属月 1，后两个属月 2。
TRUTH = ((3, 3),) * 4
HIDDEN = ((1, 2), (1, 2), (2, 1), (2, 1))
OBSERVED = tuple(tuple(x - m for x, m in zip(row, miss))
                 for row, miss in zip(TRUTH, HIDDEN))


def months(flat):
    """flat 顺序: W1,E1,W2,E2,W3,E3,W4,E4。"""
    return ((flat[0] + flat[2], flat[1] + flat[3]),
            (flat[4] + flat[6], flat[5] + flat[7]))


def east_change(flat):
    (w1, e1), (w2, e2) = months(flat)
    return Fraction(e2, w2 + e2) - Fraction(e1, w1 + e1)


def weak_compositions(total, size):
    if size == 1:
        yield (total,)
    else:
        for first in range(total + 1):
            for tail in weak_compositions(total - first, size - 1):
                yield (first,) + tail


def rectangles(min_duration):
    """空间为 W、E 或相邻的 W+E；时间为连续区间。正支持等于矩形。"""
    return {frozenset(2 * t + s for t in range(a, b + 1) for s in space)
            for space in ((0,), (1,), (0, 1))
            for a in range(4) for b in range(a + min_duration - 1, 4)}


def support_unions(rects, max_blocks):
    supports = {frozenset()} | rects
    if max_blocks == 2:
        supports |= {r | q for r, q in combinations(rects, 2) if r.isdisjoint(q)}
    return supports


def run():
    observed_flat = tuple(v for row in OBSERVED for v in row)
    # 只在第一个月东侧两个时段各补 3：成本 6，是单块及其放宽模型的可行解。
    witness = (0, 3, 0, 3, 0, 0, 0, 0)
    upper_bound = sum(witness)
    assert east_change(tuple(y + m for y, m in zip(observed_flat, witness))) == 0
    rects = rectangles(min_duration=2)
    one = support_unions(rects, 1)
    two = support_unions(rects, 2)
    one_short = support_unions(rectangles(min_duration=1), 1)
    assert frozenset(i for i, m in enumerate(witness) if m) in one
    model_supports = {'free': None, 'one_block': one,
                      'two_blocks': two, 'one_block_duration1': one_short}
    stats = {name: {'admissible_by_exact_budget': [0] * (upper_bound + 1),
                    'counterexamples_by_exact_budget': [0] * (upper_bound + 1),
                    'threshold': None, 'optimal_configs': [],
                    'lower_delta_by_budget': []}
             for name in model_supports}
    minima = {name: [None] * (upper_bound + 1) for name in stats}
    enumerated = 0
    for budget in range(upper_bound + 1):
        for miss in weak_compositions(budget, 8):
            enumerated += 1
            support = frozenset(i for i, value in enumerate(miss) if value)
            filled = tuple(y + m for y, m in zip(observed_flat, miss))
            delta = east_change(filled)
            (w1, e1), (w2, e2) = months(filled)
            # 整数交叉相乘与精确分数独立核对判定，避免浮点相等误差。
            overturns = e2 * w1 <= e1 * w2
            assert overturns == (delta <= 0)
            for name, allowed in model_supports.items():
                if allowed is not None and support not in allowed:
                    continue
                stat = stats[name]
                stat['admissible_by_exact_budget'][budget] += 1
                old = minima[name][budget]
                minima[name][budget] = delta if old is None else min(old, delta)
                if overturns:
                    stat['counterexamples_by_exact_budget'][budget] += 1
                    if stat['threshold'] is None:
                        stat['threshold'] = budget
                    if stat['threshold'] == budget:
                        stat['optimal_configs'].append(list(miss))
    assert enumerated == comb(upper_bound + 8, 8) == 3003
    for name, stat in stats.items():
        best = None
        for d in minima[name]:
            if d is not None:
                best = d if best is None else min(best, d)
            stat['lower_delta_by_budget'].append(str(best))
        stat['admissible_count'] = sum(stat['admissible_by_exact_budget'])
        stat['optimal_count'] = len(stat['optimal_configs'])
        b = stat['threshold']
        stat['threshold_missing_fraction'] = str(Fraction(b, sum(observed_flat) + b))
    assert [stats[n]['threshold'] for n in ('free', 'one_block', 'two_blocks')] == [4, 6, 4]
    # 用便于阅读的代表解核对最终月度计数。
    witnesses = {
        'free': (0, 1, 0, 1, 1, 0, 1, 0),
        'one_block': witness,
        'two_blocks': (0, 1, 0, 1, 1, 0, 1, 0),
    }
    for name, miss in witnesses.items():
        assert list(miss) in stats[name]['optimal_configs']
        filled = tuple(y + m for y, m in zip(observed_flat, miss))
        stats[name]['representative_missing_by_time'] = [list(miss[i:i + 2]) for i in range(0, 8, 2)]
        stats[name]['representative_monthly_true_counts'] = months(filled)
        stats[name]['representative_delta'] = str(east_change(filled))
    continuous_checks = []
    for epsilon in (Fraction(1, 10), Fraction(1, 100)):
        miss = (0, 0, epsilon, 2 + epsilon, 2 + epsilon, epsilon, 0, 0)
        assert frozenset(i for i, value in enumerate(miss) if value) in one
        filled = tuple(y + m for y, m in zip(observed_flat, miss))
        assert east_change(filled) == 0
        continuous_checks.append({'epsilon': str(epsilon),
                                  'total_missing': str(sum(miss)),
                                  'delta': str(east_change(filled)),
                                  'missing': [str(m) for m in miss]})
    result = {
        'experiment_type': 'deterministic synthetic example; not real AIS and not Monte Carlo',
        'capacity_upper_bound': None,
        'input_observed_by_time_WE': OBSERVED,
        'latent_simulated_truth_by_time_WE': TRUTH,
        'latent_hidden_by_time_WE': HIDDEN,
        'latent_hidden_total': sum(map(sum, HIDDEN)),
        'observed_east_share_change': str(east_change(observed_flat)),
        'latent_true_east_share_change': str(east_change(tuple(v for r in TRUTH for v in r))),
        'positive_support_rule': 'one rectangle, or union of at most two disjoint rectangles; each block cell >= 1; outside = 0; zero missing allowed',
        'minimum_block_duration': 2,
        'candidate_rectangles': len(rects),
        'enumeration_budget_from_verified_witness': upper_bound,
        'enumerated_configurations': enumerated,
        'models': stats,
        'continuous_positive_support_checks': continuous_checks,
        'continuous_one_block_infimum': 4,
        'continuous_one_block_infimum_attained': False,
    }
    dest = ROOT / 'AIS缺测阈值_模拟结果.json'
    dest.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({k: {n: v[n] for n in ('threshold', 'admissible_count', 'optimal_count', 'lower_delta_by_budget')}
                      for k, v in stats.items()}, ensure_ascii=False, indent=2))
    return result


if __name__ == '__main__':
    run()
