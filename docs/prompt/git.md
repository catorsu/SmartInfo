<Git-ruls condition="User command is '/git'">
Execute a specific commit and push workflow on the current repository based on the user's request and the current state of the codebase (which you can inspect using your tools).

Proceed through the following steps sequentially:

1.  **Fetch Remote Changes:** Update local tracking branches from the 'origin' remote repository.

2.  **Stage Changes:** Use `git add -A` to stage all relevant new, modified, and deleted files (respecting `.gitignore`).

3.  **Commit Message Generation:**
    *   If no changes are staged, report "No changes to commit." and conclude.
    *  Otherwise, analyze staged changes (excluding detailed "docs/memory bank/" content from subject unless it's a `docs:` commit specifically for it).
    *   Determine a conventional commit **type** (`feat:`, `fix:`, `docs:`, `chore:`, etc.) based on the nature of changes. Default to `chore:` if unclear.
    *   Create a concise **subject** summarizing the changes.
    *   Format as `"type: subject"`. Report the generated message.

4.  **Commit:** Execute the commit with the generated message.

5.  **Sync with Remote (Rebase Pull):** Attempt `git pull --rebase origin [current_branch]`. If this results in merge conflicts that require manual intervention, report the conflict clearly, state that manual resolution is needed, and terminate the workflow, providing instructions for the user on how to proceed (resolve conflicts, add, rebase continue, and then push).

6.  **Push:** If pull was successful, `git push origin [current_branch]`.
</Git-rules>
