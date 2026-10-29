# Publishing this Project to GitHub (Windows + VS Code)

This guide takes you from "no Git installed" to "project visible on my own GitHub page", and then shows how to push later changes.
All commands are for the **VS Code terminal** (PowerShell) opened in the project folder (the folder that contains `app.py`).

> **Replace the placeholders.** Anywhere you see `YOUR-USERNAME` or `YOUR-REPOSITORY`, type **your own** GitHub username and the repository name you create in step 3.
> For example, if your username is `asha-rao` and the repository is `youtube-topic-graph-analytics`, the URL becomes
> `https://github.com/asha-rao/youtube-topic-graph-analytics.git`. Do not type the placeholders literally.

> **Security rules**
> * Never put API keys, passwords, tokens or private data in files you commit.
> * Never paste a password or access token into a chat (including with an AI assistant), a README, or code. If a sign-in window appears, type credentials only there.
> * This project needs **no** secrets. The files `.env.example` and `.streamlit/secrets.toml.example` contain placeholders only.

## 1. Install Git and verify
1. Download **Git for Windows** from <https://git-scm.com/download/win> and run the installer. The default options are fine; keep **Git Credential Manager** selected (it handles GitHub sign-in).
2. **Close and reopen VS Code** (so it sees the new program), then open the terminal (`` Ctrl+` ``) and run:
   ```powershell
   git --version
   ```
   You should see something like `git version 2.xx.x.windows.x`. If you get *"git is not recognized"*, see the troubleshooting section.

## 2. Tell Git who you are (once per computer)
```powershell
git config --global user.name "Your Name"
git config --global user.email "your-email@example.com"
git config --global init.defaultBranch main
git config --global --list
```
Use the name you want shown on commits. For the email you can use your GitHub private "noreply" address
(GitHub > Settings > Emails > tick *Keep my email addresses private*, then copy the address shown).

## 3. Create the repository on GitHub
1. Sign in (or create a free account) at <https://github.com>.
2. Click **+** (top right) > **New repository**.
3. **Repository name:** for example `youtube-topic-graph-analytics`. Add a short description if you like.
4. Choose **Public** or **Private**.
5. **Leave all "Initialize this repository" boxes UNTICKED** - no README, no .gitignore, no licence. The project already has them, and ticking them causes a "rejected push" later.
6. Click **Create repository**. Keep the page open; you will need its HTTPS address, which looks like `https://github.com/YOUR-USERNAME/YOUR-REPOSITORY.git`.

## 4. Pre-flight check: make sure no secrets are in the folder
In the project folder run:
```powershell
# 1) These two files must NOT exist (only the *.example versions should)
Test-Path .env
Test-Path .streamlit\secrets.toml

# 2) Look for text that resembles real keys or tokens (no output = good)
Get-ChildItem -Recurse -File -Force |
  Where-Object { $_.FullName -notmatch '\\(\.venv|\.git|__pycache__|\.pytest_cache)\\' } |
  Select-String -Pattern 'AIza[0-9A-Za-z_-]{30,}','ghp_[A-Za-z0-9]{30,}','password\s*='
```
Both `Test-Path` lines should print `False`. If a real key ever appears, delete it from the file and revoke/regenerate it with the provider before continuing.

## 5. Initialise Git, stage files and **review** them
```powershell
git init
git add .
git status
```
**Read the `git status` list carefully before committing.**

*You should see* (under "Changes to be committed" / "new file"): `app.py`, `README.md`, `requirements.txt`, `pytest.ini`, `.gitignore`, `.env.example`,
`.streamlit/config.toml`, `.streamlit/secrets.toml.example`, `.vscode/settings.json`, `.vscode/extensions.json`, `data/youtube_videos.csv`,
`scripts/generate_sample_data.py`, the files in `src/`, `tests/` and `docs/`.

*You must NOT see:* `.venv/` (or any `Lib/`, `Scripts/`, `site-packages` paths), `__pycache__/`, `.pytest_cache/`, `.env`, `.streamlit/secrets.toml`, any `*.zip`, `*.log`, API keys, passwords or private data.

Double-check that the important patterns are ignored (each line should print the matching rule from `.gitignore`; a path that does not exist on your computer simply prints nothing):
```powershell
git check-ignore -v .venv .env .streamlit/secrets.toml
```
If something that should not be committed is listed, unstage it:
```powershell
git restore --staged PATH-TO-FILE          # one file
git rm -r --cached .venv                   # a whole folder that was staged by mistake
```
then add the missing pattern to `.gitignore`, run `git add .` and `git status` again.

## 6. Create the first commit
```powershell
git commit -m "Initial commit: YouTube graph analytics project"
```
If Git says *"Author identity unknown"*, repeat step 2 and commit again. Check with `git log --oneline`.

## 7. Connect to your GitHub repository
```powershell
git branch -M main
git remote add origin https://github.com/YOUR-USERNAME/YOUR-REPOSITORY.git
git remote -v
```
`git remote -v` should print your URL twice (fetch and push). If the URL has a typo, fix it with:
`git remote set-url origin https://github.com/YOUR-USERNAME/YOUR-REPOSITORY.git`.

## 8. Push
```powershell
git push -u origin main
```
A sign-in window from **Git Credential Manager** normally opens - choose **Sign in with your browser** and approve. Do not paste your GitHub password anywhere
(GitHub no longer accepts account passwords for Git). Afterwards refresh your repository page: you should see the files, the README rendered with its diagram,
and **no** `.venv` folder.

**Only after you see your files on GitHub is the project published.** Until then it exists only on your computer.

## 9. Making changes later
```powershell
git status                       # what changed?
git add .                        # stage everything (or: git add src/graph_builder.py)
git status                       # review again - no secrets, no .venv
git commit -m "Describe what you changed"
git push
```
Useful extras: `git log --oneline` (history), `git diff` (see unstaged edits), `git pull` (download changes if you also edit on another computer or on github.com).
Write commit messages that say *what and why*, e.g. `Add similarity threshold explanation to README`.

## 10. Alternative: VS Code Source Control (no typing)
1. Click the **Source Control** icon in the left bar (`Ctrl+Shift+G`).
2. If the folder is not a repository yet, click **Initialize Repository**.
3. Under **Changes**, review the file list. Same rule as step 5: no `.venv`, `.env`, secrets or caches should appear (they are ignored by `.gitignore`). Hover a file and click **+** to stage it, or click **+** next to "Changes" to stage all.
4. Type a message such as `Initial commit: YouTube graph analytics project` in the box and click **Commit**.
5. First publish: click **Publish Branch**, sign in to GitHub when asked, and choose a repository name and **Public/Private**. VS Code creates the repository and pushes. (If you already created an empty repository in step 3, use the terminal commands from step 7 to connect it, then click **Sync Changes** or **Push**.)
6. Later changes: edit files > stage (**+**) > write a message > **Commit** > **Sync Changes** (or **Push** from the `...` menu).

## 11. Troubleshooting
| Message or problem | What it means and how to fix it |
|---|---|
| `git is not recognized...` | Git is not installed or VS Code was open during install. Close all VS Code windows, reopen, try `git --version` again. If it still fails, rerun the installer and choose "Git from the command line and also from 3rd-party software". |
| `fatal: not a git repository` | You are in the wrong folder or have not run `git init`. Use `cd` to the folder containing `app.py`, then `git init`. |
| `Author identity unknown` / `Please tell me who you are` | Run the two `git config --global user.name/user.email` commands from step 2, then `git commit` again. |
| `fatal: remote origin already exists.` | A remote is already set. See it with `git remote -v`. Change it: `git remote set-url origin https://github.com/YOUR-USERNAME/YOUR-REPOSITORY.git`. Or delete and re-add: `git remote remove origin` then `git remote add origin ...`. |
| `error: src refspec main does not match any` | There is no commit yet (or the branch has another name). Run `git status`, make the commit (step 6), then `git branch -M main` and push again. `git branch` shows the current branch name. |
| `remote: Repository not found.` / `fatal: repository ... not found` | The URL is wrong, the repository does not exist yet, it is private and you are signed in with a different account, or the placeholders were not replaced. Check `git remote -v` against the address shown on your GitHub repository page. |
| `Authentication failed` / `Support for password authentication was removed` | GitHub does not accept passwords for Git. Remove stale credentials: Windows **Credential Manager** > **Windows Credentials** > delete entries starting with `git:https://github.com`, then push again and sign in through the browser window. If you must use a personal access token, create it yourself in GitHub > Settings > Developer settings, give it the minimum permission (repository contents), paste it **only** into the sign-in prompt, never into files or chat, and never commit it. |
| `! [rejected] main -> main (fetch first)` or `non-fast-forward` | The GitHub repository contains commits you do not have locally (often because a README or licence was ticked at creation). Fix: `git pull origin main --allow-unrelated-histories`. If Git reports a conflict (usually `README.md`), open the file, keep the version you want, remove the `<<<<<<<` `=======` `>>>>>>>` marker lines, then `git add .` and `git commit -m "Merge remote changes"`, then `git push`. Avoid `git push --force`: it overwrites the remote history and is only safe on a brand-new repository whose contents you do not need. |
| `failed to push some refs` | Read the lines above it - it is usually one of the two rows above (rejected / authentication). |
| `warning: LF will be replaced by CRLF` | Harmless line-ending notice on Windows. You can ignore it. |
| I committed `.venv`, caches or a secret by mistake **before** pushing | Remove it from tracking: `git rm -r --cached .venv` (or the file), make sure `.gitignore` lists it, then `git commit --amend` (if it was the last commit) or make a new commit. For a secret: also **revoke/regenerate the key**, because it is stored in the commit history. |
| I **pushed** a secret | Treat it as exposed. Immediately revoke or regenerate the key with the provider. Then remove it from history with a tool such as `git filter-repo` (see GitHub Docs: "Removing sensitive data from a repository") - deleting the file in a new commit is not enough. |
| VS Code shows thousands of changes | The `.venv` folder is not ignored. Check that `.gitignore` is in the project root and contains `.venv/`; if files were already staged, run `git rm -r --cached .venv`. |
| README diagram does not render on GitHub | GitHub renders Mermaid in README files automatically. Make sure the code fence starts with three backticks followed by the word `mermaid`. |

## 12. Final checklist
- [ ] `git --version` works
- [ ] `git config --global --list` shows your name and email
- [ ] Empty GitHub repository created with **no** README / .gitignore / licence
- [ ] `Test-Path .env` and `Test-Path .streamlit\secrets.toml` both print `False`
- [ ] `git status` reviewed - no `.venv`, `__pycache__`, `.env`, secrets, keys, passwords or private data
- [ ] First commit created
- [ ] `git remote -v` shows **your** username and repository (placeholders replaced)
- [ ] `git push -u origin main` succeeded and the files are visible on github.com
- [ ] Put your repository link into `docs/project_report.md`
