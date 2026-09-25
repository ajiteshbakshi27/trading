/**
 * validate-tokens.cjs — constitution gate (P051 discipline).
 * Marketing surfaces must consume var(--*) tokens, not raw hex/rgb.
 * Exits non-zero on violations so CI/PR fails review like it should.
 */
const fs = require("fs");
const path = require("path");

const ROOT = path.join(__dirname, "..", "src");
const SCAN_DIRS = [
  path.join(ROOT, "app", "(marketing)"),
  path.join(ROOT, "components", "marketing"),
];

const HEX = /#[0-9a-fA-F]{3,8}\b/g;
const RAW_RGB = /\brgba?\(/g;
const CSS_ALLOWLIST = new Set(["globals.css"]);

const violations = [];
let scanned = 0;

function walk(dir) {
  for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
    const p = path.join(dir, entry.name);
    if (entry.isDirectory()) walk(p);
    else if (/\.(tsx?|css)$/.test(entry.name)) {
      scanned++;
      if (CSS_ALLOWLIST.has(entry.name) && p.includes("app")) continue;
      const src = fs.readFileSync(p, "utf8");
      const lines = src.split("\n");
      lines.forEach((line, i) => {
        if (line.trim().startsWith("//") || line.trim().startsWith("*")) return;
        const hex = line.match(HEX);
        if (hex) violations.push(`${p}:${i + 1} raw hex ${hex.join(", ")}`);
        const rgb = line.match(RAW_RGB);
        if (rgb) violations.push(`${p}:${i + 1} raw rgb() ${rgb.join(", ")}`);
      });
    }
  }
}

for (const d of SCAN_DIRS) if (fs.existsSync(d)) walk(d);

const globals = fs.readFileSync(path.join(ROOT, "app", "globals.css"), "utf8");
for (const required of [
  "--color-background", "--color-foreground", "--color-accent",
  "--color-hairline", "--dur-base", "--ease-out", "--focus-ring",
]) {
  if (!globals.includes(required)) violations.push(`globals.css missing token ${required}`);
}

if (violations.length) {
  console.error("✗ token gate FAILED");
  violations.forEach((v) => console.error("  - " + v));
  process.exit(1);
}
console.log(`✓ token gate passed (${scanned} marketing files scanned, tokens-only)`);
