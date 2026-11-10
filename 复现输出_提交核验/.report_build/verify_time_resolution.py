"""Independent, exact check of a fixed-event-ledger time-resolution experiment.

The search enumerates FOUR monthly/region totals, not vessel trajectories.
Compression is exact only for the explicitly stated allocation models: no
vessel identity, movement, or per-time capacity restrictions are imposed on M.
The six-vessel truth is used solely to generate the same observations at each h.
"""
from fractions import Fraction as F
from math import comb
from pathlib import Path
import json

ROOT = Path(__file__).resolve().parent
HORIZON = F(4)
PERIODS = ((F(0), F(2)), (F(2), F(4)))
HS = (F(1), F(1, 2), F(1, 4))
DELTA = F(1, 4)
SPACES = ((0,), (1,), (0, 1))
# At every instant: three fixed-position ships in W, three in E.
# Each of the six identities is received in one of the two periods.
EVENTS = []
for region, prefix in ((0, 'W'), (1, 'E')):
    for ship in (1, 2, 3):
        for period, (start, end) in enumerate(PERIODS):
            received = ((ship in (1, 2)) if period == 0 else ship == 3) if region == 0 else (
                ship == 1 if period == 0 else ship in (2, 3))
            EVENTS.append((prefix + str(ship), region, start, end, received))


def overlap(a, b, c, d):
    return max(F(0), min(b, d) - max(a, c))


def event_aggregate(h, received_only):
    rows = []
    for j in range(int(HORIZON / h)):
        a, b = j * h, (j + 1) * h
        rows.append(tuple(sum(overlap(a, b, start, end)
                              for _, region, start, end, received in EVENTS
                              if region == s and (received or not received_only))
                          for s in (0, 1)))
    return rows


def period_totals(rows):
    mid = len(rows) // 2
    return tuple(sum(row[s] for row in rows[a:b])
                 for a, b in ((0, mid), (mid, len(rows))) for s in (0, 1))


OBS = (F(4), F(2), F(2), F(4))


def eliminates_shift(m):
    w1, e1, w2, e2 = tuple(y + x for y, x in zip(OBS, m))
    return e2 * w1 <= e1 * w2


def compositions_at_most(budget, n=4):
    if n == 0:
        yield ()
        return
    for first in range(budget + 1):
        for rest in compositions_at_most(budget - first, n - 1):
            yield (first,) + rest


def physical_candidates(exact=True):
    intervals = [(F(a), F(b)) for a in range(4) for b in range(a + 2, 5)
                 if (b - a == 2 or not exact)]
    return [(space, a, b) for space in SPACES for a, b in intervals]


def aggregate_requirements(block, quantum, full_bin):
    space, a, b = block
    durations = tuple(overlap(a, b, start, end) if s in space else F(0)
                      for start, end in PERIODS for s in (0, 1))
    assert all(d / quantum == int(d / quantum) for d in durations)
    allowed = tuple(d > 0 for d in durations)
    minimum = tuple(int(d / quantum) if full_bin else 0 for d in durations)
    return allowed, minimum


def compatible(q, requirements):
    allowed, minimum = requirements
    return all(value >= lower and (active or value == 0)
               for value, active, lower in zip(q, allowed, minimum))


def solve(quantum, model, exact=True):
    # A concrete A counterexample has cost 6 ship-hours. Therefore searching
    # to cost 6 proves a global minimum for A, B, and the free relaxation.
    cutoff = int(F(6) / quantum)
    reqs = [aggregate_requirements(b, quantum, model == 'full_bin')
            for b in physical_candidates(exact)]
    count = legal = counterexamples = 0
    best = None
    optima = []
    for q in compositions_at_most(cutoff):
        count += 1
        if model != 'free' and any(q) and not any(compatible(q, r) for r in reqs):
            continue
        legal += 1
        mass = tuple(quantum * value for value in q)
        if not eliminates_shift(mass):
            continue
        counterexamples += 1
        cost = sum(mass)
        if best is None or cost < best:
            best, optima = cost, [mass]
        elif cost == best:
            optima.append(mass)
    assert count == comb(cutoff + 4, 4)
    return {'threshold_ship_hours': str(best),
            'physical_candidates': len(reqs),
            'aggregate_vectors_enumerated': count,
            'legal_aggregate_vectors': legal,
            'counterexample_aggregate_vectors': counterexamples,
            'optimal_aggregate_vectors': [list(map(str, x)) for x in optima]}


