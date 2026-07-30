# Inoreader → GitHub Pages 無料連携

Inoreaderの次の2フォルダを毎朝取得し、直近30時間の記事を重複除去して静的HTMLとJSONにします。

- `00_毎日確認`
- `06_左派ニュース・社会主義戦略`

OpenAI API、n8n Cloud、Gmailは使用しません。

## 費用

公開リポジトリで標準のGitHub-hosted runnerを使うGitHub Actionsは無料です。  
この構成は1日1回、数分以内の実行を想定しています。

## 重要な公開範囲

GitHub PagesをChatGPTの定期タスクから読ませるため、リポジトリと生成ページを公開します。

公開されるもの:

- 2つのInoreader出力フィードURL
- フィードに収録された直近30時間の記事タイトル、URL、本文または概要

InoreaderのパスワードやAPIキーは使いません。

## 設置手順

### 1. GitHubで公開リポジトリを作る

1. GitHubへログイン
2. `New repository`
3. Repository nameを例として `inoreader-briefing`
4. `Public`を選択
5. `Create repository`

### 2. このフォルダの内容をアップロードする

GitHubのリポジトリ画面で:

1. `Add file`
2. `Upload files`
3. このZIPを展開した中身を、フォルダ構造を保ったままアップロード
4. `Commit changes`

最低限、次の構造を維持します。

```text
.github/workflows/update-feed.yml
scripts/fetch_feeds.py
docs/index.html
requirements.txt
README.md
```

### 3. GitHub Actionsを初回実行する

1. リポジトリの `Actions` タブ
2. `Update Inoreader feeds`
3. `Run workflow`
4. 終了後、リポジトリの `docs` に次のファイルが作られていることを確認
   - `latest.json`
   - `latest.html`
   - `status.json`

失敗した場合は、Actionsの実行ログをChatGPTへ貼ってください。

### 4. GitHub Pagesを有効にする

1. `Settings`
2. 左側の `Pages`
3. `Build and deployment`
4. Sourceを `Deploy from a branch`
5. Branchを `main`
6. Folderを `/docs`
7. `Save`

公開URLは通常、次の形です。

```text
https://<GitHubユーザー名>.github.io/inoreader-briefing/latest.html
https://<GitHubユーザー名>.github.io/inoreader-briefing/latest.json
```

### 5. ChatGPT定期タスクのURLを差し替える

GitHub Pagesの公開URLが確定したら、このチャットへ貼ってください。

現在の「Inoreader朝刊」タスクを、Inoreaderへの直接アクセスではなく、静的な次のページを読む設定へ変更します。

```text
https://<ユーザー名>.github.io/inoreader-briefing/latest.html
```

HTMLを第一候補、JSONを補助候補にします。

## 実行時刻

GitHub Actionsは毎日05:30（日本時間）に実行します。

GitHub ActionsのcronはUTCで書くため、設定値は次のとおりです。

```yaml
- cron: "30 20 * * *"
```

ChatGPTの朝刊タスクは6時台のままでよいため、GitHub Pagesの更新後に取得できます。

## 生成ファイル

- `docs/latest.html`
  - 人間とChatGPTが読みやすい静的ページ
- `docs/latest.json`
  - 構造化データ
- `docs/status.json`
  - フィード取得の成否を確認する軽量データ

## 要約について

このGitHub Actionsは記事の収集・整理だけを行います。AI要約はChatGPTの定期タスクで行うため、OpenAI API料金は発生しません。

## 時刻の扱い

フィードに公開日時がある記事は、直近30時間に限定します。  
公開日時がない記事は取りこぼし防止のため残し、`date_missing: true`を付けます。

## 手動更新

Actionsの `Run workflow` を押せば、予定時刻を待たずに更新できます。
