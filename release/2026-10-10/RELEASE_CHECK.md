# リリース判定 — Issue #1

RELEASE STATUS: BLOCKED（Square直販の実リンクと実購入後納品のみ）

販売素材・実装は完成。ココナラFEはIssue #1の報告による公開済み、サービスID4445208、価格3,000円、同時受付上限10件。販売者UIをCodex自身が操作したという意味ではない。

- FE：4問、300〜500字診断、既製パッチ1本、導入手順・チェックリスト。
- CORE10,000円・PRO40,000円の資産を保持。今回の直販追加登録は後日。
- 5パッチ、画像3枚、納品見本ZIP8個、ココナラ/Square文章、SNS25本を再利用。
- scripts/square_fe_launch.py：全リンクと注文の照合、既存再利用、必要時のみ冪等な1件作成。既存民泊AIの2,980円を変更しない。
- scripts/square_fulfill.py：実支払確認、4問依頼、回答選択肢から既存生成器でZIP作成、メール送信と実送信状態照合。返信収集と診断承認は販売者操作。
- scripts/square_promote.py：本番の実リンク・実納品到達と購入者検証承認後だけSNS草稿生成。現時点では実URL未取得、投稿保留。
- APIモックテストと全件QAの証拠：[QA_REPORT.md](QA_REPORT.md)。実Square、Resend、M365実接続、VBA実機は未検証。
- Square認証、送信認証、検証済み送信元と受信可能返信先が未提供。必要な入力欄と通信先を環境ドラフトへ保存。保存はPublishを意味しない。
- 常時運用ホスト・自動返信収集・自動返金は未配備。常時全自動納品とは扱わない。

人間のみの残作業は[HUMAN_ACTIONS.md](HUMAN_ACTIONS.md)の2項目。全文と設定は[GO_LIVE_NOW.md](GO_LIVE_NOW.md)、項目別の実施・未検証は[SQUARE_LAUNCH_STATUS.md](SQUARE_LAUNCH_STATUS.md)。制作・API実装・コミット・pushを人間へ返さない。
