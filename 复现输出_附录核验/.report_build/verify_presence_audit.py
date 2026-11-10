"""Independent checks of a fixed-mask, removal-stability presence audit.

This audits missingness constraints BEFORE any reversal target is imposed.
The mask is held fixed. A special all-zero configuration does not count as
passing: selectively removing leakage while retaining other leakage is tested.
This is a diagnostic use of downward closure, not a claim of a new theorem or
of identification of the true reception mechanism.
"""
from fractions import Fraction as F
from math import comb
from pathlib import Path
import json

ROOT = Path(__file__).resolve().parent


def vectors_at_most(budget, size):
    if size == 0:
        yield ()
        return
    for value in range(budget + 1):
        for tail in vectors_at_most(budget - value, size - 1):
            yield (value,) + tail


def model_a(v):
    return not any(v) or all(x >= 1 and int(x) == x for x in v)


def model_b(v):
    return all(x >= 0 and int(x) == x for x in v)


def erase(v, cells):
    return tuple(0 if i in cells else value for i, value in enumerate(v))


def original_mask_checks():
    rows = []
    for h in (F(1), F(1, 2), F(1, 4)):
        # Fixed physical mask W+E over [1,3), independent of h.
        bins = int(F(2) / h)
        v = (1,) * (2 * bins)  # integer numbers of missing full-h ship units
        w_cells = set(range(0, len(v), 2))
        e_cells = set(range(1, len(v), 2))
        reduced = erase(v, w_cells)
        assert model_a(v) and not model_a(reduced) and model_b(reduced)
        # An E-cell remains positive. The special all-zero exception is irrelevant.
        assert sum(reduced) > 0
        rows.append({
            'h_hours': str(h),
            'mask_cell_count': len(v),
            'fixed_mask_hours': '[1,3)',
            'A_nonzero_minimum_ship_hours': str(h * len(v)),
            'A_W_region_minimum_with_positive_E_anchor_ship_hours': str(h * len(w_cells)),
            'B_W_region_minimum_with_positive_E_anchor_ship_hours': '0',
            'whole_W_region_removal_preserves_A': False,
            'whole_W_region_removal_preserves_B': True,
            'remaining_missing_ship_hours': str(h * sum(reduced)),
        })
    return rows