def profile_aggregate(profile, h):
    rows = []
    for j in range(int(HORIZON / h)):
        a, b = j * h, (j + 1) * h
        rows.append(tuple(sum(rate * overlap(a, b, start, end)
                              for region, start, end, rate in profile if region == s)
                          for s in (0, 1)))
    return rows


def main():
    result = {
        'units': 'ship-hours',
        'main_duration_hours': '2',
        'main_start_times_hours': ['0', '1', '2'],
        'model_B_fixed_atomic_quantum_hours': str(DELTA),
        'candidate_A_witness': 'E, [0,2): 3 unobserved ships throughout; cost 6',
        'candidate_B_witness': 'E, [1,2): 2 ships; W, [2,3): 2 ships; cost 4; mask W+E x [1,3)',
        'search_scope': 'monthly region totals, not full vessel trajectories',
        'compression_assumptions': 'no identity, speed, movement, or per-time capacity constraints on M',
        'truth_role': 'same six-vessel event ledger generates observations; not a constraint on candidate M',
        'true_hidden_ship_hours': '12',
        'actual_generation_is_single_D2_block': False,
        'by_h': [],
    }
    witness_A = [(1, F(0), F(2), F(3))]
    witness_B = [(1, F(1), F(2), F(2)), (0, F(2), F(3), F(2))]
    b_solution = solve(DELTA, 'mask')
    assert b_solution['threshold_ship_hours'] == '4'
    for h in HS:
        truth, observed = event_aggregate(h, False), event_aggregate(h, True)
        assert period_totals(truth) == (F(6),) * 4
        assert period_totals(observed) == OBS
        a = solve(h, 'full_bin')
        free = solve(h, 'free')
        a_long = solve(h, 'full_bin', exact=False)
        b_long = solve(DELTA, 'mask', exact=False)
        assert a['threshold_ship_hours'] == a_long['threshold_ship_hours'] == '6'
        assert free['threshold_ship_hours'] == b_long['threshold_ship_hours'] == '4'
        am, bm = profile_aggregate(witness_A, h), profile_aggregate(witness_B, h)
        assert sum(map(sum, am)) == 6 and eliminates_shift(period_totals(am))
        assert sum(map(sum, bm)) == 4 and eliminates_shift(period_totals(bm))
        assert all(sum(row) <= 3 * h for row in am + bm)
        result['by_h'].append({
            'h_hours': str(h),
            'observed_ship_hours_by_bin_WE': [list(map(str, row)) for row in observed],
            'observed_period_totals_W1_E1_W2_E2': list(map(str, OBS)),
            'A_full_bin_rule': a,
            'B_mask_fixed_atomic_grid': b_solution,
            'free': free,
            'duration_at_least_2_same_fixed_integer_hour_endpoints': {
                'A': a_long['threshold_ship_hours'], 'B': b_long['threshold_ship_hours'],
                'physical_candidates': a_long['physical_candidates']},
            'witness_A_by_bin_WE': [list(map(str, row)) for row in am],
            'witness_B_by_bin_WE': [list(map(str, row)) for row in bm],
        })
    output = ROOT / 'verify_time_resolution_results.json'
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({'verified': True, 'result': str(output),
                      'thresholds': [[row['h_hours'], row['free']['threshold_ship_hours'],
                                      row['A_full_bin_rule']['threshold_ship_hours'],
                                      row['B_mask_fixed_atomic_grid']['threshold_ship_hours']]
                                     for row in result['by_h']]}, ensure_ascii=False))


if __name__ == '__main__':
    main()
