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

Use lowercase words separated by hyphens and put the issue number first: `feat/13-user-registration`. Don't name branches `bugfix/...` or `release/...`: Git can't have a branch `bugfix/x` while a branch `bugfix` exists.

## Picking an issue

Every task is a GitHub issue: **take it → branch → code → pull request with `Closes #N` → merge**. The issue closes automatically after the merge.

1. **Pick an issue whose "Depends on" issues are all closed.** List issues nobody has taken yet:
   ```bash
   gh issue list --no-assignee
   ```
2. **Assign it to yourself** so the team sees it's taken: on GitHub click **Assignees → assign yourself**, or run:
   ```bash
   gh issue edit 13 --add-assignee @me
   ```
3. **Use the issue as your plan.** "Tasks" is the checklist of work, "Done when" is what to check before opening the pull request.

## Working on a task

```bash
# 1. Start from the latest main
git checkout main
git pull

# 2. Create a branch for the issue
git checkout -b feat/13-user-registration

# 3. Work and commit in small steps
git add .
git commit -m "feat: add user registration endpoint"

# 4. Fix lint and formatting before pushing
uv run ruff check --fix . && uv run ruff format .

# 5. Push the branch to GitHub (next times just `git push`)
git push -u origin feat/13-user-registration
```

6. **Open a pull request** `feat/13-user-registration -> main`: click "Compare & pull request" on GitHub, or run `gh pr create --base main`. Write `Closes #13` in the description.
7. **Review.** Wait for green CI and ask a teammate to review. Fix comments with new commits in the same branch and `git push`. The pull request updates automatically.
8. **Merge** the pull request on GitHub and click "Delete branch". The issue closes automatically.
9. **Clean up locally:**
   ```bash
   git checkout main
   git pull
   git branch -d feat/13-user-registration
   ```

### If main changed while you were working

```bash
git checkout feat/13-user-registration
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
- Link the issue with `Closes #N` so it closes on merge.
- Don't merge a pull request with failing checks or unresolved comments.

## Working in parallel

- **Take issues from different areas** (for example auth and email vs seats and bookings). Then you rarely touch the same files.
- **If your issue depends on one that is still in progress**, agree on the function signature with its owner and start with a stub. For example, use a fake user until `get_current_user` is merged.
- **Small pull requests, merged often.** The longer a branch lives, the harder it is to merge.

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

- Never commit directly to `main` or `release`. Changes reach them only through pull requests.
- Always start a new task from the latest `main`.
- Never commit secrets: `.env` files, passwords, API keys. Put example values in `.env.example`.
- After your branch is merged and deleted, run `git fetch --prune` to remove stale remote branches locally.
