"""Build one self-contained publication document from the reviewed sales texts."""
from pathlib import Path
import json
ROOT=Path(__file__).resolve().parents[1]
REL=ROOT/'release/2026-10-10'
CAT=json.loads((ROOT/'business/catalog.json').read_text(encoding='utf-8'))
parts=[]

def add(s):parts.append(s.strip())
def text(channel,tier,filename):return (REL/channel/tier/filename).read_text(encoding='utf-8').strip()
def block(label,value):return f'#### {label}\n\n```text\n{value}\n```'

CC_FIELDS=[('サービスタイトル','title.txt'),('キャッチコピー','catchcopy.txt'),('サービス説明','description.txt'),('購入にあたってのお願い','purchase_notes.txt'),('FAQ','faq.txt')]
SQ_FIELDS=[('商品名','product_name.txt'),('短い説明','short_description.txt'),('商品説明','full_description.txt'),('購入後メッセージ（回答依頼）','first_reply.txt'),('納品メッセージ（納品時のみ送信）','delivery_message.txt')]

def cc(tier,after=False):
 c=CAT[tier]
 settings=f'''- 価格：{c['price']:,}円。購入時に追加オプションなし。
- 納期：全設問の回答受領後{c['days']}日以内。画面の予想お届け日数は{c['days']}日。回答が未着の間は診断を開始しない。
- 即購入：ON（見積り不要で通常購入）。見積り必須：OFF。
- 有料オプション：OFF。定期購入：OFF。ビデオチャット：OFF。受付：ON。同時受付上限：最初は1件。
- 推奨カテゴリ：IT・プログラミングの業務効率化・自動化に相当する相談・助言カテゴリ。既存の販売手順に沿った推奨で、現行UIの分類名はこの環境から未実確認。
- アップロード画像：/workspace/work-retirement-os/release/2026-10-10/images/{tier}.png
- FAQはQとAを対応する入力欄へ分けて貼り付ける。
- 購入後の返信と納品文は出品本文に混ぜず、トークルームで送信する時に使う。納品文は診断と納品ZIPの添付後だけ送る。
'''
 body=settings+'\n\n'+'\n\n'.join(block(label,text('coconala',tier,f)) for label,f in CC_FIELDS)
 if after:
  body+='\n\n'+block('購入後最初の返信文',text('coconala',tier,'first_reply.txt'))
  body+='\n\n'+block('納品メッセージ',text('coconala',tier,'delivery_message.txt'))
 return body

def sq(tier):
 c=CAT[tier]
 settings=f'''- 価格：{c['price']:,}円（購入者に表示する商品価格）。配送・追加オプション料金なし。税を追加して表示価格を増やす設定は使わず、税区分は販売者アカウントの実際の設定に従う。
- 納期：全設問回答の受領後{c['days']}日以内。自動ダウンロードではなく手動納品。
- 商品タイプ：サービス。オンライン販売：ON。配送：OFF。定期課金：OFF。在庫追跡：OFF。購入後の自動ファイル配布：OFF。
- 画像：/workspace/work-retirement-os/release/2026-10-10/images/{tier}.png
- 購入後メッセージは注文に紐づく購入者連絡で送る。返信を受領してから診断を生成する。納品文は実際の納品と同時に送る。
- Squareの販売者UI・添付可能な形式は未実操作。公開前に、注文に紐づく購入者連絡とZIPの手動納品が販売者アカウントで使えることが必要。未対応なら、このチャネルの決済受付はOFFのままにする。ココナラFEの先行公開には影響しない。
'''
 return settings+'\n\n'+'\n\n'.join(block(label,text('square',tier,f)) for label,f in SQ_FIELDS)+'\n\n'+block('返金方針（ストアの返金規定欄）',text('square',tier,'refund_policy_draft.txt'))

SNS={}
for platform,filename in [('X','x_posts.txt'),('Instagram','instagram_posts.txt'),('Facebook','facebook_posts.txt')]:
 first=(REL/'sns'/filename).read_text(encoding='utf-8').split('\n\n---\n\n')[0]
 if platform=='Instagram':
  body=first.split('キャプション：',1)[1].strip()
  body='AIを増やさない。仕事を減らす。\n'+body
 else:body=first.split('\n',1)[1].strip()
 SNS[platform]=body
# A canonical plain-text post is supplied as well, while the launch guide embeds it fully.
for platform,body in SNS.items():
 (ROOT/'sales/sns'/f'tonight_{platform.lower()}.txt').write_text(body+'\n',encoding='utf-8')
 (REL/'sns'/f'tonight_{platform.lower()}.txt').write_text(body+'\n',encoding='utf-8')

