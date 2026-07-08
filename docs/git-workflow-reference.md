# Git Workflow Reference

A breakdown of the git setup we walked through for the `weather-etl` project, in order, with the reasoning behind each step. Use it as a checklist for future projects.

---

## Key idea to remember

**Git ≠ GitHub.** Git runs on your machine and records your project's history — no internet or account needed. GitHub is a website that *hosts a copy* of a git repo in the cloud. Everything below is pure local git; GitHub is a separate, later step.

The core loop, once set up, is always: **change files → stage what belongs together → commit with a message explaining why.**

---

## What we did, step by step

### 1. Install Git (Windows)
Git wasn't installed (the `'git' is not recognized` error). Installed via either:
- `winget install --id Git.Git -e --source winget`, or
- the official installer from git-scm.com/download/win

**Gotcha:** after installing, open a *brand new* terminal — a terminal only reads the PATH when it starts, so the old window won't see git.

Verify:
```
git --version
```

### 2. Set your identity (one-time, per machine)
Git stamps every commit with who made it.
```
git config --global user.name "Justin"
git config --global user.email "you@example.com"
```
No output = success. Use the email you'll use for GitHub later.

### 3. Point the terminal at the project folder
Git acts on whatever folder the terminal is "in." Always confirm first:
```
pwd
```
Should end in `weather-etl`. If not, `cd` into it.

### 4. Initialize the repository
```
git init
```
Creates a hidden `.git/` folder where all history lives. You never open it. **Do this early** — the cost is zero and you keep your project's full history.

### 5. Read the state (do this constantly)
```
git status
```
This is git narrating its own state. Learning to read it *is* learning git. It tells you the branch, whether any commits exist, and which files are untracked / staged.

### 6. Rename the branch to `main`
The repo started on `master`; convention (and GitHub) is `main`. Easy to rename while empty:
```
git branch -m master main
```

### 7. Create and verify `.gitignore`
A plain text file at the project root listing what git should NOT track. Things to ignore fall into three buckets:

- **Secrets** — dangerous to publish (e.g. a `.env` file holding your Postgres password)
- **Regenerated / machine-specific** — rebuilt automatically (`venv/`, `__pycache__/`, `*.pyc`)
- **Produced data / outputs** — files the pipeline creates (`data/`, raw `*.csv` / `*.json` dumps)

Our starter `.gitignore`:
```gitignore
# --- Secrets ---
.env

# --- Python regenerated/machine-specific ---
venv/
.venv/
__pycache__/
*.pyc

# --- Produced data / outputs ---
data/
*.csv
*.json
```
Trailing `/` = a folder. `*` = wildcard. `#` = comment.

**Verify it works** (the important habit): create a fake `.env` with a dummy secret, then run `git status`. If `.env` does NOT appear in the untracked list, ignoring works — you've proven your secret won't leak before writing any real code.

**Gotcha we hit:** `.gitignore` only takes effect once the file is actually *saved to disk*. An unsaved file in VS Code (dot ● instead of X on the tab) reads as empty. `cat .gitignore` shows what's really on disk.

### 8. The stage → commit loop (first commit)
Stage the files you want in the snapshot (the "waiting room"):
```
git add .gitignore README.md requirements.txt
```
(`git add .` stages everything not ignored.)

Check what's staged:
```
git status
```
Staged files move from "Untracked files" to "Changes to be committed." That shift *is* the staging concept made visible.

Take the snapshot:
```
git commit -m "Initial commit: project scaffolding and gitignore"
```
`-m` is the message — a note to your future self about *why* this snapshot exists.

Confirm:
```
git status      # "working tree clean" = all changes captured
git log         # shows your commit history
```

---

## Going forward — the rhythm

Repeat this every time you finish a small, logical chunk of work:
```
git status                       # see what changed
git add <files>                  # stage what belongs together
git commit -m "why this change"  # snapshot it
```

**Habit:** commit in small, meaningful units — not one giant "did stuff" commit at the end of the day. Your future self reading the history will thank you.

---

## Quick command cheat sheet

| Command | What it does |
|---|---|
| `git --version` | Confirm git is installed |
| `git config --global user.name "..."` | Set commit identity (one-time) |
| `git init` | Start a repo in the current folder |
| `git status` | Show current state (run constantly) |
| `git branch -m master main` | Rename branch to `main` |
| `git add <file>` | Stage a file for the next commit |
| `git add .` | Stage everything not ignored |
| `git commit -m "message"` | Snapshot staged changes |
| `git log` | View commit history |
| `cat .gitignore` | See what's actually saved on disk |
