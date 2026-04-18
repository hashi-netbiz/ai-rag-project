# Commit and Push Skill
1. Run `git status` to check for changes
2. Check for diverged branches with `git log --oneline HEAD..origin/main` — if diverged, ASK user before proceeding
3. Stage all changes with `git add -A`
4. Generate a concise conventional commit message based on the diff
5. Commit and push to the current branch
6. Report success with the commit hash