def sns_full():
 return '\n\n'.join(block(platform+'：今夜の投稿本文',body) for platform,body in SNS.items())

add('''# GO LIVE NOW — 2026-10-10（日本時間）

公開用テキストはすべてこの文書に全文収録。管理ラベルや見出しを投稿本文へ混ぜず、text枠内だけをコピーします。販売画像も末尾に表示します。

## A. RELEASE STATUS

READY

販売素材・納品サンプル・ローカル検証の準備完了。販売サイトへの公開済みを意味しません。M365の実接続・VBA実機実行は未検証と商品文面に明記済みです。

Codexが実施：Git・main・最新コミット・remote・push一致の照合、必要ファイルと全文の再読、価格・商品範囲・チャネル分離・CTA・未完成マーカー・秘密情報検査、画像と納品ZIPの検証。詳細な再検査結果はリリースQAへ反映しています。
販売サイト・SNSの認証済み操作ツールはこの環境にありません。販売者本人による公開操作だけが残ります。本人認証・決済設定済みアカウントを前提にした所要時間です。未設定や審査待ちなら、そのチャネルの販売開始時刻は確約できません。

## B. 今日公開する順番

最初の購入可能な状態を優先し、CORE/PROと環境Publishは先行FEの販売開始後に実施します。

| 順 | 操作 | 見積もり | 累計 |
| --- | --- | --- | --- |
| 1 | ココナラFEを公開 | 8分 | 8分：最初の販売開始 |
| 2 | SquareはFEだけを先行公開 | 7分 | 15分 |
| 3 | Square FEの実URLをSNSプロフィールへ設定し、X・Instagram・Facebookを各1本公開 | 7分 | 22分：FEの販売導線が完成 |
| 4 | ココナラCORE/PROを公開 | 各8分 | FE販売開始後の拡張 |
| 後続 | Square CORE/PRO、環境Publish | 各商品6分、環境1分 | FE販売開始後の拡張 |

### B1. ココナラFE — 最初に公開（8分）

- 開くサービス：ココナラ、販売者アカウント。
- 開く画面：「サービスを出品する」→通常サービスの入力画面。
- 入力文面：以下に全文。価格3,000円、納期は回答受領後3日以内。
- 最後のボタン：「公開する」。画面上の同趣旨の公開ボタンを使う。ボタン名・配置は実ログインで未検証。
''')
add(cc('FE'))
add('''### B2. Square FE — SNSの決済先を作る（7分）

- 開くサービス：Square、販売者アカウント。
- 開く画面：Squareオンラインストア→商品→商品を作成。
- 初日はFEを1商品だけ登録。商品タイプをサービスにし、オンライン販売ON、配送OFF、定期課金OFF、自動ファイル配布OFF。価格3,000円、全回答受領後3日以内の手動納品。
- 最後のボタン：「保存」→サイトの「公開」。公開されたFE商品ページを開き、ブラウザーのアドレス欄から実URLをコピーする。この実URLだけをB3のリンク欄に入れる。仮URLの入力やリンク文字列の創作はしない。
- Squareが利用可能な販売者状態でない、購入者連絡・ZIP手動納品の導線がない場合は決済受付を開始しない。B1のココナラFEは先行公開し、Square用SNS投稿はリンクが成立してから実行する。
''')
add(sq('FE'))
add('''### B3. SNS — この3本に決定（7分）

- 開くサービス：販売者のX、Instagram、Facebook。ココナラ取引の購入者向け配信ではない。
- 開く画面：各プロフィール編集のウェブサイト／リンク欄→各通常投稿の作成画面。
- リンク欄：B2でコピーした公開済みSquare FE商品ページの実URL。最後に「保存」。本文中の「プロフィールのSquareストア」はこのURLを指す。
- 価格：本文の3,000円。納期はリンク先に表示した回答受領後3日以内。
- ON/OFF：投稿を公開設定ON。有料広告・予約投稿・自動DM・自動返信・アカウント連携はOFF。通常の公開投稿を今送信する。
- 画像：3媒体とも /workspace/work-retirement-os/release/2026-10-10/images/FE.png の1枚。Instagramも1枚で投稿し、未制作のカルーセルを要求しない。
- 最後のボタン：X「ポストする」、Instagram「シェア」、Facebook「投稿」。
- コピーする本文は以下の3枠。候補の選択は不要。
''')
add(sns_full())
add('''### B4. ココナラCORE/PRO — FE販売開始後（各8分）

- 開くサービス：ココナラ。
- 開く画面：「サービスを出品する」→通常サービス。
- 先にCORE、次にPRO。見積り必須OFF、即購入ON、有料オプションOFF、ビデオチャットOFF、受付ON、各同時受付上限1件。
- COREは10,000円・全回答受領後3日以内。PROは40,000円・全回答受領後5日以内。
- アップロード画像：下記の各商品パス。
- 最後のボタン：「公開する」。下の完成済み文面を対応欄へそのまま入力する。
''')
for tier in ['CORE','PRO']:
 add('#### ココナラ'+tier+' 完全入力セット')
 add(cc(tier,after=True))

