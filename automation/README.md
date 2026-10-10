# 制作・納品コマンド

この既存チェックアウトを使います。新しいworktreeは作りません。
Python 3.10以上が必要です。納品サンプルと単体テストは標準ライブラリのみ。画像再生成と画像QAはPillow 12.3.0とNoto Sans CJKが必要です。

## 販売者の納品生成

選択肢だけのJSONをGit対象外のlocal_outputに置きます。schemaはFE_demo_answers.json、CORE_demo_answers.json、PRO_demo_answers.jsonを参照します。本人や勤務先の情報は入れません。

```bash
python automation/fulfill.py FE automation/FE_demo_answers.json --output local_output/fe_demo
python automation/fulfill.py CORE automation/CORE_demo_answers.json --output local_output/core_demo
python automation/fulfill.py PRO automation/PRO_demo_answers.json --output local_output/pro_demo
```

各コマンドは診断下書き、対象パッチ、参照実行コード入りZIPを生成します。同じ出力先への上書きを拒否します。FEのパッチは条件に合わせて1本のみ。CORE/PROは5本。顧客回答で実行する場合、診断の適用条件を販売者が確定し、ココナラはトークルーム、Squareは検証した購入者メールへ納品します。

## 販売素材の再生成とQA

```bash
python automation/build_content.py
python automation/build_images.py
python -m unittest discover -s qa -p 'test_*.py' -v
python automation/build_release.py
python automation/build_go_live.py
python automation/qa.py
```

build_contentはソース管理下の販売文章とサンプルを再生成するため、文章を編集した後は不用意に実行しないでください。商品診断テンプレートはfulfill.pyを正本とします。build_releaseは管理されたrelease配下の集約先だけを更新し、顧客の納品先には触れません。
qa.pyは全件検査と単体テストを実行し、qa/full_qa.md、リリースQA、SHA256一覧を更新します。終了コード0がPASS、1がFAILです。

## 検証範囲

ローカルサンプル、入力境界、納品ZIP、販売文章、画像を検証します。M365テナント接続、VBA実機、AIサービスへの送信、販売サイトの公開は実施しません。アプリの常駐サーバーは不要です。

Square支払確認・メール・冪等再実行は[Square CLI手順](../scripts/README.md)。既存資産生成だけでは実決済・メール到達や常時運用を検証しません。
