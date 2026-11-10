"""固定可能受影响范围的删减检查与条件强制漏计下界。

仅标准库。审查模型本身，不将东移/增长被推翻条件放入合法性检查。
局部枚举盒 [0,2]^n 仅用于程序核验，不是活动容量假设。
对 A 的一个删减反例即足以否定向下闭；对 B 另有全域代数证明。
"""
from itertools import product
from fractions import Fraction
from math import comb
from pathlib import Path
import json

ROOT=Path(__file__).resolve().parent


def accepts(m, rule):
    if any(x<0 or int(x)!=x for x in m):
        return False
    if rule=='A':
        # 固定掩膜内每格至少 1；保留原模型的全零例外。
        return not any(m) or all(x>=1 for x in m)
    if rule=='B':
        return True
    if rule=='known_total_2':
        return sum(m)==2
    raise ValueError(rule)


def decrement_audit(n, rule, anchor, target):
    tested=0
    edges=0
    failures=[]
    floor=None
    floor_witness=None
    for m in product(range(3),repeat=n):
        tested+=1
        if not accepts(m,rule):
            continue
        if m[anchor]>=1:
            value=sum(m[i] for i in target)
            if floor is None or value<floor:
                floor=value
                floor_witness=m
        for i,x in enumerate(m):
            if x==0:
                continue
            edges+=1
            reduced=list(m)
            reduced[i]-=1
            if not accepts(reduced,rule):
                failures.append({'original':m,'deleted_index':i,'reduced':reduced})
    return {'box_vectors':tested,'unit_deletion_edges':edges,
            'failed_deletions':len(failures),'first_failure':failures[0] if failures else None,
            'anchor_index':anchor,'target_indices':target,
            'conditional_minimum_in_box':floor,'floor_witness':floor_witness,
            'scope':'finite box for implementation check; not a physical upper bound'}


def compositions(total,n):
    if n==1:
        yield (total,)
    else:
        for first in range(total+1):
            for tail in compositions(total-first,n-1):
                yield (first,)+tail


def new_growth_example():
    # 五艘静止船：L 两艘、C 无船、R 三艘；前期仅 R 第三艘隐藏。
    observed_early=((2,0,2),(2,0,2))
    observed_late=((2,0,3),(2,0,3))
    truth=((2,0,3),(2,0,3))
    observed_early_total=sum(map(sum,observed_early))
    observed_late_total=sum(map(sum,observed_late))
    result={r:{'legal':0,'counterexamples':0,'threshold':None,'optimal':[]} for r in ('A','B')}
    enumerated=0
    for budget in range(7):
        for missing in compositions(budget,6):
            enumerated+=1
            for rule,stats in result.items():
                if not accepts(missing,rule):
                    continue
                stats['legal']+=1
                # 后期不补，固定 S 只覆盖前期六格。
                no_increase=observed_late_total<=observed_early_total+sum(missing)
                if no_increase:
                    stats['counterexamples']+=1
                    if stats['threshold'] is None:
                        stats['threshold']=budget
                    if budget==stats['threshold']:
                        stats['optimal'].append(missing)
    assert enumerated==comb(12,6)==924
    assert result['A']['threshold']==6 and result['B']['threshold']==2
    assert len(result['A']['optimal'])==1 and len(result['B']['optimal'])==21
    true_missing=(0,0,1,0,0,1)
    assert not accepts(true_missing,'A') and accepts(true_missing,'B')
    assert 8+sum(true_missing)==10
    delete_center=(1,0,1,1,0,1)
    assert not accepts(delete_center,'A') and accepts(delete_center,'B')
    return {'observed_early':observed_early,'observed_late':observed_late,
            'truth_each_period':truth,'actual_hidden_early':true_missing,
            'S':'L,C,R x first two one-hour slots; fixed independently of missing support',
            'target':'later total <= earlier total', 'enumerated':enumerated,
            'models':result,'center_deleted_witness':delete_center}


def run():
    old={r:decrement_audit(4,r,anchor=1,target=(0,)) for r in ('A','B')}
    new={r:decrement_audit(6,r,anchor=2,target=(1,4)) for r in ('A','B')}
    assert old['A']['failed_deletions']==32 and old['B']['failed_deletions']==0
    assert old['A']['conditional_minimum_in_box']==1 and old['B']['conditional_minimum_in_box']==0
    assert new['A']['failed_deletions']==192 and new['B']['failed_deletions']==0
    assert new['A']['conditional_minimum_in_box']==2 and new['B']['conditional_minimum_in_box']==0
    control=decrement_audit(2,'known_total_2',anchor=0,target=(1,))
    assert control['failed_deletions']==4 and control['conditional_minimum_in_box']==0
    resolution_floors=[]
    for h in (Fraction(1),Fraction(1,2),Fraction(1,4)):
        n=int(2/h)
        # 固定 R=W×[1,2), H=E×[1,2)，相对跨期块[1,3)。
        target_indices=[2*k for k in range(int(1/h))]
        anchor_indices=[i+1 for i in target_indices]
        full=(1,)*(2*n)
        sparse=tuple(1 if i in anchor_indices else 0 for i in range(2*n))
        assert accepts(full,'A') and accepts(sparse,'B')
        assert sum(sparse[i] for i in anchor_indices)*h==1
        floor_A=sum(full[i] for i in target_indices)*h
        floor_B=sum(sparse[i] for i in target_indices)*h
        assert floor_A==1 and floor_B==0
        resolution_floors.append({'h_minutes':int(h*60),'A':int(floor_A),'B':int(floor_B)})
    output={'old_cross_period_mask_4_cells':old,'new_first_period_mask_6_cells':new,
            'new_growth_example':new_growth_example(),
            'applicability_control_known_total_2':control,
            'cross_resolution_fixed_region_floor_vessel_hours':resolution_floors,
            'cross_resolution_basis':'For R=W x [1,2), A has (1/h) cells, each >=h vessel-hours; B permits all zero while E x [1,2) retains >=1 vessel-hour.',
            'global_proofs':{'A':'m=ones legal, deleting one cell while another stays positive is illegal for n>=2',
                             'B':'nonnegative coordinate reductions retain support subset S and any upper budget bound'},
            'limitations':['Audit model feasibility, not the desired conclusion.',
                           'Keep S fixed; do not refit the mask after deletion.',
                           'Do not interpret failure as error when supported lower totals or coupling constraints are explicitly intended.',
                           'A finite successful search alone does not prove an unbounded model is downward closed.']}
    (ROOT/'AIS缺测模型_检查结果.json').write_text(json.dumps(output,ensure_ascii=False,indent=2),encoding='utf-8')
    summary={label:{r:{key:stats[key] for key in ('box_vectors','unit_deletion_edges','failed_deletions','conditional_minimum_in_box')}
                    for r,stats in block.items()} for label,block in (('old',old),('new',new))}
    summary['new_thresholds']={r:v['threshold'] for r,v in output['new_growth_example']['models'].items()}
    print(json.dumps(summary,ensure_ascii=False,indent=2))
    return output


if __name__=='__main__':
    run()
