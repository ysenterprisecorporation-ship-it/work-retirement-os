"""Embed existing sales assets and the Issue #1 checkout/delivery gates."""
from pathlib import Path
import json
ROOT=Path(__file__).resolve().parents[1]
REL=ROOT/'release/2026-10-10'
CAT=json.loads((ROOT/'business/catalog.json').read_text(encoding='utf-8'))
parts=[]
def add(value):parts.append(value.strip())
def text(channel,tier,name):return (REL/channel/tier/name).read_text(encoding='utf-8').strip()
def block(label,value):return f'#### {label}\n\n```text\n{value}\n```'
CC_FIELDS=[('サービスタイトル','title.txt'),('キャッチコピー','catchcopy.txt'),('サービス説明','description.txt'),('購入にあたってのお願い','purchase_notes.txt'),('FAQ','faq.txt'),('購入後最初の返信文','first_reply.txt'),('納品メッセージ','delivery_message.txt')]
SQ_FIELDS=[('商品名','product_name.txt'),('短い説明','short_description.txt'),('商品説明','full_description.txt'),('購入後メッセージ','first_reply.txt'),('納品メッセージ','delivery_message.txt'),('返金方針','refund_policy_draft.txt')]
def cc(tier):
 c=CAT[tier]
 return f"価格：{c['price']:,}円。納期：全回答受領後{c['days']}日以内。即購入ON、見積り必須OFF、有料オプション・定期購入・ビデオチャットOFF。FE同時受付上限10件。推奨カテゴリ：業務効率化・自動化に相当する相談カテゴリ（現在の分類名は未実確認）。画像：{REL}/images/{tier}.png。返信と納品文は取引の実際のタイミングにトークルームで使用。\n\n"+'\n\n'.join(block(label,text('coconala',tier,name)) for label,name in CC_FIELDS)
def sq(tier):
 c=CAT[tier]
 return f"価格：{c['price']:,}円、追加税・配送・チップ・定期課金なし。納期：全回答受領後{c['days']}日以内。画像：{REL}/images/{tier}.png。購入者の決済登録メールへ回答依頼を送り、選択肢回答の受信と診断承認後にZIPを添付送信。Square自身の自動ZIP配布を前提にしない。\n\n"+'\n\n'.join(block(label,text('square',tier,name)) for label,name in SQ_FIELDS)
SNS={}
for platform,filename in [('X','x_posts.txt'),('Instagram','instagram_posts.txt'),('Facebook','facebook_posts.txt')]:
 first=(REL/'sns'/filename).read_text(encoding='utf-8').split('\n\n---\n\n')[0]
 body='AIを増やさない。仕事を減らす。\n'+first.split('キャプション：',1)[1].strip() if platform=='Instagram' else first.split('\n',1)[1].strip()
 SNS[platform]=body
 for folder in [ROOT/'sales/sns',REL/'sns']:(folder/f'tonight_{platform.lower()}.txt').write_text(body+'\n',encoding='utf-8')
