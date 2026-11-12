import hashlib

import numpy as np

from src.constants.species import SPECIES
from .bootstrap import _validate_seed, _validate_repetitions
from .diversity import indices
from .fingerprint import paired_fingerprint
from .rarefaction import expected_species, valid_counts

PAIR_STATUS = {
 'eligible': '共同量比较',
 'missing_spring': '春季缺期',
 'missing_autumn': '秋季缺期',
 'empty': '空样线',
 'insufficient': '采样量不足',
}


def _survey_meta(survey):
 date = survey.get('survey_date')
 return {
  'id': survey['id'],
  'name': survey['name'],
  'survey_date': date.isoformat() if hasattr(date, 'isoformat') else date,
  'filename': survey.get('filename', ''),
 }


def _side(t, counts, survey_id, m, include_rarefied):
 a = valid_counts(counts)
 n = int(a.sum())
 if n:
  desc = indices(a)
  observed, shannon, simpson = desc['observed_species'], desc['shannon'], desc['simpson']
 else:
  observed, shannon, simpson = 0, None, None
 return {
  'id': t['id'],
  'survey_id': survey_id,
  'reference': t['reference'],
  'name': t.get('name', ''),
  'habitat': t.get('habitat', ''),
  'n': n,
  'observed_species': observed,
  'shannon': shannon,
  'simpson': simpson,
  'rarefied': expected_species(a, m) if include_rarefied else None,
 }


def _quantile(values):
 return np.quantile(values, [.025, .975]).tolist()


def _paired_bootstrap(counts_spring, counts_autumn, m, repetitions, seed, key):
 """Independent multinomial resampling for each side of one pair.

 The sub-seed depends only on the configured seed and the stable survey/reference
 key, never on input row order or on the number of other pairs in the run.
 """
 s = valid_counts(counts_spring)
 a = valid_counts(counts_autumn)
 ns, na = int(s.sum()), int(a.sum())
 if not ns or not na:
  raise ValueError('空群落不可bootstrap')
 _validate_repetitions(repetitions)
 _validate_seed(seed)
 expected_species(s, m)
 expected_species(a, m)
 key_seed = int.from_bytes(hashlib.sha256(key.encode()).digest()[:4], 'big')
 rng = np.random.default_rng(np.random.SeedSequence([seed, key_seed]))
 spring_reps = rng.multinomial(ns, s / ns, size=repetitions)
 autumn_reps = rng.multinomial(na, a / na, size=repetitions)
 spring_e = np.asarray([expected_species(row, m) for row in spring_reps])
 autumn_e = np.asarray([expected_species(row, m) for row in autumn_reps])
 delta = autumn_e - spring_e
 return {
  'spring_reps': spring_e,
  'autumn_reps': autumn_e,
  'delta_reps': delta,
  'spring_ci': _quantile(spring_e),
  'autumn_ci': _quantile(autumn_e),
  'delta_ci': _quantile(delta),
 }