def new_three_region_example():
    # Time-major order: L0,C0,R0,L1,C1,R1; both bins are in period 1.
    # Period 2 has no allowed missing activity for either model.
    observed_first = ((2, 0, 2), (2, 0, 2))
    observed_second = ((2, 0, 3), (2, 0, 3))
    truth = ((2, 0, 3),) * 4
    actual_hidden = (0, 0, 1, 0, 0, 1)
    y1, y2 = sum(map(sum, observed_first)), sum(map(sum, observed_second))
    assert (y1, y2) == (8, 10)
    assert sum(actual_hidden) == 2
    assert sum(map(sum, truth[:2])) == sum(map(sum, truth[2:])) == 10

    all_vectors = list(vectors_at_most(6, 6))
    assert len(all_vectors) == comb(12, 6) == 924
    stats = {}
    anchor = 2  # R in first hour
    centre = {1, 4}
    for name, legal in [('A', model_a), ('B', model_b)]:
        allowed = [v for v in all_vectors if legal(v)]
        # The target is applied only here, separately from the presence audit.
        reversing = [v for v in allowed if y1 + sum(v) >= y2]
        best = min(map(sum, reversing))
        optima = [v for v in reversing if sum(v) == best]
        anchored = [v for v in allowed if v[anchor] >= 1]
        forced_c = min(sum(v[i] for i in centre) for v in anchored)
        audit_tests = audit_failures = 0
        # Entire-coordinate deletion stays on the same integer lattice.
        # For B, general downward closure follows analytically from its sole
        # nonnegativity rule. These finite tests corroborate, rather than prove,
        # that property for an arbitrary model.
        for v in allowed:
            for cell, value in enumerate(v):
                if value:
                    audit_tests += 1
                    audit_failures += not legal(erase(v, {cell}))
        stats[name] = {
            'legal_vectors_in_certified_search_range': len(allowed),
            'target_satisfying_vectors': len(reversing),
            'minimum_ship_hours': best,
            'optimal_count': len(optima),
            'all_optima': optima,
            'anchor': 'R in first hour has at least 1 missing ship-hour',
            'minimum_C_ship_hours_under_anchor': forced_c,
            'removal_tests_without_target_condition': audit_tests,
            'failed_removal_tests_without_target_condition': audit_failures,
        }
    witness = (1,) * 6
    reduced = erase(witness, centre)
    assert model_a(witness) and model_b(witness)
    assert not model_a(reduced) and model_b(reduced) and sum(reduced) == 4
    assert stats['A']['minimum_ship_hours'] == 6
    assert stats['B']['minimum_ship_hours'] == 2
    assert [stats[n]['optimal_count'] for n in ('A', 'B')] == [1, 21]
    assert [stats[n]['legal_vectors_in_certified_search_range'] for n in ('A', 'B')] == [2, 924]
    assert [stats[n]['target_satisfying_vectors'] for n in ('A', 'B')] == [1, 917]
    assert [stats[n]['minimum_C_ship_hours_under_anchor'] for n in ('A', 'B')] == [2, 0]
    assert stats['A']['failed_removal_tests_without_target_condition'] == 6
    assert stats['B']['failed_removal_tests_without_target_condition'] == 0
    return {
        'mask': 'L,C,R x period 1, both 1-hour bins; fixed, not reselected',
        'physical_meaning': 'region where partial reception impairment may occur; not a total AIS blackout',
        'observed_period_totals_ship_hours': [y1, y2],
        'true_period_totals_ship_hours': [10, 10],
        'true_C_activity_ship_hours': 0,
        'truth_not_given_to_optimizer': True,
        'counterexample_target': 'first-period true total at least second-period true total',
        'fixed_mask_variable_order': ['L0', 'C0', 'R0', 'L1', 'C1', 'R1'],
        'enumerated_vectors': len(all_vectors),
        'search_cutoff_from_feasible_A_witness_ship_hours': 6,
        'actual_hidden_witness': actual_hidden,
        'audit_start_witness': witness,
        'audit_after_C_deletion': reduced,
        'audit_after_C_deletion_still_nonzero': True,
        'models': stats,
    }


def additional_total_growth_check():
    # Independent alternative: two periods, two regions, observations 7 -> 10.
    # Fixed mask covers all four cells. Unit = 1 ship-hour for both models.
    observed = (5, 2, 4, 6)
    vecs = list(vectors_at_most(7, 4))
    assert len(vecs) == comb(11, 4)
    thresholds = {}
    for name, legal in [('A', model_a), ('B', model_b)]:
        feasible = [v for v in vecs if legal(v)
                    and observed[0] + observed[1] + v[0] + v[1]
                    >= observed[2] + observed[3] + v[2] + v[3]]
        thresholds[name] = min(map(sum, feasible))
    assert thresholds == {'A': 7, 'B': 3}
    return {'observed_W1_E1_W2_E2': observed,
            'threshold_ship_hours': thresholds,
            'A_forced_second_period_ship_hours': 2}


def main():
    result = {
        'audit_scope': 'fixed mask; prior mechanism constraints only; no target condition; no mask reselection',
        'interpretation': 'failure exposes a mandatory missing-activity condition, not proof that a mechanism is false',
        'deletion_precision': 'whole cells/regions are erased, so both models share the same admissible precision',
        'all_zero_exception_handled_by': 'retaining positive leakage elsewhere, and a positive anchor outside the probe region',
        'original_two_region_fixed_physical_mask': original_mask_checks(),
        'new_three_region_total_activity_example': new_three_region_example(),
        'internal_second_example': additional_total_growth_check(),
    }
    dest = ROOT / 'verify_presence_audit_results.json'
    dest.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({'verified': True,
                      'new_example_thresholds': {k: v['minimum_ship_hours'] for k, v in result['new_three_region_total_activity_example']['models'].items()},
                      'new_example_C_lower_bounds': {k: v['minimum_C_ship_hours_under_anchor'] for k, v in result['new_three_region_total_activity_example']['models'].items()},
                      'enumerated': result['new_three_region_total_activity_example']['enumerated_vectors']}, ensure_ascii=False))


if __name__ == '__main__':
    main()
