"""固定同一船舶事件账本，比较 60/30/15 分钟时间片下的漏计船时阈值。

仅使用 Python 标准库。运行后在同目录输出 AIS时间分辨率_船时结果.json。
船舶真值仅用于生成/核对观测，不向阈值计算提供真实位置或活动容量。
有限穷举针对期×区聚合补量，无身份、航速和逐时容量约束；不是全轨迹枚举。
"""
from fractions import Fraction as F
from itertools import product
from math import comb
from pathlib import Path
import json

ROOT = Path(__file__).resolve().parent
PERIODS = ((F(0), F(2)), (F(2), F(4)))
H_VALUES = (F(1), F(1, 2), F(1, 4))
ATOM = F(1, 4)
# 所有时间分辨率读取这个相同账本，不重新模拟船舶或缺测。
FLEET = (
    ('W1', 0, ((F(0), F(4)),)),
    ('W2', 0, ((F(0), F(2)),)),
    ('W3', 0, ()),
    ('E1', 1, ((F(0), F(4)),)),
    ('E2', 1, ((F(2), F(4)),)),
    ('E3', 1, ()),
)
# 主实验候选块均恰好 2 小时；起止时刻不随时间片长度改变。
WINDOWS = ((F(0), F(2)), (F(1), F(3)), (F(2), F(4)))
SPACES = ((0,), (1,), (0, 1))
BLOCKS = tuple((space, start, end) for space in SPACES for start, end in WINDOWS)


def overlap(a, b, c, d):
    return max(F(0), min(b, d) - max(a, c))


def aggregate_events(h):
    rows = []
    for k in range(int(F(4) / h)):
        start, end = k * h, (k + 1) * h
        truth, seen = [F(0), F(0)], [F(0), F(0)]
        for boat, region, visible in FLEET:
            truth[region] += h
            seen[region] += sum((overlap(start, end, a, b) for a, b in visible), F(0))
        rows.append({'start': start, 'end': end, 'truth': truth, 'seen': seen,
                     'hidden': [x-y for x, y in zip(truth, seen)]})
    return rows


def monthly(rows, field):
    result = [F(0)] * 4  # W前,E前,W后,E后
    for row in rows:
        period = 0 if row['start'] < 2 else 1
        for s in (0, 1):
            result[2 * period + s] += row[field][s]
    return tuple(result)


def compositions(total, n):
    if n == 1:
        yield (total,)
    else:
        for first in range(total + 1):
            for tail in compositions(total-first, n-1):
                yield (first,) + tail


def delta(values):
    w1, e1, w2, e2 = values
    return e2/(w2+e2) - e1/(w1+e1)


def projected_constraints(block, h, full_bin):
    space, start, end = block
    present, minimum = [], []
    for a, b in PERIODS:
        duration = overlap(start, end, a, b)
        for s in (0, 1):
            covered = s in space and duration > 0
            present.append(covered)
            minimum.append(int(duration/h) if covered and full_bin else 0)
    return tuple(present), tuple(minimum)


def optimize(observed, h, mode, blocks=BLOCKS):
    # 仅旧整片规则随 h 改变整数单位；自由和范围模型均使用固定底层单位。
    quantum = h if mode == 'full_bin_positive' else ATOM
    limit = int(F(6)/quantum)  # 已验证总量 6 船时可行；不是容量上限。
    y = tuple(int(v/quantum) for v in observed)
    constraints = [projected_constraints(b, h, mode == 'full_bin_positive') for b in blocks]
    threshold = None
    witness = None
    evaluated = 0
    for total in range(limit+1):
        for values in compositions(total, 4):
            evaluated += 1
            w1,e1,w2,e2 = (a+b for a,b in zip(y,values))
            if e2*w1 > e1*w2:
                continue
            if mode == 'free':
                valid_block = -1
            else:
                valid_block = None
                for i,(present, minimum) in enumerate(constraints):
                    if all((present[j] and values[j]>=minimum[j]) or
                           (not present[j] and values[j]==0) for j in range(4)):
                        valid_block=i
                        break
                if valid_block is None:
                    continue
            if threshold is None:
                threshold=total*quantum
                witness={'aggregate_missing': [v*quantum for v in values], 'block_index':valid_block}
    assert evaluated == comb(limit+4,4)
    assert threshold is not None
    return {'threshold_vessel_hours': threshold, 'quantum_vessel_hours': quantum,
            'aggregate_vectors_enumerated': evaluated, 'witness': witness}


