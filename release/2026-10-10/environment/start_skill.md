# Work Retirement OS 起動手順

既存チェックアウト /workspace/work-retirement-os を使用する。依頼がない限りGit worktreeを作成しない。
常駐サーバーやDBは不要。この環境は商品文章・画像・サンプル・納品ZIPの制作と検証用。

作業シェルで以下を実行する。

```bash
cd /workspace/work-retirement-os
export PYTHONPATH=/workspace/work-retirement-tools${PYTHONPATH:+:$PYTHONPATH}
python -c "import PIL; assert PIL.__version__ == '12.3.0'"
python -m unittest discover -s qa -p 'test_*.py' -v
```

機能テスト33件が完了することを確認する。画像フォントは /usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc。依存関係が不足する場合は保存したinstall_scriptを実行する。

販売素材の案内は release/2026-10-10/COPY_PASTE_INDEX.md。納品生成は automation/README.md。
顧客データはGit対象外のlocal_outputだけに置く。選択肢のみ使い、個人・勤務先・認証情報は保存しない。

既存の文章・アプリロジック・テスト・依存宣言・ロックファイルをオンボーディング目的で変更しない。qa.pyや再生成スクリプトは管理対象の成果物を更新するので、ユーザーが制作・更新を依頼した場合に実行する。通常の起動チェックは上の読み取りテストだけにする。
M365実接続、VBA実機実行、販売サイト公開はこの起動チェックでは検証しない。販売文章で実機未検証箇所を隠さない。
