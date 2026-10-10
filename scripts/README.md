# Square FE 決済・納品運用（Issue #1）

標準ライブラリのみ。既存商品・パッチ・salesの文章・automation/fulfill.pyを再利用。新規ストア、他ブランドの変更、返金API、SNS投稿APIは実装対象外。認証がない場合もモックテストは実行できる。

## 認証と通信

秘密欄：SQUARE_ACCESS_TOKEN、RESEND_API_KEY。環境変数：DELIVERY_FROM、DELIVERY_REPLY_TO。複数店舗の場合だけSQUARE_LOCATION_IDを選ぶ。トークンや購入者情報をコマンド引数やGitへ書かない。Resendはドメイン検証・送信・送信状態読み取りに必要なFull access権限を使用。既存の受信可能な返信先を使用する。Resendは送信経路であり、返信受信箱を作成する機能ではない。
HTTPSプロキシ・CAをそのまま継承。固定APIホスト以外へ認証ヘッダーを転送せず、リダイレクトを拒否する。ProductionとSandboxは必ず明示指定。Square API版2025-03-19。

## 1. 全ページ探索と必要時のみ作成

```bash
python scripts/square_fe_launch.py --environment production --dry-run
python scripts/square_fe_launch.py --environment production --apply
```

最初のコマンドはGETだけで、ローカル台帳も作らない。全リンクの注文を取得し、商品名・1個・3,000円JPYの総額・割引なし・追加料金なしを照合。民泊AIの2,980円など他ブランドは除外し変更しない。全ページ取得に失敗した場合は作成しない。重複やFE価格不一致は候補IDだけを報告し作成を止める。店舗が複数の場合はACTIVE・JPY・カード決済可能な候補IDだけ表示し、location-idで指定するまで作成しない。
一致リンクがあれば再利用し、変更しない。一致がない場合だけ、検証済み送信ドメインと販売者返信先を確認してquick_payを1件POSTする。冪等キーは環境・店舗・商品ごとに固定、作成意図を事前保存して異なる再試行を拒否する。
購入者に表示されないdescriptionを条件表示として使わない。必須同意欄2つで4問・既製パッチ1本・回答後3日・別途利用料・開発なし・保証なし・返金条件を表示し、連絡先を設定する。既存リンクにこの表示がない場合はそのリンクを変更せずSNS宣伝を保留。販売者の法定表示、現在の画面表示、購入者メール取得は実購入で検証する。APIモックだけで検証済みとしない。

## 2. 支払確認と4問依頼

payment-idにはSquareに存在する支払IDを使用する。通知や領収書URLだけでは確認済みとしない。下記はシェル変数に実IDが設定されている状態で実行する。IDや住所を公開ログへ転記しない。

```bash
python scripts/square_fulfill.py request --environment production --payment-id "$square_payment_id" --dry-run
python scripts/square_fulfill.py request --environment production --payment-id "$square_payment_id" --apply
```

Payments APIでCOMPLETED、総額3,000円JPY、未返金、チップなしを確認し、注文のFE名と価格・完了状態・店舗・顧客一致を照合する。メールは支払情報から、欠損時だけ対応するCustomerから取得する。メール未取得なら送らない。購入者メールは通信メモリだけで扱い、出力・台帳へ保存しない。機械検証済みの依頼文をResendで送信する。

## 3. 選択肢の回答と納品

購入者はDELIVERY_REPLY_TOの販売者受信箱へ返信。返信収集と診断承認は自動化しない。実名・勤務先・実ファイルは不要。例示schemaはautomation/FE_demo_answers.json。回答選択肢だけをlocal_output/answers.jsonに保存し、回答と診断が一致した後だけapprove-diagnosisを付ける。

```bash
python scripts/square_fulfill.py deliver --environment production --payment-id "$square_payment_id" --answers local_output/answers.json --approve-diagnosis --dry-run
python scripts/square_fulfill.py deliver --environment production --payment-id "$square_payment_id" --answers local_output/answers.json --approve-diagnosis --apply
python scripts/square_fulfill.py check-delivery --environment production --payment-id "$square_payment_id"
```

300〜500字のミニ診断と選定パッチ1本・導入手順・チェックリストを既存生成器でZIP化する。自己完結ZIPをメール添付する。送信には依頼済み台帳が必要。同じ支払・送信段階のメールは再送しない。API応答前の異常は意図・内容ハッシュと固定メール冪等キーで再試行する。23時間を越える不明な送信は再送せず、Resend送信履歴と台帳を照合する。履歴IDを誤って入力すると検証を偽るため、手動で台帳を書き換えない。
台帳・ZIPはlocal_output内限定、ファイル0600。顧客宛先を出力しない。台帳のメールIDとハッシュは送信照合に必要なので私有運用情報として扱う。acceptedとdeliveredを区別し、依頼とZIP両方の実送信状態をAPIで取得する。deliveredは受信サーバー到達であって購入者がZIPを開いた証明ではない。

## 4. 稼働中の新規支払監視

begin_timeは対象期間のRFC3339、location-idは検証したFE店舗。実運用で希望する期間だけ対象にする。

```bash
python scripts/square_fulfill.py poll --environment production --location-id "$square_location_id" --begin-time "$square_begin_time" --dry-run
python scripts/square_fulfill.py poll --environment production --location-id "$square_location_id" --begin-time "$square_begin_time" --watch --interval 60 --apply
```

60秒ごとに支払を再照合し、完成支払の依頼だけを重複なく送る。他ブランド・未完了・2,980円を送信しない。失敗は個人情報を含まないコード別集計で出す。24時間運用ホスト・クラウド終了後の継続・返信自動収集・自動返金は未配備。販売者は7日目の再案内、14日目の未納品全額返金を既存Square管理画面で行う。

## 5. 実URLによるSNS草稿の生成

本番APIから検証したリンクと同店舗の実FE支払について、依頼とZIPの送信状態を取得する。購入者が購入画面の条件・連絡先・法定表示、返信受信、ZIP展開を実確認した後だけapprove-buyer-checkを付ける。

```bash
python scripts/square_promote.py --environment production --proof-payment-id "$square_payment_id" --dry-run
python scripts/square_promote.py --environment production --proof-payment-id "$square_payment_id" --approve-buyer-check --apply
```

本番の実URLのみlocal_output/sns_liveの3草稿へ出力。仮URL・Sandbox・送信未着は不可。自動でSNSへ投稿しない。既存SNSのプロフィールCTAを使用する場合は同じ実URLをプロフィールへ登録してから公開する。

## テストとAPI仕様の根拠

```bash
python -m unittest discover -s qa -p 'test_*.py' -v
```

[Square公式API仕様](https://github.com/square/connect-api-specification/blob/master/api.json)、[Resend公式API仕様](https://github.com/resend/resend-openapi/blob/main/resend.yaml)のcheckout_options、Payment、Customer、emails、domainsを照合。公式仕様の取得は実施済み。実SquareアカウントとResend・受信箱の操作は認証未提供で未実施。モックは実決済やDNS認証を検証しない。
