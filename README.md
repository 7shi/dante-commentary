# dante-commentary

ダンテ『神曲』の各カントについて、寓意や背景を解説し、イタリア語原文からの引用を交えた日本語の解説記事（Markdown）を生成します。さらに、そのカントの全行に対応する日本語の翻訳テキスト（行ごとに1行の訳文）も生成します。

**[公開ページ](https://7shi.github.io/dante-commentary/)** — 原文と日本語訳を1行ずつ並べた対訳形式で、該当する行範囲に解説を組み込んで掲載しています。三篇（地獄篇・煉獄篇・天国篇）ごとに、全カントへのリンクを備えた索引ページも用意しています。

> [!NOTE]
> 本リポジトリの解説記事・翻訳はすべて機械生成（LLM）によるもので、専門の翻訳者や研究者による校閲は受けていません。誤りや誤訳が含まれている可能性があるため、参考用としてご利用ください。

原典テキストは [dante-corpus](https://github.com/7shi/dante-corpus) 経由で取得し、LLMへのリクエストには[llm7shi](https://github.com/7shi/llm7shi) を使用します。

## 依存プロジェクト

本プロジェクトは以下の姉妹リポジトリに関連しています。

- [dante-corpus](https://github.com/7shi/dante-corpus) — 共通のコーパスライブラリおよび軽量CLI。正規化されたイタリア語原文、形態素トークン、引用範囲ツリーを `dante_corpus` API を通じて問い合わせ可能なデータベースとして提供します。**【必須】** 本プロジェクトは editable path dependency として各カントのテキストをここから読み込みます。
- [dante-gemini-25](https://github.com/7shi/dante-gemini-25) — Gemini 2.5 Pro による『神曲』全篇の英訳・和訳プロジェクト。翻訳をセグメント単位で行うための場面境界データを持っています。本プロジェクトにはそのデータが `segments/` としてすでに取り込まれているため、**実行時には不要**です（詳細は[セグメント分割](#セグメント分割)を参照）。

### 準備

`dante-commentary` は `dante-corpus` を editable path dependency（`../dante-corpus`）として利用するため、両リポジトリを同一の親ディレクトリ直下に並べて配置する必要があります。`uv` がインストールされていることを確認した上で、次のようにセットアップしてください。

```bash
git clone https://github.com/7shi/dante-corpus.git
git clone https://github.com/7shi/dante-commentary.git
make -C dante-corpus
cd dante-commentary
uv sync
```

ディレクトリ構成は以下のようになります。

```
your-workspace/
├── dante-corpus/       # 原文テキスト、トークン（dante_corpus API経由で読み込み）
└── dante-commentary/   # 本リポジトリ
```

## ファイル構成

- `scripts/` — 生成・後処理・検査用スクリプト一式
- `templates/` — GitHub Pages 公開用の静的サイトビルダー（Jinja2テンプレート・`build.py`・`deploy.sh`）。詳細は [templates/README.md](templates/README.md) を参照
- `segments/` — 各カントを場面の切れ目で分割した境界データ（`fix_brackets.py` で使用。`inferno.jsonl`、`purgatorio.jsonl`、`paradiso.jsonl`）
- `fable/`、`astra/`、`gemma4-26b/` — モデル別のサンプル出力（サイトは `astra/` を使用）

解説記事と翻訳テキスト・原文コーパスのアライメント点検・修正手順は [ALIGNMENT.md](ALIGNMENT.md) を参照してください。修正は Gemini 3.8 Flash で行います。

## スクリプト一覧

用途別に分類しています。各スクリプトのコマンドライン引数や処理内容の詳細は [scripts/README.md](scripts/README.md) を参照してください。

**生成**

- `scripts/generate.py` — 解説記事および翻訳テキストの生成スクリプト（カント単位で処理し、セグメント分割は不使用）

**後処理**

- `scripts/add_conclusion.py` — 解説記事に「結び」セクションが欠けている場合に追記
- `scripts/fix_brackets.py` — 翻訳テキストの鍵括弧を原文に合わせて補正（セグメント単位の後処理）
- `scripts/fix_quote_blocks.py` — 解説記事の引用ブロックを原文コーパスと訳文テキストから再構成し正規の形式に統一

**検査**

- `scripts/check_style.py` — 解説記事が「です・ます調」か「だ・である調」かを判定（調査後、Gemini 3.8 Flash により「です・ます調」に統一）
- `scripts/check_quote_blocks.py` — 解説記事の各 `##` セクションに含まれる引用ブロック数を検査
- `scripts/analyze_canto.py` — 解説記事のセクション見出し、引用行、本文冒頭、コーパス総行数を抽出し一覧表示（行範囲の照合・確認用）

## サイトの生成・公開

```bash
make build   # dist/ に静的サイトを生成
make serve   # dist/ をローカルで確認（http://localhost:8000）
make deploy  # build の上で gh-pages ブランチへ公開
```

詳細は [templates/README.md](templates/README.md) を参照してください。
