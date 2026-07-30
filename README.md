# Inoreader → GitHub Pages 無料連携（修正版）

## 設置手順

1. GitHubで `inoreader-briefing` という公開リポジトリを作成します。
2. このZIPを展開します。
3. リポジトリの `Add file` → `Upload files` を開きます。
4. 展開したフォルダの中身をすべてアップロードし、`Commit changes` を押します。
5. `Settings` → `Pages` → `Build and deployment` で、`Source` を `GitHub Actions` にします。
6. `Actions` → `Update Inoreader feeds` → `Run workflow` → Branch `main` → `Run workflow` の順に押します。
7. 緑色のチェックになれば成功です。

通常の公開URL:
`https://<GitHubユーザー名>.github.io/inoreader-briefing/`

記事一覧:
`https://<GitHubユーザー名>.github.io/inoreader-briefing/latest.html`

JSON:
`https://<GitHubユーザー名>.github.io/inoreader-briefing/latest.json`

毎朝5時30分（日本時間）に自動更新します。