def make_json(value):
    if isinstance(value, F):
        return str(value)
    if isinstance(value, dict):
        return {key:make_json(item) for key,item in value.items()}
    if isinstance(value,(list,tuple)):
        return [make_json(item) for item in value]
    return value


def check_event_witness(rows, kind):
    corrected=[F(0)]*4
    total=F(0)
    for row in rows:
        a,b=row['start'],row['end']
        if kind=='full_bin_positive':
            extra=(F(0), 3*overlap(a,b,F(0),F(2)))
        else:
            extra=(2*overlap(a,b,F(2),F(3)),2*overlap(a,b,F(1),F(2)))
        period=0 if a<2 else 1
        for s in (0,1):
            corrected[2*period+s]+=row['seen'][s]+extra[s]
        total+=sum(extra)
    assert delta(corrected)==0
    assert total== (6 if kind=='full_bin_positive' else 4)
    return {'vessel_hours':total,'corrected_months':corrected,'delta':delta(corrected)}


def run():
    results=[]
    for h in H_VALUES:
        rows=aggregate_events(h)
        obs=monthly(rows,'seen')
        truth=monthly(rows,'truth')
        hidden=monthly(rows,'hidden')
        assert obs==(4,2,2,4) and truth==(6,6,6,6) and sum(hidden)==12
        solved={mode:optimize(obs,h,mode) for mode in ('free','full_bin_positive','outage_region')}
        assert [solved[m]['threshold_vessel_hours'] for m in solved]==[4,6,4]
        # 原模型是至少 2 小时；同一固定物理端点允许更长窗口也复核一次。
        windows_long=tuple((space,F(a),F(b)) for space in SPACES
                           for a in range(3) for b in range(a+2,5))
        checks_long={m:optimize(obs,h,m,windows_long)['threshold_vessel_hours']
                     for m in ('full_bin_positive','outage_region')}
        assert checks_long=={'full_bin_positive':6,'outage_region':4}
        results.append({'h_minutes':int(h*60),'required_bins_for_2h':int(2/h),
                        'observed_months_vessel_hours':obs,'truth_months_vessel_hours':truth,
                        'actual_hidden_vessel_hours':sum(hidden), 'aggregated_event_rows':rows,
                        'models':solved,'at_least_2h_same_endpoint_control':checks_long,
                        'verified_event_witnesses':{k:check_event_witness(rows,k)
                                                   for k in ('full_bin_positive','outage_region')}})
    output={'time_unit':'hours; two simulated periods [0,2),[2,4)',
            'fleet_truth_only':FLEET,'same_observation_events_across_h':True,
            'capacity_bound_used':False,'candidate_blocks':BLOCKS,
            'duration_hours':2,'latent_truth_is_not_assumed_to_follow_a_single_2h_outage':True,
            'exact_projection_condition':'No vessel identity, speed, or per-slot capacity constraints; all covered cells allow unbounded additions.',
            'results':results}
    dest=ROOT/'AIS时间分辨率_船时结果.json'
    dest.write_text(json.dumps(make_json(output),ensure_ascii=False,indent=2),encoding='utf-8')
    for row in results:
        print(row['h_minutes'], {k:str(v['threshold_vessel_hours']) for k,v in row['models'].items()},
              {k:v['aggregate_vectors_enumerated'] for k,v in row['models'].items()})
    return output


if __name__=='__main__':
    run()
