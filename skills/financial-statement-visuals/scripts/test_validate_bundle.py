"""Behavior tests: historical checking, missingness, metadata, legacy compatibility."""
import copy
import importlib.util
import unittest
from pathlib import Path
import validate_data


def fixture():
    values = dict(assets=100, current_assets=40, noncurrent_assets=60,
                  liabilities=40, current_liabilities=20, noncurrent_liabilities=20,
                  equity=60, revenue=100, cost=50, gross=50, sga=20,
                  other_operating_expense=0, operating_income=30,
                  pretax_income=30, tax=10, discontinued_income=0, net_income=20,
                  opening_cash=10, operating_cf=20, investing_cf=-5,
                  financing_cf=-5, fx_cf=0, scope_cf=0, closing_cash=20)
    prov = {'source': 'S1', 'kind': 'reported'}
    metric = dict(id='margin', label='Margin', category='profitability', unit='ratio',
                  value=.3, status='ok', reason='', definition='Operating income / revenue',
                  formula='operating_income / revenue', inputs=['values.operating_income', 'values.revenue'],
                  provenance=dict(source='S1', kind='derived', formula='operating_income / revenue'))
    periods = []
    for y in range(2021, 2026):
        row = dict(id='total', label='Total', original_label='Total', level=0,
                   unit='USD million', value=100, status='ok', reason='', provenance=prov.copy())
        periods.append(dict(id=f'FY{y}', label=f'FY{y}', period=dict(start=f'{y}-01-01', end=f'{y}-12-31', bs_date=f'{y}-12-31'), values=values.copy(),
                            provenance={k: prov.copy() for k in values}, rounding={}, notes=[],
                            statements={k: [row.copy()] for k in ('PL', 'BS', 'CF')}, metrics=[copy.deepcopy(metric)]))
    company = dict(id='example', name='Example', scope='consolidated', accounting_standard='US GAAP', currency='USD', unit='million',
                   sources={'S1': dict(title='Provided annual report', url='/tmp/report.pdf', published='2026-01-01', pages='1-10')},
                   notes=[], default_period='FY2025', periods=periods, growth_metrics=[])
    return dict(schema_version=2, input_mode='finance-valuation', input_files=['/tmp/report.pdf'], dataset_id='test', generated_at='2026-01-02T00:00:00Z', outputs={'dashboard': 'dashboard.html'}, companies=[company])


class BundleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        path = Path(__file__).with_name('validate_bundle.py')
        cls.validator = None
        if path.exists():
            spec = importlib.util.spec_from_file_location('validate_bundle', path)
            cls.validator = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(cls.validator)

    def check(self, data):
        self.assertIsNotNone(self.validator, 'v2 bundle validation is not implemented')
        return self.validator.validate(data)

    def test_all_five_periods_are_checked(self):
        errors, checks = self.check(fixture())
        self.assertEqual(errors, [])
        self.assertEqual(sum('PASS bs;' in c for c in checks), 5)

    def test_figures_share_one_html_with_optional_separate_dashboard(self):
        d = fixture()
        d['outputs'] = {k: 'visuals.html' for k in ('boxes', 'sankey', 'strac')}
        self.assertEqual(self.check(d)[0], [])
        d['outputs']['dashboard'] = 'dashboard.html'
        self.assertEqual(self.check(d)[0], [])

    def test_explicit_split_figures_remain_supported(self):
        d = fixture()
        d['outputs'] = {k: k + '.html' for k in ('boxes', 'sankey', 'strac')}
        self.assertEqual(self.check(d)[0], [])

    def test_dashboard_may_embed_box_figure(self):
        d = fixture()
        d['outputs'] = {'boxes': 'dashboard.html', 'dashboard': 'dashboard.html'}
        self.assertEqual(self.check(d)[0], [])

    def test_management_cannot_overwrite_sankey_or_strac_html(self):
        for kind in ('sankey', 'strac'):
            d = fixture()
            d['outputs'] = {'boxes': 'dashboard.html', kind: 'dashboard.html', 'dashboard': 'dashboard.html'}
            self.assertTrue(any('separate output' in e for e in self.check(d)[0]), kind)

    def test_legacy_results_are_preserved(self):
        d = fixture(); c = d['companies'][0]; p = c['periods'][0]
        old = {'companies': [{**c, **{k: p[k] for k in ('period', 'values', 'provenance', 'rounding')}}]}
        self.assertEqual(self.check(old), validate_data.validate(old))

    def test_oldest_year_error_is_not_hidden_by_default(self):
        d = fixture(); d['companies'][0]['periods'][0]['values']['assets'] = 101
        errors, _ = self.check(d)
        self.assertTrue(any('FY2021' in e and 'residual' in e for e in errors))

    def test_missing_reason_is_required_and_missing_is_not_pass(self):
        d = fixture(); r = d['companies'][0]['periods'][0]['metrics'][0]
        r.update(value=None, status='missing', reason='')
        self.assertTrue(self.check(d)[0])
        r['reason'] = 'Input unavailable'
        errors, checks = self.check(d)
        self.assertEqual(errors, [])
        self.assertTrue(any('MISSING' in c for c in checks))

    def test_market_date_and_basis_are_required(self):
        d = fixture(); c = d['companies'][0]
        c['market'] = dict(metrics=[copy.deepcopy(c['periods'][0]['metrics'][0])], notes=[])
        self.assertTrue(self.check(d)[0])
        c['market']['as_of'] = '2026-01-02'
        c['market']['metrics'][0]['basis'] = {'price_date': '2026-01-02', 'eps_period': 'FY2025'}
        self.assertEqual(self.check(d)[0], [])

    def test_cagr_intervals_match_period_distance(self):
        d = fixture(); c = d['companies'][0]
        growth = copy.deepcopy(c['periods'][0]['metrics'][0])
        growth.update(id='revenue_cagr', from_period='FY2021', to_period='FY2025', intervals=5)
        c['growth_metrics'] = [growth]
        self.assertTrue(self.check(d)[0])
        growth['intervals'] = 4
        self.assertEqual(self.check(d)[0], [])

    def test_invalid_shapes_never_crash(self):
        for value in (None, [], {'schema_version': 3}, {'schema_version': 2, 'companies': [None]}, {'schema_version': 2, 'companies': [{'id': []}]}):
            with self.subTest(value=value):
                self.assertTrue(self.check(value)[0])

    def test_duplicate_ids_default_and_dates(self):
        for mutate in (
            lambda d: d['companies'].append(copy.deepcopy(d['companies'][0])),
            lambda d: d['companies'][0]['periods'].append(copy.deepcopy(d['companies'][0]['periods'][0])),
            lambda d: d['companies'][0].update(default_period='FY2021'),
            lambda d: d['companies'][0]['periods'][0]['period'].update(start='bad'),
            lambda d: d['companies'][0]['periods'][0]['statements'].pop('CF'),
        ):
            d = fixture(); mutate(d)
            self.assertTrue(self.check(d)[0])

    def test_invalid_values_provenance_and_formula_inputs(self):
        for mutate in (
            lambda r: r.update(value=float('inf')),
            lambda r: r.update(value=True),
            lambda r: r.update(value='=A1/B1'),
            lambda r: r.update(inputs=[]),
            lambda r: r.update(provenance={'source': 'unknown', 'kind': 'reported'}),
            lambda r: r.update(status='missing', value=.3, reason='Unavailable'),
        ):
            d = fixture(); mutate(d['companies'][0]['periods'][0]['metrics'][0])
            self.assertTrue(self.check(d)[0])


if __name__ == '__main__':
    unittest.main()
