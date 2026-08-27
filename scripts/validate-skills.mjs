#!/usr/bin/env node
// Validates the curated skill list in README.md against the conventions
// documented in CONTRIBUTING.md.
//
// Checks performed:
//   - Every skill bullet is a well-formed markdown link with non-empty text
//     and a non-empty URL (hard error when violated).
//   - The author/skill-name prefix convention (link text contains a "/").
//   - Duplicate skill URLs (warning).
//   - The "Skills-<count>+" README badge vs. the actual number of entries
//     (warning).
//
// Exit codes:
//   0  no hard errors (warnings may still be printed)
//   1  one or more hard errors, or --strict with any warning
//   2  could not read/parse input files

import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";

const strict = process.argv.includes("--strict");
const repoRoot = join(dirname(fileURLToPath(import.meta.url)), "..");
const readmePath = join(repoRoot, "README.md");

let text;
try {
  text = readFileSync(readmePath, "utf8");
} catch (err) {
  console.error(`Unable to read ${readmePath}: ${err.message}`);
  process.exit(2);
}

const lines = text.split("\n");

// A skill entry is a bullet whose first inline element is a bold markdown
// link, e.g. `- **[author/name](https://...)** - description`.
const entryRe = /^\s*[-*]\s+\*\*\[([^\]]*)\]\(([^)]*)\)\*\*\s*(.*)$/;

const errors = [];
const warnings = [];
const entries = [];

lines.forEach((line, idx) => {
  const m = line.match(entryRe);
  if (!m) return;
  const lineNo = idx + 1;
  const [, linkText, url, trailing] = m;
  entries.push({ lineNo, linkText, url, trailing });

  if (linkText.trim() === "") {
    errors.push(`L${lineNo}: skill entry has empty link text`);
  }
  if (url.trim() === "") {
    errors.push(`L${lineNo}: skill entry "${linkText}" has an empty URL`);
  } else if (!/^https?:\/\//.test(url.trim())) {
    errors.push(
      `L${lineNo}: skill entry "${linkText}" URL is not http(s): ${url}`,
    );
  }
  if (linkText.trim() !== "" && !linkText.includes("/")) {
    warnings.push(
      `L${lineNo}: entry "${linkText}" is missing an author/org prefix (expected "author/skill-name")`,
    );
  }
  // Description follows the bold link, optionally after a "-" or ":" separator.
  const desc = trailing.replace(/^[\s:—-]+/, "").trim();
  if (desc === "") {
    warnings.push(`L${lineNo}: entry "${linkText}" has no description`);
  }
});

// Duplicate URL detection.
const byUrl = new Map();
for (const e of entries) {
  const key = e.url.trim();
  if (!key) continue;
  if (!byUrl.has(key)) byUrl.set(key, []);
  byUrl.get(key).push(e.lineNo);
}
let duplicateCount = 0;
for (const [url, occurrences] of byUrl) {
  if (occurrences.length > 1) {
    duplicateCount++;
    warnings.push(
      `duplicate URL (${occurrences.length}x) at lines ${occurrences.join(", ")}: ${url}`,
    );
  }
}

// Badge count vs. actual entries.
const badge = text.match(/Skills-(\d+)\+/);
if (badge) {
  const badgeCount = Number(badge[1]);
  if (entries.length > badgeCount) {
    warnings.push(
      `badge claims ${badgeCount}+ skills but ${entries.length} entries were counted; consider updating the badge`,
    );
  }
} else {
  warnings.push('could not find a "Skills-<count>+" badge in README.md');
}

// Report.
console.log("Awesome Agent Skills — list validation");
console.log("--------------------------------------");
console.log(`Skill entries parsed : ${entries.length}`);
console.log(`Unique skill URLs    : ${byUrl.size}`);
console.log(`Duplicate URLs       : ${duplicateCount}`);
if (badge) console.log(`Badge count          : ${badge[1]}+`);
console.log("");

if (warnings.length) {
  console.log(`Warnings (${warnings.length}):`);
  for (const w of warnings) console.log(`  ⚠ ${w}`);
  console.log("");
}

if (errors.length) {
  console.log(`Errors (${errors.length}):`);
  for (const e of errors) console.log(`  ✖ ${e}`);
  console.log("");
  console.error("Validation FAILED: fix the errors above.");
  process.exit(1);
}

if (strict && warnings.length) {
  console.error("Validation FAILED (--strict): resolve the warnings above.");
  process.exit(1);
}

console.log("Validation PASSED: no hard errors found.");
process.exit(0);
