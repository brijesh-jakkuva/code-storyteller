#!/bin/bash
set -e

# Setup
STYLE="${INPUT_STYLE:-heist}"
OUTPUT_MODE="${INPUT_OUTPUT:-comment}"
MODEL="${INPUT_MODEL:-claude-sonnet-4-6}"
export MODEL

# Determine what to analyze
if [ -n "$INPUT_PATH" ]; then
  TARGET="$INPUT_PATH"
elif [ "$GITHUB_EVENT_NAME" = "pull_request" ]; then
  # Get changed files from the PR
  TARGET=""
else
  TARGET="."
fi

# Run storytell
echo "🎬 Code Storyteller — style: $STYLE"

if [ -n "$TARGET" ] && [ -d "$TARGET" ]; then
  STORY=$(storytell tell "$TARGET" --as "$STYLE" --no-stream 2>&1)
elif [ -n "$TARGET" ] && [ -f "$TARGET" ]; then
  STORY=$(storytell tell "$TARGET" --as "$STYLE" --no-stream 2>&1)
else
  # Analyze each changed file
  STORY=""
  # Use merge base for multi-commit PRs, fallback to HEAD~1
  MERGE_BASE=$(git merge-base HEAD origin/"${GITHUB_BASE_REF:-main}" 2>/dev/null || echo "")
  if [ -n "$MERGE_BASE" ]; then
    CHANGED=$(git diff --name-only HEAD "$MERGE_BASE" -- '*.py' '*.js' '*.ts' '*.tsx' '*.jsx' '*.go' '*.rs' '*.java' 2>/dev/null || echo "")
  else
    CHANGED=$(git diff --name-only HEAD~1 -- '*.py' '*.js' '*.ts' '*.tsx' '*.jsx' '*.go' '*.rs' '*.java' 2>/dev/null || echo "")
  fi
  if [ -z "$CHANGED" ]; then
    STORY="No supported source files changed."
  else
    while IFS= read -r f; do
      [ -z "$f" ] && continue
      if [ -f "$f" ]; then
        FILE_STORY=$(storytell tell "$f" --as "$STYLE" --no-stream 2>&1 || echo "Could not analyze $f")
        STORY="$STORY

---

## $f

$FILE_STORY"
      fi
    done <<< "$CHANGED"
  fi
fi

echo "$STORY"

# Post as PR comment if requested
if [ "$OUTPUT_MODE" = "comment" ] && [ "$GITHUB_EVENT_NAME" = "pull_request" ]; then
  COMMENT="## 🎬 Code Storyteller ($STYLE style)

$STORY"

  # Use gh CLI to post comment
  echo "$COMMENT" | gh pr comment "$GITHUB_PULL_REQUEST_NUMBER" --body-file - 2>/dev/null || \
    echo "Could not post comment (gh CLI may not be configured)"
fi

# GitHub Actions output (new method)
if [ -n "$GITHUB_OUTPUT" ]; then
  echo "story<<EOF" >> "$GITHUB_OUTPUT"
  echo "$STORY" >> "$GITHUB_OUTPUT"
  echo "EOF" >> "$GITHUB_OUTPUT"
fi
