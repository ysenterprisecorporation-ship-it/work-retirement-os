# 受入試験

sample.basの静的結果はSTATIC_CHECK_PASS、executedはfalse。危険語を含むコードではREVIEW_REQUIREDを出す。これはコンパイル試験ではない。Excel実機：10/20/30は60・3件、空欄/文字列/エラーは除外、負数-5を追加すると55・4件。Dataがない時は通知して終了。Summaryは検証専用の出力先であることを確かめる。

実施済み：Python参照実行・期待出力照合・境界条件の単体テスト。未実施：顧客テナントでの接続、AIサービスへの実送信、VBA実機実行。結果はリリースのQA_REPORT.mdに記載。
