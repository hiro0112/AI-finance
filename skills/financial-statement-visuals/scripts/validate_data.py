#!/usr/bin/env python3
"""Validate shared financial-data.json; no network, rendering, or file mutation."""
import argparse
import json
import math
from pathlib import Path

RELATIONS = {
    'bs': {'assets': 1, 'liabilities': -1, 'equity': -1},
    'assets': {'assets': 1, 'current_assets': -1, 'noncurrent_assets': -1},
    'liabilities': {'liabilities': 1, 'current_liabilities': -1, 'noncurrent_liabilities': -1},
    'gross': {'revenue': 1, 'cost': -1, 'gross': -1},
    'operating': {'revenue': 1, 'cost': -1, 'sga': -1, 'other_operating_expense': -1, 'operating_income': -1},
    'net': {'pretax_income': 1, 'tax': -1, 'discontinued_income': 1, 'net_income': -1},
    'cf': {'opening_cash': 1, 'operating_cf': 1, 'investing_cf': 1, 'financing_cf': 1, 'fx_cf': 1, 'scope_cf': 1, 'closing_cash': -1},
}

def number(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)

def validate(data):
    errors, checks = [], []
    if not isinstance(data, dict) or not isinstance(data.get('companies'), list) or not data['companies']:
        return ['companies must be a nonempty list'], checks
    ids = set()
    for c in data['companies']:
        if not isinstance(c, dict):
            errors.append('company must be an object')
            continue
        cid = str(c.get('id', '?'))
        if cid in ids:
            errors.append(f'{cid}: duplicate company id')
        ids.add(cid)
        for key in ('id', 'name', 'scope', 'accounting_standard', 'currency', 'unit'):
            if not isinstance(c.get(key), str) or not c[key].strip():
                errors.append(f'{cid}: missing {key}')
        prov = c.get('provenance', {})
        prov = prov if isinstance(prov, dict) else {}
        source_dict = c.get('sources', {})
        source_dict = source_dict if isinstance(source_dict, dict) else {}
        provided_sources = {p.get('source') for p in prov.values() if isinstance(p, dict) and p.get('kind') == 'provided'} | {k for k, v in source_dict.items() if isinstance(v, dict) and v.get('type') == 'provided'}
        provided_only = bool(prov) and all(isinstance(p, dict) and p.get('source') in provided_sources for p in prov.values())
        period = c.get('period', {})
        if not isinstance(period, dict) or not all(period.get(k) for k in ('start', 'end', 'bs_date')):
            (checks if provided_only else errors).append(f'{cid}: incomplete period' + (' (user example; unspecified, not invented)' if provided_only else ''))
        values, provenance, sources, rounding = (c.get(k, {}) for k in ('values', 'provenance', 'sources', 'rounding'))
        if not all(isinstance(x, dict) for x in (values, provenance, sources, rounding)):
            errors.append(f'{cid}: values/provenance/sources/rounding must be objects')
            continue
        if not values:
            errors.append(f'{cid}: no values')
        for key, value in values.items():
            if value is None:
                checks.append(f'{cid}: MISSING {key}; confirm reason in notes')
                continue
            if not number(value):
                errors.append(f'{cid}: {key} must be finite numeric or null')
            p = provenance.get(key, {})
            if not isinstance(p, dict) or p.get('kind') not in ('reported', 'derived', 'provided') or p.get('source') not in sources:
                errors.append(f'{cid}: {key} needs provenance and valid source')
                continue
            src = sources[p['source']]
            required_source = ('title',) if p['source'] in provided_sources else ('title', 'url', 'published', 'pages')
            if not isinstance(src, dict) or not all(src.get(k) for k in required_source):
                errors.append(f'{cid}: {key} incomplete source metadata')
            if p['kind'] == 'derived' and not p.get('formula'):
                errors.append(f'{cid}: {key} derived value needs formula')
        for name, terms in RELATIONS.items():
            if not all(number(values.get(k)) for k in terms):
                checks.append(f'{cid}: SKIP {name} (missing/inapplicable values; not verified)')
                continue
            delta = sum(values[k] * factor for k, factor in terms.items())
            r = rounding.get(name)
            expected = 0
            if r is not None:
                if not isinstance(r, dict) or not number(r.get('delta')) or not r.get('reason'):
                    errors.append(f'{cid}: {name} invalid rounding record')
                    continue
                expected = r['delta']
            if not math.isclose(delta, expected, rel_tol=0, abs_tol=1e-8):
                errors.append(f'{cid}: {name} residual {delta:g}; declared {expected:g}')
            else:
                checks.append(f'{cid}: PASS {name}; residual {delta:g}' + (' (declared rounding; verify source)' if expected else ''))
        for name in rounding:
            if name not in RELATIONS:
                errors.append(f'{cid}: unknown rounding check {name}')
    return errors, checks

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('data', type=Path)
    args = parser.parse_args()
    try:
        errors, checks = validate(json.loads(args.data.read_text(encoding='utf-8')))
    except (ValueError, OSError) as exc:
        parser.exit(2, str(exc) + '\n')
    for check in checks:
        print(check)
    for error in errors:
        print('ERROR ' + error)
    print(f'{len(errors)} error(s). SKIP is not a passed check; source accuracy and rendering require separate review.')
    return bool(errors)

if __name__ == '__main__':
    raise SystemExit(main())
