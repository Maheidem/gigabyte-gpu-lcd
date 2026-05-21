# Publishing Checklist

The repository is published at:

```text
https://github.com/Maheidem/gigabyte-gpu-lcd
```

For future machines or forks, the initial publish flow is:

```bash
gh auth login
cd ~/gigabyte-gpu-lcd
gh repo create gigabyte-gpu-lcd --public --source=. --remote=origin --push
```

If the remote repository already exists and a local checkout only needs to be
connected:

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