def analyze_paired(spring, autumn, spring_transects, autumn_transects, config):
 """Compare the same physical transects across two survey periods.

 Pairing identity is Transect.reference. Every reference in the union is
 materialised in the report; missing, empty and under-sampled pairs are kept
 with an explicit reason instead of being dropped from the input.
 """
 if spring['id'] == autumn['id']:
  raise ValueError('春、秋比较必须选择两个不同调查期')
 m = config.get('m')
 repetitions = config.get('bootstrap')
 seed = config.get('seed')
 if not isinstance(m, (int, np.integer)) or m < 0:
  raise ValueError('共同稀释量m必须是非负整数')
 _validate_repetitions(repetitions)
 _validate_seed(seed)

 def by_reference(transects, survey_id, label):
  if len({t['reference'] for t in transects}) != len(transects):
   raise ValueError(f'{label}存在重复样线编号，无法唯一配对')
  if any(t['survey_id'] != survey_id for t in transects):
   raise ValueError(f'{label}样线不属于所选调查期')
  return {t['reference']: t for t in transects}

 spring_map = by_reference(spring_transects, spring['id'], '春季')
 autumn_map = by_reference(autumn_transects, autumn['id'], '秋季')
 references = sorted(set(spring_map) | set(autumn_map))
 if not references:
  raise ValueError('两个调查期都没有样线记录，无法配对')

 vectors = {}
 for ref in references:
  for label, mapping in (('春季', spring_map), ('秋季', autumn_map)):
   if ref not in mapping:
    continue
   t = mapping[ref]
   if not set(t['counts']) <= set(SPECIES):
    raise ValueError(f'{label}样线{ref}包含未知物种')
   vectors[(label, ref)] = valid_counts([t['counts'].get(s, 0) for s in SPECIES])

 both_nonempty = [
  ref for ref in references
  if ref in spring_map and ref in autumn_map
  and vectors[('春季', ref)].sum() > 0 and vectors[('秋季', ref)].sum() > 0
 ]
 common_limit = min(
  (min(int(vectors[('春季', ref)].sum()), int(vectors[('秋季', ref)].sum())) for ref in both_nonempty),
  default=0,
 )

 pairs = []
 bootstrap_arrays = []
 point_deltas = []
 for ref in references:
  in_spring, in_autumn = ref in spring_map, ref in autumn_map
  ns = int(vectors[('春季', ref)].sum()) if in_spring else 0
  na = int(vectors[('秋季', ref)].sum()) if in_autumn else 0
  spring_side = _side(spring_map[ref], vectors[('春季', ref)], spring['id'], m, False) if in_spring else None
  autumn_side = _side(autumn_map[ref], vectors[('秋季', ref)], autumn['id'], m, False) if in_autumn else None
  base = {
   'reference': ref,
   'spring': spring_side,
   'autumn': autumn_side,
   'delta': None,
   'delta_ci': None,
   'spring_ci': None,
   'autumn_ci': None,
  }
  if not in_spring:
   pairs.append({**base, 'status': 'missing_spring', 'reason': '秋季有记录、春季缺期；编号未配对，不进入比较'})
   continue
  if not in_autumn:
   pairs.append({**base, 'status': 'missing_autumn', 'reason': '春季有记录、秋季缺期；编号未配对，不进入比较'})
   continue
  empty_sides = ('春季' if ns == 0 else '') + ('、' if ns == 0 and na == 0 else '') + ('秋季' if na == 0 else '')
  if ns == 0 or na == 0:
   pairs.append({**base, 'status': 'empty', 'reason': f'{empty_sides}N=0为空样线；稀释期望不定义，不当作低多样性，不进入比较'})
   continue
  short = []
  if ns < m:
   short.append(f'春季N={ns}<m={m}')
  if na < m:
   short.append(f'秋季N={na}<m={m}')
  if short:
   pairs.append({**base, 'status': 'insufficient', 'reason': '；'.join(short) + '；保留在配对明细中，不静默删除，不进入比较'})
   continue

  spring_side['rarefied'] = expected_species(vectors[('春季', ref)], m)
  autumn_side['rarefied'] = expected_species(vectors[('秋季', ref)], m)
  boot = _paired_bootstrap(
   vectors[('春季', ref)], vectors[('秋季', ref)], m, repetitions, seed,
   f'paired/{spring["id"]}/{autumn["id"]}/{ref}',
  )
  delta = float(autumn_side['rarefied'] - spring_side['rarefied'])
  point_deltas.append(delta)
  bootstrap_arrays.append(boot['delta_reps'])
  pairs.append({
   **base,
   'status': 'eligible',
   'reason': '',
   'delta': delta,
   'delta_ci': boot['delta_ci'],
   'spring_ci': boot['spring_ci'],
   'autumn_ci': boot['autumn_ci'],
  })

 eligible = sum(p['status'] == 'eligible' for p in pairs)
 missing = sum(p['status'] in ('missing_spring', 'missing_autumn') for p in pairs)
 empty = sum(p['status'] == 'empty' for p in pairs)
 insufficient = sum(p['status'] == 'insufficient' for p in pairs)

 overall = None
 if eligible:
  reps = np.mean(np.vstack(bootstrap_arrays), axis=0)
  overall = {
   'pairs': eligible,
   'mean_delta': float(np.mean(point_deltas)),
   'median_delta': float(np.median(point_deltas)),
   'min_delta': float(np.min(point_deltas)),
   'max_delta': float(np.max(point_deltas)),
   'mean_delta_ci': _quantile(reps),
  }

 definitions = {
  'pairing': 'Transect.reference is the physical-transect identity; a pair exists only when the same reference has a record in both survey periods.',
  'rarefaction': 'E[S_m]=sum_i(1-C(N-n_i,m)/C(N,m)), individual-based without replacement; computed separately for spring and autumn at the same m.',
  'delta': 'Delta_pair = E_autumn[S_m] - E_spring[S_m]; m is fixed by the run and does not vary with either period N.',
  'bootstrap': 'Each side is independently resampled as Multinomial(N, observed p); both sides recompute E[S_m] at the same m and are subtracted. Percentile 95% interval.',
  'overall': 'Arithmetic mean of eligible pair deltas; its interval averages the paired bootstrap replicate deltas across pairs.',
 }
 assumptions = [
  'Only references with a non-empty record in both periods enter comparison; pairing is by reference, not by row order or transect name.',
  'Spring and autumn N may differ; rarefaction makes them comparable only at the same m, and both sides must satisfy N>=m.',
  'Missing period, empty transect and insufficient sampling are separate exclusion categories and remain listed with reasons; under-sampled pairs are never silently removed.',
  'Bootstrap is conditional on each observed composition and treats the two periods as independent samples; it does not cover unseen species, spatial dependence, detection misses or full field-sampling uncertainty.',
  'A fixed seed plus the stable pair/survey key derives each pair sub-seed, so row order and other pair additions do not change an existing pair result.',
  'Observational differences and intervals do not establish causal effects of conservation actions.',
 ]
 return {
  'mode': 'paired',
  'fingerprint': paired_fingerprint(spring, autumn, spring_transects, autumn_transects, config),
  'spring_survey': _survey_meta(spring),
  'autumn_survey': _survey_meta(autumn),
  'm': int(m),
  'bootstrap': int(repetitions),
  'seed': int(seed),
  'common_limit': int(common_limit),
  'm_exceeds_common_limit': bool(both_nonempty and m > common_limit),
  'total_references': len(pairs),
  'eligible': eligible,
  'missing': missing,
  'empty': empty,
  'insufficient': insufficient,
  'excluded_total': missing + empty + insufficient,
  'pairs': pairs,
  # Compatibility counters for list/run-table consumers.
  'excluded_empty': empty,
  'overall': overall,
  'definitions': definitions,
  'assumptions': assumptions,
  'interpretation': 'Compare the autumn-minus-spring rarefied expectation only at the run common m; excluded pairs are reported, not dropped. Observational differences do not establish conservation causality.',
 }


