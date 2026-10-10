# 導入手順

## ローカルの参照実行

展開した納品フォルダー（automationとpatchesがある階層）で以下を実行します。外部通信やログインは行いません。

```bash
python automation/patch_runner.py 05_vba_generate_test patches/05_vba_generate_test/sample_input.json --output local_output/05_vba_generate_test.json
```

出力をexpected_output.jsonと照合します。JSONはUTF-8です。Pythonがない端末でもPROMPT.txtと下の手順を使えます。

## 業務ツールでの適用

1. デスクトップ版Excelで検証専用ブックを作り、DataシートのA1を項目、B1を数値、B2:B4を10、20、30とする。既存のSummaryシートは置かない。
2. ファイルをマクロ有効ブックとして別名で保存する。原本を開いた状態では実行しない。
3. 組織がマクロを許可している場合だけ、VBEの標準モジュールにsample.basを取り込む。保護ビューやマクロの信頼設定を全体で弱めない。
4. VBEで「デバッグ→VBAProjectのコンパイル」。エラーがあれば実行せず、対象行と一般化したエラー文をPROMPT.txtで見直す。
5. SummarizeSampleを実行し、SummaryのTotalが60、Numeric countが3になることを照合する。
6. 文字列・空欄・エラーセル・負数を追加し、TEST.mdの受入条件を順に試す。
7. ローカル静的チェックは危険語の検出だけであり、VBA実行の証明ではない。組織がマクロ不可なら、このパッチは導入せず別のパッチを選ぶ。

M365・Excel・AIツールの利用料は商品価格に含まれません。機能、ライセンス、権限、管理者ポリシーによって利用可否が変わります。導入や削減効果は保証しません。