def sns_full():return '\n\n'.join(block(platform+'：公開保留の草稿',body) for platform,body in SNS.items())
add('''# GO LIVE NOW — Issue #1

## A. RELEASE STATUS

BLOCKED（Square直販とSNS）。実装・販売素材は完成。Issue #1ではココナラFEは公開済み（サービスID4445208）と報告されている。Codex自身は販売者UIへログインしていない。
Squareトークン、送信APIキー、検証済み送信元と受信可能な返信先の提供が必要。実URLと実購入後の回答依頼・ZIP受信は未検証。未検証のリンクや架空URLをSNSへ掲載しない。

## B. 今日公開する順番

### B1. ココナラFE — 既に公開済み

再出品しない。サービスID4445208、価格3,000円、回答受領後3日、同時受付上限10件。集客はサービス内検索のみ。公開操作は不要。以下は既存サービスの入力・取引用完成文面。
''')
add(cc('FE'))
add('''### B2. Square FE — 既存決済リンクを優先

新しいストアは作らない。既存の民泊AI、2,980円、他リンクを変更・停止しない。CodexがAPIで全ページと注文を照合し、商品名・税込総額3,000円JPY・単発決済が一致するリンクを再利用。一致なしの場合だけapplyで1件を冪等作成する。複数一致、価格矛盾、店舗が複数で未選択の場合は自動作成しない。

人間操作1：このチャットの環境設定→保存済み認証・変数欄。Square Developer Dashboardの既存アプリProduction credentialsからSQUARE_ACCESS_TOKENを安全なシークレット欄へ登録（リンク・注文・支払い・店舗・顧客の読み取りと決済リンク作成権限）。既存のResend API Keysから送信・ドメイン・送信履歴を扱えるRESEND_API_KEYを同様に登録。DELIVERY_FROMにResendで検証済みドメインの送信元、DELIVERY_REPLY_TOに実際に受信できる販売者返信先を環境変数欄へ入力。通常のスクリプト・リポジトリを貼り直す必要はない。保存→Publish。既存送信ドメインが未設定の場合はResend DomainsのDNS設定とドメイン所有者の認証が先に必要。認証情報をチャットへ貼らない。

設定後の探索・必要な作成・送信・ZIP生成はCodexが実行する。配送・チップ・定期課金・クーポン・追加税を使わず、3,000円。購入画面の必須同意2欄に商品範囲・利用料別・回答後3日・返金条件を表示し、販売者返信先を連絡先へ設定する。既存リンクに同等の表示がなければ変更せず、宣伝を保留する。
納品条件、返金方針、法定表示は既存の販売者アカウントに実情報で登録されている必要がある。購入画面・法定表示の実表示はAPI照合だけで検証済みとは扱わない。
''')
add(sq('FE'))
add('''### B3. SNS — 実決済・納品検証後だけ公開

人間操作2：取得された本番Square決済ページを購入者として開く。商品・総額3,000円・下記の範囲と返金条件・販売者連絡先・法定表示を購入画面で読み、検証を承認する場合だけ決済ボタンを押す。実課金3,000円であり、無断でCodexがカードを操作しない。届いた4問メールに選択肢だけ返信し「送信」。Codexがその回答から診断を作成・承認後にZIPを送る。受信したZIPを開き、欠損なく利用できたかをこの会話へ回答する。配送事業者のdeliveredだけでは人間がZIPを開いた証明にならない。

この結果を踏まえCodexがproductionの実URL入り投稿をlocal_output/sns_liveへ出力する。現時点では実URL未取得なので以下は公開保留。プロフィールのリンク先をその本番URLへ設定してから、X「ポストする」、Instagram「シェア」、Facebook「投稿」。画像は3媒体とも release/2026-10-10/images/FE.png。広告・予約・自動DMはOFF。SNSの公開操作は後続作業であり、今は依頼しない。
''')
add(sns_full())
add('''### B4. ココナラCORE/PRO — 後日に分離

今回の最短導線には追加しない。完成文面を保持する。追加する場合の価格はCORE10,000円、PRO40,000円。個別開発は含めない。
''')
for tier in ['CORE','PRO']:add(cc(tier))
add('## C. ココナラFE 完全入力セット\n\n既存サービス用。公開済みFEの再出品は不要。')
add(cc('FE'))
add('## D. Square 完全入力セット\n\n外部SNSからの新規流入専用。FE以外は今回登録・決済リンク作成しない。商品名と価格と納期、回答依頼・納品文を以下に全文保持する。')
for tier in CAT:add('### Square '+tier+'\n\n'+sq(tier))
add('## E. SNS 今夜投稿するもの\n\n各媒体の1本を選定済み。実URLと納品検証が成立するまで公開しない。リンク先を創作しない。')
add(sns_full())
add('''## F. 環境設定

Square直販にはB2の秘密変数2つとメール変数2つが必要。既存のインストール・起動・リポジトリ設定を保持して必要条件をドラフト保存する。ドラフト保存と実環境への適用は別。環境設定→認証・変数の入力→保存→Publishで適用する。現行UIの「要確認」表示やPublish完了をこの会話から断定しない。
購入後監視はpoll --watchで実行可能だが、クラウド作業環境の停止中は動作しない。恒久運用のホストは今回未配備。常時完全自動受付や自動返金は約束しない。

## G. 人間総作業時間

ココナラFEは公開済みなので販売開始操作0分。既存のSquareアプリ・Resend検証済み送信ドメイン・受信箱がある場合、環境設定入力約8分＋購入画面と返信・ZIP受信約7分＝操作約15分。実課金への同意、メール待機、DNS認証、アカウント審査、Publish処理、Codexによる診断納品待ちの経過時間は含まない。未設定なら30分以内とは保証しない。
CORE/PROの出品、新規ストア、画像再制作、広告、SNS公開を今回の人間作業から除き、既存資産で最短化した。
''')
for tier in CAT:add(f'{tier}画像：{REL}/images/{tier}.png\n\n![{tier}販売画像](images/{tier}.png)')
(REL/'GO_LIVE_NOW.md').write_text('\n\n'.join(parts)+'\n',encoding='utf-8')
print('Created Issue #1 guide: existing FE, existing Square links, verified delivery gate')