add('''## C. ココナラFE 完全入力セット

出品画面へコピーする全文です。購入後最初の返信と納品文は、トークルームで実際のタイミングに送信します。
''')
add(cc('FE',after=True))
add('''最終検査：このC欄の貼り付け用文面とB1/B4の貼り付け用文面は、販売用ココナラファイルとの全文一致および外部誘導検索で検証する。外部連絡・外部決済・外部取引への誘導文は含めない。''')
add('''## D. Square 完全入力セット

外部SNSからの新規流入専用です。初日はFEのみ先行し、CORE/PROは先行FEの販売開始後に同じ商品作成画面で追加します。以下に3商品すべての全文を掲載します。
販売者アカウントの本人・決済口座・通信販売の表示情報は、販売者アカウント側の実情報を使います。この文書へ実名・住所・口座・勤務先を記入する必要はありません。
返金方針もこの文書に全文収録しています。納品ZIPの見本は架空回答です。実購入者には、回答選択肢から作成した診断とZIPを手動納品します。
''')
for tier in CAT:
 add('### Square '+tier)
 add(sq(tier))
add('''## E. SNS 今夜投稿するもの

X投稿1、Instagram投稿1のキャプション、Facebook投稿1を採用しました。本文を再掲します。InstagramはFE画像1枚だけで成立するキャプションにしました。
Square FEの公開済み実URLを各プロフィールのリンク欄に登録してから投稿します。価格3,000円、診断4問、ミニ診断、既製パッチ1本の同じ訴求で統一します。
''')
add(sns_full())
add('''## F. 環境設定 — 販売公開後へ回す

保存済みドラフトにはインストールスクリプト・起動手順・リポジトリ設定があります。稼働状態はrunning／connected、未入力の実行要件は0件です。保存済みドラフトの存在だけでは、最新内容のPublish完了を断定できません。UIの「環境を編集・要確認」はこのチャットから直接観測していません。

- 画面：このチャットに紐づくクラウド環境の設定画面。販売公開後に開く。
- 確認対象：保存済みインストールスクリプト・起動手順・work-retirement-osのリポジトリ設定が表示されていること。文面の貼り直しは不要。
- ボタン：未公開の差分が表示される場合だけ「保存」→「Publish（公開）」。未公開の差分がなければ追加操作は不要。

この環境のPublishはココナラ・Squareの販売開始条件ではありません。新しいタスクでのスナップショット復元は今回未検証です。

## G. 人間総作業時間

最初の販売開始：ココナラFEの8分。
FEを2チャネルで販売しSNS3媒体に告知する最短導線：8＋7＋7＝22分。画像のアップロードと通常の貼り付けを含む操作見積もりで、実測値ではありません。

当初の全3商品を両チャネルで一括公開する工程は長いため、CORE/PROを販売開始後へ分離しました。全商品公開までを含める場合は22＋16＋12＝50分、環境Publishまでで約51分です。全工程が30分以内と偽って扱いません。今夜の販売開始の目標30分以内は、FE先行の22分で達成する計画です。
本人認証・決済口座・法定表示が未設定のアカウントでは、その設定と審査待ちの時間をこの見積もりへ含められません。Square未準備の場合も、ココナラFEの販売開始を先行させます。

省略した先行工程：CORE/PROの出品、動画制作、複数画像制作、環境Publish、広告出稿。必要な商品本文と画像は完成しており、ファイルを個別に探す工程はありません。

### アップロード画像（この文書で表示）

FE：/workspace/work-retirement-os/release/2026-10-10/images/FE.png

![FE販売画像](images/FE.png)

CORE：/workspace/work-retirement-os/release/2026-10-10/images/CORE.png

![CORE販売画像](images/CORE.png)

PRO：/workspace/work-retirement-os/release/2026-10-10/images/PRO.png

![PRO販売画像](images/PRO.png)
''')
(REL/'GO_LIVE_NOW.md').write_text('\n\n'.join(parts)+'\n',encoding='utf-8')
print('Created GO_LIVE_NOW.md; all input fields inline; 3 definitive posts; FE-first 22 minute plan')
