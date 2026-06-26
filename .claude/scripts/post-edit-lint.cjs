/**
 * PostToolUse hook — runs ESLint or Stylelint on edited files.
 *
 * Reads tool input from stdin JSON, extracts the file_path,
 * and dispatches to the correct linter based on extension.
 *
 * Designed to be fast: uses --cache for both linters.
 * Errors are non-blocking (warning only).
 */

const { execSync } = require('child_process');
const path = require('path');

// --- read stdin JSON ------------------------------------------------
let raw = '';
process.stdin.setEncoding('utf8');
process.stdin.on('data', (chunk) => { raw += chunk; });
process.stdin.on('end', () => {
  let fp = '';
  try {
    const data = JSON.parse(raw);
    fp = (data.tool_input && data.tool_input.file_path) || '';
  } catch {
    // Malformed input — exit silently
    process.exit(0);
  }

  if (!fp) process.exit(0);

  const ext = path.extname(fp).toLowerCase();
  const cwd = process.cwd();

  // --- dispatch -----------------------------------------------------
  try {
    if (ext === '.ts' || ext === '.tsx') {
      execSync(`npx eslint --fix --cache "${fp}"`, {
        cwd,
        stdio: 'pipe',
        timeout: 30_000,
      });
    } else if (ext === '.scss' || ext === '.css') {
      execSync(`npx stylelint --fix --cache "${fp}"`, {
        cwd,
        stdio: 'pipe',
        timeout: 15_000,
      });
    }
    // Other file types — no-op
  } catch {
    // Linter warnings/errors are non-blocking for the edit flow.
    // The session-end Stop hook will catch remaining issues.
  }
});
