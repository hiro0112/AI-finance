# 共通データと財務確認

単年の図では次の形式のJSONを使用できる。複数年・ダッシュボードは[multi-year-data.md](multi-year-data.md)のv2形式を使い、各年度の集約値には本ページの会計規約を適用する。値は原通貨・原単位。企業ごとに異なる単位は許容するが図では変換する。JSONは将来の汎用レンダラーAPIではなく、共通数値を管理する契約である。

```json
{
  "companies": [{
    "id": "example",
    "name": "例示会社",
    "period": {"start": "2025-01-01", "end": "2025-12-31", "bs_date": "2025-12-31"},
    "scope": "連結", "accounting_standard": "日本基準",
    "currency": "JPY", "unit": "百万円",
    "values": {"assets": 100, "liabilities": 40, "equity": 60},
    "sources": {"S1": {"title": "決算短信", "url": "https://example.com/report.pdf", "published": "2026-02-06", "pages": "PDF P.9–10"}},
    "provenance": {"assets": {"source": "S1", "kind": "reported"}, "liabilities": {"source": "S1", "kind": "reported"}, "equity": {"source": "S1", "kind": "reported"}},
    "rounding": {},
    "notes": []
  }]
}
```

例はスキーマ用の架空データ。実在企業の値として使わない。未入手・非該当の値はnullとし、notesに理由を書く。sourceは公式URLまたはユーザー提供ファイルのパスを記録。PDFページ・印刷ページが異なれば両方を記す。

## 複数HTMLへの引き渡し

単年の従来形式でも複数図を作る場合は、トップレベルに `dataset_id` と `outputs`（例 `{ "boxes": "visuals.html", "sankey": "visuals.html", "strac": "visuals.html" }`）を追加する。従来検算器はこの追加情報を無視するため、親が単一HTMLへの収録と図切替を別途確認する。単独図では不要。

## 標準キー

- BS：assets, current_assets, noncurrent_assets, cash, ppe, current_liabilities, noncurrent_liabilities, liabilities, equity。equityは総資本・純資産。自己資本比率にはparent_equityを別に用意し、非支配持分を混同しない。
- PL：revenue, cost, gross, sga, other_operating_expense, operating_income, ordinary_income, pretax_income, tax, discontinued_income, net_income。net_incomeは連結全体、親会社帰属利益はparent_net_incomeを別に記録。
- CF：opening_cash, operating_cf, investing_cf, financing_cf, fx_cf, scope_cf, closing_cash。CF3区分・為替・範囲変動は流入プラス、流出マイナス。fx_cf/scope_cfの公表上ゼロ・非該当が確認できたときだけ0にする。
- 補足：配当、自社株買い、設備投資、リース、金融資産等は追加キー可。支出額か符号付フローかをnotesに定義する。

非継続事業損益が税前利益に含まれず純利益に含まれる場合、discontinued_incomeを符号付きで記録する。非該当を確認できた場合は0、未確認ならnullとして純利益検算をSKIPする。税前−税金＋非継続事業損益＝連結純利益を照合する。

各数値キーにprovenanceを付け、`kind: reported` は公表値、`kind: derived` は独自計算。独自計算には`formula`を付け、元となるsourceも記す。例えばUS GAAPでgross非開示なら、図示用の費用控除後残高と明記し、粗利益という公表科目に見せない。

## 端数と不一致

検算スクリプトの関係式（stdoutまたはコードで確認）の左辺−右辺が0でなければ、資料照合を先に行う。丸めが理由と確認できた場合のみ `rounding` に検算名と `{ "delta": 1, "reason": "百万円未満切捨てによる公表値の差" }` を記録する。大きな不一致を通すために理由を後付けしない。図のどの箱・帯を補正したかはHTMLにも明記し、公表値を書き換えない。

通貨換算はBSの期末レート、PL/CFの期中平均など目的に適した方法を選ぶ。サイズ比較だけの仮レートならその旨を明記し、原値と分ける。単位の違う値に共通金額縮尺を適用しない。

## 判断が要る範囲

金融業など売上原価・粗利益の区分が適さない業種は、機械的に同じPLに当てはめず図の適用限界を説明する。利益率差は直営/FC構成、会計基準、事業範囲も確認。BSはストック、PL/CFはフローであり、同じ金額縮尺でも加算できない。

## ユーザー提供の例示数値

架空会社や提供数値は `kind: provided` を使用できる。sourceは `type: provided` とし、ユーザー提供である旨のtitleを必須とする。同じ提供sourceからの独自計算は `kind: derived` とformulaを使う。存在しないURL・公開日・ページを作らない。未指定の対象期間はnull、範囲・会計基準・通貨は「未指定」等を記録し、HTMLに例示・未指定と明記する。すべてprovidedの例示ケースでは期間欠損は検証報告に記録するがエラーにしない。実在企業の未入手情報をprovidedへ変更して検証を通してはいけない。
