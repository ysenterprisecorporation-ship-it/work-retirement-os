# 導入手順

## ローカルの参照実行

展開した納品フォルダー（automationとpatchesがある階層）で以下を実行します。外部通信やログインは行いません。

```bash
python automation/patch_runner.py 03_meeting_minutes_todo patches/03_meeting_minutes_todo/sample_input.json --output local_output/03_meeting_minutes_todo.json
```

出力をexpected_output.jsonと照合します。JSONはUTF-8です。Pythonがない端末でもPROMPT.txtと下の手順を使えます。

## 業務ツールでの適用

1. メモを「会議名／決定事項／作業・担当・期限」に分ける。
2. 氏名や社内固有名を担当Aなどへ置換し、承認済みAIにPROMPT.txtとメモを入力する。外部入力が禁止ならローカルの構造化JSONサンプル方式を使う。
3. 元メモと出力を照合し、決まっていない担当・期限は「未設定」のまま残す。
4. 合意済みの議事録を社内の所定の保存先に保存し、必要ならTeams内に貼り付ける。
5. ToDoの担当者に、内容と期限を合意してもらってから運用する。To Do／Plannerへの自動登録は含まれない。

M365・Excel・AIツールの利用料は商品価格に含まれません。機能、ライセンス、権限、管理者ポリシーによって利用可否が変わります。導入や削減効果は保証しません。
