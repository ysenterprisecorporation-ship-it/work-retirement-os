# 導入手順

## ローカルの参照実行

展開した納品フォルダー（automationとpatchesがある階層）で以下を実行します。外部通信やログインは行いません。

```bash
python automation/patch_runner.py 01_forms_excel_teams patches/01_forms_excel_teams/sample_input.json --output local_output/01_forms_excel_teams.json
```

出力をexpected_output.jsonと照合します。JSONはUTF-8です。Pythonがない端末でもPROMPT.txtと下の手順を使えます。

## 業務ツールでの適用

M365内で接続する場合：
1. Formsで「分類」「内容」の2設問を作り、架空回答で試す。個人情報を収集しない。
2. OneDrive for BusinessまたはSharePoint上のExcelブックに、response_id／category／detailの3列を作り「受付表」というテーブルにする。
3. Power Automateで自動化したクラウドフローを作り、Forms「新しい応答が送信されるとき」を選ぶ。対象フォームを指定する。
4. Forms「応答の詳細を取得する」を追加。フォームIDを指定し、応答IDにはトリガーの動的コンテンツを使う。
5. 「作成」（Compose）を追加し、名前をResponseIdとする。入力にはトリガーの動的コンテンツの応答IDを選ぶ。Excel Online (Business)「表内に存在する行を一覧表示」で受付表を読む。小規模でもページネーションを有効にし、保管行が取得上限を超える前に別表へ分ける。
6. 「アレイのフィルター処理」を追加して名前をExistingResponsesとする。FromにはExcelのvalueを選ぶ。詳細モードの式は @equals(string(item()?['response_id']), string(outputs('ResponseId'))) とする。
7. 条件を @equals(length(body('ExistingResponses')), 0) とする。Yes側の中へExcel「表に行を追加」を置き、response_idにはResponseIdの出力、category/detailにはFormsの回答を選ぶ。
8. 同じYes側の中で、行追加が成功した場合だけTeams「チャットまたはチャネルでメッセージを投稿する」を実行する。検証チャネルを指定し、受付IDにはResponseIdの出力を入れる。回答本文は投稿しない。No側は何もしない。通知失敗後の再実行では既存IDとしてスキップするため、実行履歴を見て担当者が通知不足を補う。
9. トリガー設定の同時実行制御を有効にして並列度を1にする。架空回答2件を送信し、Excel2行とTeams2通知を確かめる。
10. 実行履歴から同じ応答を再実行し、増えないことを確かめてから運用開始する。
注：行数制限・ページネーション・Excelロックに注意。サンプルは小規模受付向け。大量処理や通知失敗後の再試行制御は対象外。CSVサンプルはフローのインポートファイルではない。

M365・Excel・AIツールの利用料は商品価格に含まれません。機能、ライセンス、権限、管理者ポリシーによって利用可否が変わります。導入や削減効果は保証しません。
