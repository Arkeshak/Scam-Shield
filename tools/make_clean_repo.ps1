# tools/make_clean_repo.ps1
# Exports a clean copy of scamshield-family to ..\scamshield-clean
# Excludes .git, venv, __pycache__, .env, *.db, checkpoints, tmp, outputs

$source = "$PSScriptRoot\.."
$dest = "$PSScriptRoot\..\..\scamshield-clean"

Write-Host "Exporting clean project from $source to $dest..."

$excludeDirs = @(".git", "venv", ".venv", "__pycache__", ".claude", ".codex", ".cursor", "checkpoints", "tmp", "outputs", ".history", "dev-notes")
$excludeFiles = @(".env", "*.db", "*.sqlite", "*.sqlite3", "*.zip", "CLAUDE.md", "AGENT_PROMPT*.md", "PATCHES.md", "CLAUDE_CODE_AUDIT_PROMPT.md")

robocopy $source $dest /E /XD $excludeDirs /XF $excludeFiles

if ($LASTEXITCODE -le 7) {
    Write-Host "Robocopy completed successfully (exit code $LASTEXITCODE)."
} else {
    Write-Error "Robocopy failed with exit code $LASTEXITCODE"
    exit $LASTEXITCODE
}