PAIRED_HEADERS = [
 '研究编号', '研究名称', '比较模式', '春季调查期', '秋季调查期', '共同m', 'bootstrap次数', 'seed',
 '输入指纹', '统计假设', '编号', '配对状态', '排除原因',
 '春季样线ID', '春季名称', '春季N', '春季原始S', '春季E[S_m]', '春季E[S_m]区间下限', '春季E[S_m]区间上限',
 '秋季样线ID', '秋季名称', '秋季N', '秋季原始S', '秋季E[S_m]', '秋季E[S_m]区间下限', '秋季E[S_m]区间上限',
 '差值(秋-春)', '差值区间下限', '差值区间上限',
 '总体平均差值', '总体平均区间下限', '总体平均区间上限',
 '有效配对总数', '缺期总数', '空线总数', '不足总数', '算法',
]


def _obj(run, key):
 return run[key] if isinstance(run, dict) else getattr(run, key)


def paired_csv(run):
 result = _obj(run, 'result')
 if result.get('mode') != 'paired':
  raise ValueError('只有春秋配对研究可导出该CSV')
 spring = result['spring_survey']
 autumn = result['autumn_survey']
 overall = result.get('overall') or {}
 assumptions = ' | '.join(result.get('assumptions', []))
 rows = []
 for pair in result['pairs']:
  side_s = pair.get('spring') or {}
  side_a = pair.get('autumn') or {}
  pair_ci = pair.get('delta_ci') or [None, None]
  spring_ci = pair.get('spring_ci') or [None, None]
  autumn_ci = pair.get('autumn_ci') or [None, None]
  overall_ci = overall.get('mean_delta_ci') or [None, None]
  rows.append([
   _obj(run, 'id'), _obj(run, 'name'), '春秋配对稀释期望差',
   spring.get('name', ''), autumn.get('name', ''), result['m'], result['bootstrap'], result['seed'],
   result.get('fingerprint', ''), assumptions,
   pair['reference'], PAIR_STATUS[pair['status']], pair.get('reason', ''),
   side_s.get('id', ''), side_s.get('name', ''), side_s.get('n', ''), side_s.get('observed_species', ''),
   side_s.get('rarefied', ''), spring_ci[0] if spring_ci[0] is not None else '',
   spring_ci[1] if spring_ci[1] is not None else '',
   side_a.get('id', ''), side_a.get('name', ''), side_a.get('n', ''), side_a.get('observed_species', ''),
   side_a.get('rarefied', ''), autumn_ci[0] if autumn_ci[0] is not None else '',
   autumn_ci[1] if autumn_ci[1] is not None else '',
   pair.get('delta', '') if pair.get('delta') is not None else '',
   pair_ci[0] if pair_ci[0] is not None else '', pair_ci[1] if pair_ci[1] is not None else '',
   overall.get('mean_delta', ''), overall_ci[0] if overall_ci[0] is not None else '',
   overall_ci[1] if overall_ci[1] is not None else '',
   result['eligible'], result['missing'], result['empty'], result['insufficient'],
   'paired-rarefaction-multinomial-v1',
  ])
 return PAIRED_HEADERS, rows
