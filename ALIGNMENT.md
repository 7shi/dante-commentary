# 解説記事アライメント作業手順書（ALIGNMENT.md）

解説記事（`<canticle>/<NN>.md`）と翻訳テキスト（`<canticle>/<NN>.txt`）・原文コーパスの整合（アライメント）をとるための点検・修正手順書。

---

## 1. 目的と背景

[PLAN.md](PLAN.md) で構想されている「原文・全行対訳に対訳範囲ごとの解説を埋め込んだ統合ページ」を生成する際、各解説セクションが担当する行範囲は記事内の引用行番号に基づいて決定される。引用のない行範囲は「解説なしの対訳ブロック」として補完される。

しかし、解説記事の本文中で「〇〇〜〇〇行では」と行に言及しているにもかかわらず引用ブロック（`>`）が欠落している場合、機械的に処理すると**「言及行の対訳が解説の後に解説なしで挟まれる」**など、解説と対訳の対応関係にズレが生じてしまう。

本作業では、全カントの解説記事を1ファイルずつ精査し、対訳と解説の対応関係を正しく整える。

---

## 2. チェック項目と判断基準

各ファイルについて、以下の3点を確認・是正する。

### ① 本文中の行言及と引用の突き合わせ
解説本文中で「〜行では」「第〜行」と言及されている箇所を洗い出す。
- **同一場面の解説なのに引用が抜けている場合**:
  - 原文および `.txt` から引用ブロックを作成して該当解説の直前に挿入する。
  - 引用追加によって自明になった文頭の行番号言及（例:「37〜43行では、」「88〜90行でダンテは、」）は削除・整理する。
- **後段の描写を先取りして言及している場合**（例: 地獄篇第1歌の「後の97〜99行では…」）:
  - 先取り言及は**そのまま維持**する（引用ブロックは追加しない）。

### ② セクション順序（時系列）の確認
各セクションの引用行番号が、原文の行順（時系列）通りに並んでいるか確認する。
- **行順の逆転がある場合**（例: 地獄篇第1歌の旧 `## 2` [10〜12行] と 旧 `## 3` [7〜9行]）:
  - セクションの並び順を原文の時系列順に入れ替え、見出し番号（`## 2．...`, `## 3．...`）を正しく振り直す。

### ③ 引用フォーマットの統一
追加する引用ブロックは、以下の canonical layout に完全準拠させる。
- `> 行番号 原文  `（末尾に半角スペース2つでMarkdown改行）
- `> （日本語訳）`（`.txt` の該当行の訳文を全角括弧で囲む）
- 各行の間は `>` のみの空行で区切る。
- 引用ブロックと解説本文の間は空行で区切る。

```markdown
> 88 vedi la bestia per cu' io mi volsi;  
> （私を引き返させた、あの獣をご覧ください。）
>
> 89 aiutami da lei, famoso saggio,  
> （名高い賢者よ、あの獣から私をお救いください、）
>
> 90 ch'ella mi fa tremar le vene e i polsi».  
> （あれは、私の血管も脈も震えさせるのです。）

同時に、この文学的な敬意は、切実な救援要請に続きます。ダンテは、自分を引き返させた獣から助けてほしいと願います。...
```

---

## 3. 1カントあたりの標準作業フロー

### Step 1: 現状の引用と行言及を調査する

対象ファイル（例: `astra/inferno/02.md`）の引用行および本文中の行言及を以下のワンライナーで調査する。

```bash
uv run python -c "
import re, sys
from pathlib import Path

path = Path('astra/inferno/02.md')
text = path.read_text()
sections = re.split(r'(^## .+)', text, flags=re.M)
quote_re = re.compile(r'^>\s*(\d+)\s+', re.M)
mention_re = re.compile(r'(\d+)(?:〜|～|-|–)?(\d+)?行')

print(f'=== {path} ===')
for i in range(1, len(sections), 2):
    h = sections[i].strip()
    b = sections[i+1]
    quotes = [int(m.group(1)) for m in quote_re.finditer(b)]
    mentions = []
    for line in b.splitlines():
        if line.lstrip().startswith('>'):
            continue
        for m in mention_re.finditer(line):
            s = int(m.group(1))
            e = int(m.group(2)) if m.group(2) else s
            mentions.append((f'{s}-{e}', line.strip()))
    print(h)
    print(f'  Quotes: {quotes}')
    if mentions:
        print('  Mentions:')
        for r, snippet in mentions:
            print(f'    [{r}] {snippet[:60]}...')
"
```

### Step 2: 必要な引用行の原文と訳文を取得する

引用を追加する必要がある行番号（例: 102行）について、原文と訳文を確認する。

```bash
uv run python -c "
from dante_corpus import ref
from pathlib import Path

canticle, canto = 'inferno', 2
lines = ref(f'{canticle} {canto}')
txt_lines = Path(f'astra/{canticle}/{canto:02d}.txt').read_text().splitlines()

# 対象行を指定（例: 100〜105行）
target_range = range(100, 106)
for no in target_range:
    orig = lines[no - 1].text
    trans = txt_lines[no - 1] if no - 1 < len(txt_lines) else ''
    print(f'> {no} {orig}  ')
    print(f'> （{trans}）')
    print('>')
"
```

### Step 3: Markdownファイルを編集する

1. 対象箇所の直前に引用ブロックを挿入する。
2. 本文中に「〜行では」などの言及があれば、自明となった導入部を削除・簡潔化する。
3. セクション順序の逆転があれば並び替え、見出し番号を修正する。

### Step 4: 検証・フォーマット正規化

編集後、以下のコマンドでフォーマットと文体を検証する。

```bash
# 1. 引用フォーマットの正規化・検査
uv run scripts/normalize_md.py -d astra

# 2. 文体（です・ます調）の検査
uv run scripts/check_style.py astra/inferno/02.md

# 3. 差分の最終確認
git diff astra/inferno/02.md
```

---

## 4. 進捗管理

### 地獄篇 (Inferno) - 全34歌

| カント | 状態 | 備考 |
|---|---|---|
| 01 | 済 | 37〜43, 88〜90, 106〜111, 124〜126行追加、2/3逆転修正 |
| 02 | 未 | |
| 03 | 未 | |
| 04 | 未 | |
| 05 | 未 | |
| 06〜34 | 未 | |

### 煉獄篇 (Purgatorio) - 全33歌

| カント | 状態 | 備考 |
|---|---|---|
| 01〜33 | 未 | |

### 天国篇 (Paradiso) - 全33歌

| カント | 状態 | 備考 |
|---|---|---|
| 01〜33 | 未 | |
