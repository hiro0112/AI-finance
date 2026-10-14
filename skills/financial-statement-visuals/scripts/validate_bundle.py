#!/usr/bin/env python3
"""Validate legacy/v2 financial JSON offline; never evaluate formulas or mutate data."""
import argparse
from datetime import date, datetime
import json
from pathlib import Path
import validate_data


def text(value):
    return isinstance(value, str) and bool(value.strip())


def iso_date(value):
    try:
        return date.fromisoformat(value) if isinstance(value, str) else None
    except ValueError:
        return None


def validate(data):
    if not isinstance(data, dict):
        return ['root must be an object'], []
    if 'schema_version' not in data:
        try:
            return validate_data.validate(data)
        except (TypeError, ValueError, AttributeError):
            return ['invalid legacy data structure'], []
    if type(data['schema_version']) is not int or data['schema_version'] != 2:
        return ['unsupported schema_version; expected 2 or legacy without version'], []
    errors, checks = [], []

    def require_strings(obj, keys, where):
        for key in keys:
            if not text(obj.get(key)):
                errors.append(f'{where}: missing/invalid {key}')

    def notes(obj, where):
        if not isinstance(obj.get('notes'), list):
            errors.append(f'{where}: notes must be a list')

    def provenance(p, sources, where):
        if not isinstance(p, dict):
            errors.append(f'{where}: provenance must be an object')
            return
        sid = p.get('source')
        if not text(sid) or sid not in sources or p.get('kind') not in ('reported', 'provided', 'derived'):
            errors.append(f'{where}: provenance needs valid source and kind')
        if p.get('kind') == 'derived' and not text(p.get('formula')):
            errors.append(f'{where}: derived provenance needs formula')

    def rows(items, sources, where, metric=False, market=False):
        if not isinstance(items, list):
            errors.append(f'{where}: must be a list')
            return
        if not items and not where.endswith('/growth_metrics'):
            checks.append(f'{where}: MISSING rows; completeness requires review')
        seen = set()
        for i, r in enumerate(items):
            loc = f'{where}[{i}]'
            if not isinstance(r, dict):
                errors.append(f'{loc}: row must be an object')
                continue
            require_strings(r, ('id', 'label', 'unit'), loc)
            rid = r.get('id')
            if text(rid):
                if rid in seen:
                    errors.append(f'{loc}: duplicate row id {rid}')
                seen.add(rid)
            status = r.get('status')
            if status not in ('ok', 'missing', 'not_applicable', 'not_meaningful'):
                errors.append(f'{loc}: invalid status')
            if status == 'ok':
                if not validate_data.number(r.get('value')):
                    errors.append(f'{loc}: ok value must be finite numeric')
                provenance(r.get('provenance'), sources, loc)
            else:
                if r.get('value') is not None or 'value' not in r or not text(r.get('reason')):
                    errors.append(f'{loc}: non-ok value must be null with reason')
                checks.append(f'{loc}: MISSING/non-ok {rid}; {r.get("reason", "no reason")}')
            if metric:
                require_strings(r, ('category', 'definition'), loc)
                p = r.get('provenance')
                if status == 'ok' and isinstance(p, dict) and p.get('kind') == 'derived':
                    require_strings(r, ('formula',), loc)
                    if not isinstance(r.get('inputs'), list) or not r['inputs'] or not all(text(v) for v in r['inputs']):
                        errors.append(f'{loc}: derived metric needs nonempty inputs')
                if market:
                    basis = r.get('basis')
                    if not isinstance(basis, dict) or not basis or not all(text(v) for v in basis.values()):
                        errors.append(f'{loc}: market metric needs basis metadata')
                    elif 'price_date' in basis and not iso_date(basis['price_date']):
                        errors.append(f'{loc}: invalid basis price_date')
            else:
                require_strings(r, ('original_label',), loc)
                if type(r.get('level')) is not int or r['level'] < 0:
                    errors.append(f'{loc}: level must be a nonnegative integer')

    require_strings(data, ('dataset_id', 'generated_at'), 'bundle')
    try:
        stamp = data.get('generated_at')
        if not text(stamp) or 'T' not in stamp:
            raise ValueError()
        datetime.fromisoformat(stamp.replace('Z', '+00:00'))
    except (ValueError, TypeError):
        errors.append('bundle: invalid ISO generated_at')
    if data.get('input_mode') not in ('external', 'finance-valuation'):
        errors.append('bundle: invalid input_mode')
    if not isinstance(data.get('input_files'), list) or not all(text(p) for p in data['input_files']):
        errors.append('bundle: input_files must be a list of paths')
    outputs = data.get('outputs')
    if not isinstance(outputs, dict) or not outputs:
        errors.append('bundle: outputs must be a nonempty object')
    else:
        for kind, filename in outputs.items():
            if kind not in ('boxes', 'sankey', 'strac', 'dashboard') or not text(filename) or '/' in filename or '\\' in filename or not filename.endswith('.html'):
                errors.append(f'bundle: invalid output {kind}')
        # Figure kinds may share one self-contained HTML. The management dashboard may embed
        # the BS/PL box figure (standard since 2026-09-30), but not the sankey or STRAC figures.
        dashboard_name = outputs.get('dashboard')
        if text(dashboard_name) and any(outputs.get(k) == dashboard_name for k in ('sankey', 'strac')):
            errors.append('bundle: dashboard must use a separate output filename')
    companies = data.get('companies')
    if not isinstance(companies, list) or not companies:
        errors.append('companies must be a nonempty list')
        return errors, checks
    seen_companies = set()
    for ci, c in enumerate(companies):
        loc = f'company[{ci}]'
        if not isinstance(c, dict):
            errors.append(f'{loc}: must be an object')
            continue
        require_strings(c, ('id', 'name', 'scope', 'accounting_standard', 'currency', 'unit', 'default_period'), loc)
        cid = c.get('id') if text(c.get('id')) else loc
        if cid in seen_companies:
            errors.append(f'{cid}: duplicate company id')
        seen_companies.add(cid)
        notes(c, cid)
        sources = c.get('sources')
        if not isinstance(sources, dict) or not sources:
            errors.append(f'{cid}: sources must be a nonempty object')
            sources = {}
        for sid, src in sources.items():
            if not isinstance(src, dict):
                errors.append(f'{cid}/{sid}: source must be an object')
                continue
            require_strings(src, ('title',) if src.get('type') == 'provided' else ('title', 'url', 'published', 'pages'), f'{cid}/{sid}')
        periods = c.get('periods')
        if not isinstance(periods, list) or not periods:
            errors.append(f'{cid}: periods must be a nonempty list')
            periods = []
        supporting = c.get('supporting_periods', [])
        if not isinstance(supporting, list):
            errors.append(f'{cid}: supporting_periods must be a list')
            supporting = []
        ids, ordered, dated_periods = set(), [], {}
        for pi, p in enumerate(periods + supporting):
            ploc = f'{cid}/period[{pi}]'
            if not isinstance(p, dict):
                errors.append(f'{ploc}: must be an object')
                continue
            require_strings(p, ('id', 'label'), ploc)
            pid = p.get('id') if text(p.get('id')) else f'period[{pi}]'
            ploc = f'{cid}/{pid}'
            if pid in ids:
                errors.append(f'{ploc}: duplicate period id')
            ids.add(pid)
            notes(p, ploc)
            period = p.get('period')
            if not isinstance(period, dict):
                errors.append(f'{ploc}: period must be an object')
                period = {}
            dates = [iso_date(period.get(k)) for k in ('start', 'end', 'bs_date')]
            if not all(dates) or (all(dates) and (dates[0] > dates[1] or dates[1] != dates[2])):
                errors.append(f'{ploc}: invalid period dates/order/bs_date')
            else:
                dated_periods[pid] = dates[1]
                if pi < len(periods):
                    ordered.append((dates[1], pid))
            if not isinstance(p.get('statements'), dict):
                errors.append(f'{ploc}: statements must contain PL, BS, CF')
            else:
                for statement in ('PL', 'BS', 'CF'):
                    rows(p['statements'].get(statement), sources, f'{ploc}/{statement}')
            rows(p.get('metrics'), sources, f'{ploc}/metrics', metric=True)
            # Preserve original company metadata but pass exactly this period's values.
            flat = {k: c.get(k) for k in ('name', 'scope', 'accounting_standard', 'currency', 'unit')}
            flat.update(id=ploc, sources=sources)
            flat.update({k: p.get(k) for k in ('period', 'values', 'provenance', 'rounding')})
            # Guard malformed provenance sources before calling the legacy validator.
            pv = flat.get('provenance')
            if isinstance(pv, dict):
                for key, item in pv.items():
                    if isinstance(item, dict) and not text(item.get('source')):
                        errors.append(f'{ploc}/{key}: invalid provenance source')
            try:
                old_errors, old_checks = validate_data.validate({'companies': [flat]})
                errors.extend(old_errors); checks.extend(old_checks)
            except (TypeError, ValueError, AttributeError):
                errors.append(f'{ploc}: invalid aggregate structure')
        if ordered:
            if ordered != sorted(ordered, key=lambda x: x[0]):
                errors.append(f'{cid}: periods must be oldest first')
            if c.get('default_period') != max(ordered, key=lambda x: x[0])[1]:
                errors.append(f'{cid}: default_period must be latest display period')
        if 'growth_metrics' in c:
            rows(c['growth_metrics'], sources, f'{cid}/growth_metrics', metric=True)
            if isinstance(c['growth_metrics'], list):
                for r in c['growth_metrics']:
                    if isinstance(r, dict) and any(k in r for k in ('from_period', 'to_period', 'intervals')):
                        if not text(r.get('from_period')) or not text(r.get('to_period')) or r.get('from_period') not in ids or r.get('to_period') not in ids or type(r.get('intervals')) is not int or r['intervals'] <= 0:
                            errors.append(f'{cid}: invalid growth period metadata')
                        elif r['from_period'] in dated_periods and r['to_period'] in dated_periods:
                            distance = dated_periods[r['to_period']].year - dated_periods[r['from_period']].year
                            if distance != r['intervals']:
                                errors.append(f'{cid}: growth intervals do not match fiscal year distance')
        if 'market' in c:
            market = c['market']
            if not isinstance(market, dict):
                errors.append(f'{cid}: market must be an object')
            else:
                if not iso_date(market.get('as_of')):
                    errors.append(f'{cid}: market needs ISO as_of date')
                notes(market, f'{cid}/market')
                rows(market.get('metrics'), sources, f'{cid}/market', metric=True, market=True)
        elif isinstance(outputs, dict) and 'dashboard' in outputs:
            checks.append(f'{cid}: MISSING market; dashboard coverage requires review')
    checks.append('REVIEW: source accuracy, full statement/metric coverage, formula results, market basis semantics and rendering require human review; formulas are not evaluated.')
    return errors, checks


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('data', type=Path)
    args = parser.parse_args()
    try:
        errors, checks = validate(json.loads(args.data.read_text(encoding='utf-8')))
    except (OSError, ValueError) as exc:
        parser.exit(2, str(exc) + '\n')
    for check in checks:
        print(check)
    for error in errors:
        print('ERROR ' + error)
    incomplete = sum('MISSING' in c or 'SKIP ' in c for c in checks)
    print(f'{len(errors)} error(s); {incomplete} missing/skipped check(s). Zero errors does not establish data completeness. Source accuracy, formulas and rendering need separate review.')
    return 1 if errors else 0


if __name__ == '__main__':
    raise SystemExit(main())
