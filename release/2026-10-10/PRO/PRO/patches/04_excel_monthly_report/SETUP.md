# 導入手順

## ローカルの参照実行

展開した納品フォルダー（automationとpatchesがある階層）で以下を実行します。外部通信やログインは行いません。

```bash
python automation/patch_runner.py 04_excel_monthly_report patches/04_excel_monthly_report/sample_input.json --output local_output/04_excel_monthly_report.json
```

出力をexpected_output.jsonと照合します。JSONはUTF-8です。Pythonがない端末でもPROMPT.txtと下の手順を使えます。

## 業務ツールでの適用

1. 対象ブックを複製し、period（YYYY-MM）とamount（同一単位）の列を用意する。
2. 2か月分の行をsample_input.jsonと同じ形式へ転記する。実名・勤務先名は不要。
3. ローカル実行で集計と報告文の下書きを生成する。
4. ExcelでもSUMIFによる月別合計を照合する。比較月が0の場合、増減率は出さない。
5. 数値だけを承認済みAIとPROMPT.txtへ入力し、原因を創作せず報告文を整える。
6. 数値・単位・比較期間を担当者が確定してから報告する。予測や財務助言は対象外。

M365・Excel・AIツールの利用料は商品価格に含まれません。機能、ライセンス、権限、管理者ポリシーによって利用可否が変わります。導入や削減効果は保証しません。
