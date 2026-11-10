"""Independent exhaustive verification of the 2-region, 4-period toy model.

No cohort size, per-period capacity, per-cell cap, or detection probabilities
are imposed. Six is an incumbent objective value, not an activity assumption:
adding three eastern observations in each of the first two periods gives a
one-block counterexample. Therefore enumerating every nonnegative integer
allocation of total mass <= 6 proves the global minima of all models below.

A positive-support block is a spatial interval times a temporal interval;
every cell in it must have strictly positive added mass. Two blocks must be
cell-disjoint. We count allocations, not alternative decompositions into blocks.
"""

from collections import Counter
from fractions import Fraction
from itertools import combinations
import json
from math import comb


OBSERVED = ((2, 1), (2, 1), (1, 2), (1, 2))  # (W, E) by period
SEARCH_CUTOFF = 6


def compositions(total, length):
    if length == 1:
        yield (total,)
        return
    for first in range(total + 1):
        for rest in compositions(total - first, length - 1):
            yield (first,) + rest


def rectangular_supports(min_duration):
    masks = set()
    for spatial_start in range(2):
        for spatial_end in range(spatial_start, 2):
            for temporal_start in range(4):
                for temporal_end in range(temporal_start + min_duration - 1, 4):
                    masks.add(sum(
                        1 << (2 * t + s)
                        for t in range(temporal_start, temporal_end + 1)
                        for s in range(spatial_start, spatial_end + 1)
                    ))
    return masks


def at_most_two_supports(single_supports):
    # Includes no block and one block. Cell-disjoint blocks may touch.
    masks = set(single_supports) | {0}
    for a, b in combinations(single_supports, 2):
        if a & b == 0:
            masks.add(a | b)
    return masks


def evaluate(vec):
    by_period = tuple(tuple(vec[2 * t:2 * t + 2]) for t in range(4))
    true = tuple(
        (OBSERVED[t][0] + by_period[t][0], OBSERVED[t][1] + by_period[t][1])
        for t in range(4)
    )
    w1, e1 = (sum(true[t][s] for t in (0, 1)) for s in range(2))
    w2, e2 = (sum(true[t][s] for t in (2, 3)) for s in range(2))
    # Positive observed totals guarantee nonzero denominators.
    delta = Fraction(e2, w2 + e2) - Fraction(e1, w1 + e1)
    mask = sum(1 << j for j, value in enumerate(vec) if value > 0)
    return {
        "mass": sum(vec),
        "support": mask,
        "counterexample": e2 * w1 <= e1 * w2,
        "delta": str(delta),
        "missing_by_period_WE": by_period,
        "true_month_counts_WE": ((w1, e1), (w2, e2)),
    }


def summarize(rows):
    bad = [r for r in rows if r["counterexample"]]
    optimum = min(r["mass"] for r in bad)
    best = [r for r in bad if r["mass"] == optimum]
    return {
        "legal_allocations_with_mass_at_most_6": len(rows),
        "counterexamples_with_mass_at_most_6": len(bad),
        "minimum_mass": optimum,
        "optimal_allocation_count": len(best),
        "legal_by_mass": dict(sorted(Counter(r["mass"] for r in rows).items())),
        "counterexamples_by_mass": dict(sorted(Counter(r["mass"] for r in bad).items())),
        "optimal_allocations": [
            {k: v for k, v in r.items() if k not in ("support", "counterexample")}
            for r in best
        ],
    }


def main():
    one1 = rectangular_supports(1)
    one2 = rectangular_supports(2)
    assert len(one1) == 30
    assert len(one2) == 18
    models = {
        "free": None,
        "exactly_one_block_min_duration_1": one1,
        "at_most_two_blocks_min_duration_1": at_most_two_supports(one1),
        "exactly_one_block_min_duration_2": one2,
        "at_most_two_blocks_min_duration_2": at_most_two_supports(one2),
    }
    # A feasible incumbent in every model; also obeys duration >= 2.
    incumbent = evaluate((0, 3, 0, 3, 0, 0, 0, 0))
    assert incumbent["counterexample"] and incumbent["mass"] == SEARCH_CUTOFF
    assert incumbent["support"] in one2

    rows = [
        evaluate(vec)
        for total in range(SEARCH_CUTOFF + 1)
        for vec in compositions(total, 8)
    ]
    assert len(rows) == comb(14, 8) == 3003
    results = {}
    for name, allowed_supports in models.items():
        selected = rows if allowed_supports is None else [
            r for r in rows if r["support"] in allowed_supports
        ]
        results[name] = summarize(selected)

    expected = {
        "free": (3003, 233, 4, 9),
        "exactly_one_block_min_duration_1": (355, 14, 6, 14),
        "at_most_two_blocks_min_duration_1": (2015, 189, 4, 9),
        "exactly_one_block_min_duration_2": (247, 10, 6, 10),
        "at_most_two_blocks_min_duration_2": (418, 39, 4, 1),
    }
    keys = (
        "legal_allocations_with_mass_at_most_6",
        "counterexamples_with_mass_at_most_6",
        "minimum_mass",
        "optimal_allocation_count",
    )
    for name, values in expected.items():
        assert tuple(results[name][k] for k in keys) == values

    print(json.dumps({
        "observed_by_period_WE": OBSERVED,
        "search_cutoff_from_feasible_incumbent": SEARCH_CUTOFF,
        "enumeration_size": len(rows),
        "note": "Exactly-one-block counts exclude the zero allocation; at-most-two counts include it.",
        "results": results,
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
