# Contributing Guide

How our team works with Git and GitHub. The same rules apply to every OPractica repository.

## Branches

```
           feat/office-map feat/booking-api
               o---o---o   o---o---o
              /         \ /         \
main    o----o-----------o-----------o-----------o-----> all tasks are merged here
                                      \         /
release -------------------------------o-------o-------> stable version for demos
                                        \     /
bugfix  ---------------------------------o---o---------> fixes for release bugs
```

`o` is a commit, `/` is where a branch starts, `\` is where it is merged back with a pull request.

| Branch | Purpose | How it changes |
|---|---|---|
| `main` | Main development branch. Every finished task ends up here. | Pull requests only |
| `release` | Stable version that we show and deploy. New features in `main` can't break it. | Pull request from `main` or `bugfix` |
| `bugfix` | Fixes for bugs found in `release`. | Commits, then a pull request to `release` |
| `feat/...`, `fix/...`, `docs/...`, `chore/...` | Short-lived branch for one task. Deleted after merge. | You commit here |

### Naming task branches

| Prefix | When to use | Example |
|---|---|---|
| `feat/` | New feature | `feat/office-map-svg` |
| `fix/` | Bug fix during development | `fix/booking-date-format` |
| `docs/` | Documentation only | `docs/api-readme` |
| `chore/` | Setup, configs, dependencies, project structure | `chore/folder-structure` |

Use lowercase words separated by hyphens. Don't name branches `bugfix/...` or `release/...`: Git can't have a branch `bugfix/x` while a branch `bugfix` exists.

## Working on a task

```bash
# 1. Start from the latest main
git checkout main
git pull

# 2. Create a branch for the task
git checkout -b feat/office-map-svg

# 3. Work and commit in small steps
git add .
git commit -m "feat: add clickable SVG office map"

# 4. Push the branch to GitHub (next times just `git push`)
git push -u origin feat/office-map-svg
```

5. **Open a pull request** `feat/office-map-svg -> main`: click "Compare & pull request" on GitHub, or run `gh pr create --base main`.
6. **Review.** A teammate reads the code and leaves comments. Fix them with new commits in the same branch and `git push`. The pull request updates automatically.
7. **Merge** the pull request on GitHub and click "Delete branch".
8. **Clean up locally:**
   ```bash
   git checkout main
   git pull
   git branch -d feat/office-map-svg
   ```

### If main changed while you were working

```bash
git checkout feat/office-map-svg
git pull origin main
# resolve conflicts if Git reports any, then:
git add .
git commit
git push
```

## Pull requests

- One task, one branch, one pull request. Small pull requests are reviewed faster and conflict less.
- Title in the same format as a commit message: `feat: add booking API`.
- In the description write what changed and how to check it.
- Don't merge a pull request with failing checks or unresolved comments.

## Commit messages

Format: `type: short description`, in English, imperative mood ("add", not "added").

| Type | Meaning |
|---|---|
| `feat` | New feature |
| `fix` | Bug fix |
| `docs` | Documentation |
| `chore` | Configs, dependencies, structure |
| `refactor` | Code change that doesn't change behavior |
| `test` | Tests |

Examples:

```
feat: add endpoint for booking a desk
fix: allow cancelling a booking
chore: update dependencies
```

## Making a release

When `main` has a working version you want to show:

1. Open a pull request `main -> release` and merge it.
2. Optionally tag the version:
   ```bash
   git checkout release
   git pull
   git tag v0.1
   git push --tags
   ```

## Fixing a bug in a release

```bash
# 1. Bring bugfix up to date with release
git checkout bugfix
git pull
git merge origin/release

# 2. Fix the bug and commit
git commit -m "fix: allow cancelling a booking"
git push
```

3. Open a pull request `bugfix -> release` and merge it.
4. Open a pull request `release -> main` and merge it. Without this step the bug comes back in the next release.

## Rules

- Never commit directly to `main` or `release`. Both branches are protected and accept changes only through pull requests.
- Always start a new task from the latest `main`.
- Never commit secrets: `.env` files, passwords, API keys. Put example values in `.env.example`.
- After your branch is merged and deleted, run `git fetch --prune` to remove stale remote branches locally.
