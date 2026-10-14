# 財務HTMLの共通データ契約（v2）

## 入力を選ぶ

- `input_mode: external`：公式資料から対象通期を取得する。訂正・再表示は最新資料を優先し、旧値との対応と版を残す。予想・LTM・短期決算を通期実績5期へ混ぜない。5年分析ダッシュボードを含む場合、finance-valuationが利用可能なら詳細5年分析のデータ・指標定義を利用する。HTMLの依頼だけならExcelを追加生成する必要はない。Wordも明示依頼がなければ作成しない。利用できなければfinancial-analysis-dashboardのdashboard-data.mdの標準セットを同じ定義で親が算出する。
- `input_mode: finance-valuation`：指定された分析結果のJSON・Excel・出典台帳を使う。既存の対象期・取得日・計算定義を保持し、株価を含め黙って更新しない。ネット取得を伴う不足補完はユーザーが指定した場合に限り、補完箇所と出典を分けて記録する。
- 未指定で会話に分析結果が明確に指定されていれば再利用する。それ以外はexternalとし、採用した入力経路と対象期を伝える。複数候補から入力ファイルを特定できない場合だけ確認する。

外部取得禁止の場合はどのモードでも提供資料のみ。再利用するファイルが未提供・所在不明なら所在を確認する。資料にない指標はN/Aと理由を残す。最新通期を求められたのに入力が古い場合は、その差を説明して更新に必要な資料を確認する。

## 保存形式

単年・単独図は従来の[data-contract.md](data-contract.md)形式を引き続き使える。複数年またはダッシュボードでは `schema_version: 2` の `financial-data.json` を使う。3図の描画時は選択したperiodのvaluesを従来の標準キーとして渡す。詳細三表を図用の集約値で置き換えない。

トップレベル：

- `schema_version: 2`、`input_mode`、`input_files`（入力パスの配列）、`dataset_id`（同じデータを使う成果物を識別する版）、`generated_at`（ISO日時）。
- `companies`：下記企業レコードの配列。
- `outputs`：作成する種類だけをキーにする。標準の3図統合では `boxes`・`sankey`・`strac` に同じ単一HTMLファイル名を指定する。図の位置はページ内タブ／ハッシュで扱い、値にはハッシュを入れない。明示された分割出力も使用可能。`dashboard`は経営分析HTML。BS・PLボックス図を統合する標準形では `dashboard` と `boxes` に同じファイル名を指定する。サンキー図・STRAC表を別HTMLで作る場合は、それらを経営分析とは別のファイル名にする。

企業レコード：

- 従来と共通の `id, name, scope, accounting_standard, currency, unit, sources, notes`。出典の規約はdata-contract.mdに従う。
- `default_period`：最も新しい表示対象通期のid。例 `FY2025`。
- `periods`：古い順の表示対象通期。対象期は呼出元の指定に従い、既存分析の再利用では元の期間を保持。各要素は `id, label, period, values, provenance, rounding, notes, statements, metrics`。
- `period` は従来通り `start, end, bs_date`。values/provenance/roundingは従来の関係式に使う集約値。補助年度を表示5期に数えず、`supporting_periods` に同じ形式で別保存してよい。
- `statements` は `PL, BS, CF` をキーとする明細行配列。行は `{id, label, original_label, level, unit, value, status, reason, provenance}`。`level` は0以上の階層、小計と内訳を重ねて集計しない。原表の全表示科目と必要な注記内訳を保持し、行数合わせの架空科目を作らない。
- `metrics` は当該年度の経営指標配列。`growth_metrics` はCAGR等の複数年度指標配列。`market` は `{as_of, metrics, notes}` で、年度とは独立した基準日の市場指標。過去株価データがなければ最新のスナップショットだけを保持する。

明細・指標の `value` は有限数値かnull。`status` は `ok / missing / not_applicable / not_meaningful`。ok以外はvalue=null、reason必須。表示はmissing/not_applicableがN/A、not_meaningfulがN/M。出典未確認の値にokを付けない。割合の内部値は比率（0.32）、unitはratio、画面では32.0%などに変換する。倍率はunit=multiple。通貨額や1株値は固有の単位を明記する。

指標の追加フィールド：`id, label, category, unit, value, status, reason, definition, formula, inputs, provenance`。inputsは入力の所在地を文字列配列で記す（JSON項目パスまたはExcelのシート!セル）。provenanceはsourceとkind、計算値ならformulaを持つ。市場指標には `basis` オブジェクト（例 `{ "price_date": "2026-09-10", "eps_period": "FY2025", "share_basis": "分割調整済み普通株" }`。指標に応じBPS期末・株数日も記す）、CAGRには `from_period, to_period, intervals` を追加する。formulaは説明文字列でありevalしない。

## 変換手順

finance-valuationの出力JSONは固定スキーマとは限らない。構造を読んでから親が変換し、`mapping.json` に入力ファイル／シート／行キー→出力項目、符号・単位変換、集約式を残す。

1. 元ファイルを保持し、企業・通期・通貨・単位・会計範囲・出典を抽出する。行×年度のJSONは年度別に転置し、全明細をstatementsへ移す。原科目ラベルと並び、出典の年度対応を残す。明細と注記ブロックの表示順・階層は親が確定し、担当はその順序を使う。
2. 図用valuesを標準キーへ対応付ける。1つの集約値に複数行を使う場合は内訳と式を記録。会計的に対応不明ならnullとし、名前の類似だけで対応させない。
3. 元の分析で算出済みの指標は数値・式・入力・定義を一緒に取り込む。JSONが原値だけならExcelの経営指標・市場指標シートも読む。再計算済みの保存値を確認し、数式文字列や古いキャッシュを計算結果として扱わない。
4. 保存値が利用できない場合、親が元の式と原数値から一度だけ再計算して代表値を照合する。使用可能な表計算ツールがあればその手順を使う。不足入力や不明な式はN/Aと理由にする。担当HTMLで個別に計算定義を変えない。
5. 最新市場指標はmarketへ、年度の経営指標はperiodsへ保存。再利用時にPER等の定義がダッシュボード用の標準定義と違えば保持して違いを明記し、無断で標準へ置換しない。
6. `python3 "{VISUALS_SKILL_ABSOLUTE_PATH}/scripts/validate_bundle.py" /absolute/path/financial-data.json` で全年度を検査し、元の分析結果と三表・代表指標・欠損件数を照合する。確定したdataset_idと同一JSONを全担当へ渡す。

この手順は異なる既存形式を読み取って変換するための指示であり、任意のExcelを無人で変換する汎用インポーターではない。

## 用途別のデータ範囲

図解だけの外部取得では、指定図に必要な三表項目・年度・出典を取得する。市場指標・セグメント・詳細な経営分析は自動追加しない。既存分析の再利用では含まれる明細・指標・コメントを保持するが、不足を外部取得で広げない。

経営分析ダッシュボードを作る場合は [dashboard-data.md](../../financial-analysis-dashboard/references/dashboard-data.md) の分析コメント・セグメント・標準指標を追加適用する。数値検証は本スキルのscriptsを共用する。この参照のために図解HTMLを生成する必要はない。
