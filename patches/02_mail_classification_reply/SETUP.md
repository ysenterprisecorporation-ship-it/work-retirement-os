# 導入手順

## ローカルの参照実行

展開した納品フォルダー（automationとpatchesがある階層）で以下を実行します。外部通信やログインは行いません。

```bash
python automation/patch_runner.py 02_mail_classification_reply patches/02_mail_classification_reply/sample_input.json --output local_output/02_mail_classification_reply.json
```

出力をexpected_output.jsonと照合します。JSONはUTF-8です。Pythonがない端末でもPROMPT.txtと下の手順を使えます。

## 業務ツールでの適用

1. 架空のメール本文を使い、承認済みAIの入力欄へPROMPT.txtと本文を入れる。
2. 出力のcategoryと根拠を読み、複数分類・不明情報は「要確認」にする。
3. 実メールは社内のデータ利用規則に従い、氏名・連絡先・顧客名・識別番号を削除してから入力する。許可がない場合は架空例だけを使う。
4. 下書きをメールアプリに貼り付け、宛先、事実、期限、請求内容、言い回しを担当者が確定する。
5. 送信は担当者が手動で行う。自動送信・受信箱への接続は含まれない。

M365・Excel・AIツールの利用料は商品価格に含まれません。機能、ライセンス、権限、管理者ポリシーによって利用可否が変わります。導入や削減効果は保証しません。
