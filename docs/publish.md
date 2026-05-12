# Publishing Later

GitHub authentication is not configured in this environment yet, so this repo is
prepared as a local git repository first.

After authenticating GitHub CLI:

```bash
gh auth login
cd ~/gigabyte-gpu-lcd
gh repo create gigabyte-gpu-lcd --public --source=. --remote=origin --push
```

If a remote repository already exists:

```bash
cd ~/gigabyte-gpu-lcd
git remote add origin git@github.com:<owner>/gigabyte-gpu-lcd.git
git push -u origin main
```

Before publishing, verify no generated payloads, previews, caches, or vendor
files are staged:

```bash
git status --short
git ls-files
```

Do not add extracted Gigabyte binaries, firmware blobs, personal logs, or local
machine-specific scratch files.

