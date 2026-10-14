# CLAUDE.md

このファイルは、本リポジトリで作業する Claude Code 向けのガイドです。

## プロジェクト概要

企業財務分析・バリュエーション・財務図解を行うための Claude スキル集。

| スキル | 役割 |
| --- | --- |
| [skills/finance-valuation/](skills/finance-valuation/SKILL.md) | 財務分析、詳細5年分析、PER・PBR、DCF・WACC、類似企業比較などのバリュエーション。標準成果物は出典を追える Excel |
| [skills/financial-analysis-dashboard/](skills/financial-analysis-dashboard/SKILL.md) | 経営分析ダッシュボード（BS・PLボックス図入りの単一HTML）。最後に「強み・弱み・課題・今後の戦略の方向性」のまとめを収録 |
| [skills/financial-statement-visuals/](skills/financial-statement-visuals/SKILL.md) | 財務図解（Box図・サンキー図・STRAC表）の単一HTML。共通データ契約と数値検証スクリプトを保持 |

各スキルは `SKILL.md` を入口とし、詳細仕様は `references/` 配下に分割している。

## 構成上の注意

- `financial-analysis-dashboard` は `financial-statement-visuals` の共有資源（`references/multi-year-data.md`、`data-contract.md`、`boxes.md`、`scripts/`）を相対パスで参照する。ファイル名・パスを変える場合は参照元のリンクも更新する。
- スキル間の担当範囲（図解のみ／ダッシュボード／Excel分析）の切り分けは各 `SKILL.md` に記載されている。仕様を変える場合は関連スキル側の記述と矛盾しないようにする。
- 文書は日本語で記述する。既存の文体（常体・簡潔な指示形）に合わせる。

## 検証スクリプト

`skills/financial-statement-visuals/scripts/` にオフラインの JSON 検証スクリプトがある（Python 3、外部依存なし）。

```sh
cd skills/financial-statement-visuals/scripts
python validate_data.py <data.json>
python validate_bundle.py <bundle.json>
python -m unittest test_validate_bundle.py
```

スクリプトを変更したら必ずテストを実行してからコミットする。

## Git 運用ルール

- リモート: `origin` = https://github.com/hiro0112/AI-finance.git 、ブランチ: `main`
- **コードやファイルを変更するたびに、コミットして GitHub（`origin main`）へプッシュする。** 変更をローカルに溜めたままにしない。
- 1コミット1目的を基本とし、コミットメッセージは変更内容が分かる日本語または英語で簡潔に書く。
- プッシュ前に `git status` と `git diff` で意図しないファイル（一時ファイル、生成物、機密情報）が含まれていないか確認する。
- 認証情報・APIキー・有料データの原本などはコミットしない。
- `git push --force` や履歴の書き換えは、ユーザーの明示的な指示がある場合だけ行う。
