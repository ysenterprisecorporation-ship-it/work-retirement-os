# Work Retirement OS

AIを増やさない。仕事を減らす。

M365を使う企業担当者向けの業務診断・定型業務テンプレート商品です。販売開始用の文章、導入ガイド、サンプル、検証結果を管理します。

販売開始日：2026-10-10（日本時間）。公開操作と公開済み状態は区別します。

## 2026-10-11の実行結果

[現在の作業結果と一括原稿](release/2026-10-11/EXECUTION.md)。SNSで自力集客した新規顧客は既存Square直販へ案内する。ココナラ起点の顧客はココナラ内で購入・決済・納品する。SNSからココナラへ誘導しない。 現在、実Square URLと購入後納品は未確認です。

## 販売開始用成果物

[出品全文・今夜の投稿・設定を統合したGO LIVE](release/2026-10-10/GO_LIVE_NOW.md)

[リリース判定](release/2026-10-10/RELEASE_CHECK.md) / [貼り付け索引](release/2026-10-10/COPY_PASTE_INDEX.md) / [公開操作](release/2026-10-10/HUMAN_ACTIONS.md) / [全件QA](qa/full_qa.md)

FE 3,000円、CORE 10,000円、PRO 40,000円。顧客専用開発や設定代行は含みません。商品の価格・範囲はbusiness/catalog.jsonを正本とします。

## 開発・再生成

Python 3.10以上。サンプルは標準ライブラリのみ。画像制作とQAはPillow 12.3.0を使います。

```bash
python -m pip install --upgrade --target /workspace/work-retirement-tools -r requirements-dev.txt
export PYTHONPATH=/workspace/work-retirement-tools${PYTHONPATH:+:$PYTHONPATH}
python -m unittest discover -s qa -p 'test_*.py' -v
python automation/qa.py
```

[自動化・納品生成手順](automation/README.md)。この既存チェックアウトを使い、別worktreeは作成しません。顧客選択肢はGit対象外のlocal_outputに置き、実名・勤務先・認証情報は保存しません。

## Issue #1 Square直販

[決済・支払検証・メール納品のCLI手順](scripts/README.md)。[実施状況](release/2026-10-10/SQUARE_LAUNCH_STATUS.md)。既存決済リンクを最優先し、実URLと実納品が未検証ならSNS公開を保留します。秘密値は環境設定のみへ登録。
