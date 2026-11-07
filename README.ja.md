# claudeverse

[English](README.md)

Claude Code が使用量の上限に達すると、claudeverse が次のアカウントへ自動で切り替えます。

Claude のアカウントを最初に 1 回保存しておくだけです。そのあとは、Claude Code が使用量の上限で止まると、claudeverse が次のことをします。

- **いちばん早く使えるアカウントへ切り替えます。** 上限に達していないアカウントへ移ります。全部が上限なら、いちばん早くリセットされるアカウントへ移ります。
- **開いているセッションも全部一緒に移します。** 動いている Claude Code のセッションは、次の通信から新しいアカウントを使います。開き直しもログインも要りません。
- **止まったセッションを動かし直します。** 上限で止まったセッションに、続きとサブエージェントのやり直しを頼みます。Remote Control も入れ直します。（Windows）

あなたがすることはありません。手入れも要りません。ログインの期限が切れても、Claude Code の中で `/login` するだけです。新しいログインは claudeverse が保存します。画面下には、使用中のアカウントと 5 時間・1 週間の使用量が出ます。

## 動く環境

- Python 3.9 以上・標準ライブラリだけで動きます。
- Windows で試しています。macOS は試していません。

## 入れ方

```sh
pipx install git+https://github.com/234sainsa/claudeverse
claudeverse setup
```

pipx を使わない場合: `python claudeverse.py setup`

## はじめ方

`claudeverse setup` のメニューで:

1. **1** で、今のログインを名前を付けて保存します（例: `main`）。
2. **2** で、別のアカウントを足します（ブラウザでログインします。今のログインは変わりません）。持っているアカウントの数だけ足せます。
3. **3** で、画面下の表示と hook を入れます。自動の切り替えにはこれが要ります。

そのあと、Claude Code を開き直します。これで終わりです。

## コマンド

自動の切り替えには、これらは要りません。

| コマンド | すること |
|---|---|
| `claudeverse use <名前>` | 今すぐそのプロファイルへ切り替える |
| `claudeverse use --soonest` | 今すぐ、いちばん早く使えるアカウントへ切り替える |
| `claudeverse list` | 一覧（`*` が使用中） |
| `claudeverse usage [名前]` | 5 時間と 1 週間の使用量を見る |
| `claudeverse add <名前>` / `save <名前>` | 別のアカウントを足す / 今のログインを保存する |
| `claudeverse auto off` / `auto on [--threshold <パーセント>]` | 自動の切り替えを止める / 入れる（最初から入っています）。ふだんは Claude Code が本当に止まった時に切り替えます（100% になっても、しばらくは使えるため）。`--threshold 90` にすると、90% で早めに切り替えます。 |
| `claudeverse on-switch ...` | 切り替えた後にセッションへ打ち込むものを変える |
| `claudeverse install` / `uninstall` | 画面下の表示と hook を入れる / 外す |
| `claudeverse rename <今の名前> <新しい名前>` / `remove <名前>` | 名前を変える / 消す |

## 切り替えた後

動いているセッションは、次の通信から新しいログインを使います。開き直しは要りません。

Windows では、さらに切り替えの前から動いていた各セッションへ、次を打ち込みます（切り替えの直後に裏で行い、したことは `~/.claudeverse/events.log` に書きます）。

- `/remote-control`（アカウントが変わると Remote Control が切れるため）。
- 使用量の上限で止まっていたセッションには、続きを頼み、止まったサブエージェントのやり直しを頼む一言。Claude に届くのはこの一言だけです。

打ちかけの字は消えません。打つものは `claudeverse on-switch set ...`・`on-switch continue "<言葉>"`・`on-switch clear` で変えられます。

## 知っておくこと

- 保存したログインは約 1 か月使えます。切れたら、Claude Code の中で同じアカウントに `/login` するだけです。新しいログインは claudeverse が自動で保存します（切れたプロファイルへ `claudeverse use` した時は、その場でログインもできます）。
- データは `~/.claudeverse` に置きます。

## ライセンス

MIT
