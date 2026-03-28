const fs = require("fs");
const path = require("path");

const root = process.cwd();
const outputDir = path.join(root, "dist", "cloudflare");

const PUBLIC_ENTRIES = [
  "index.html",
  "styles.css",
  "robots.txt",
  "sitemap.xml",
  "humans.txt",
  "site.webmanifest",
  "assets",
  "data",
  "src",
  "styles",
];

function removeIfExists(targetPath) {
  if (fs.existsSync(targetPath)) {
    fs.rmSync(targetPath, { recursive: true, force: true });
  }
}

function ensureDir(targetPath) {
  fs.mkdirSync(targetPath, { recursive: true });
}

function copyEntry(relativePath) {
  const sourcePath = path.join(root, relativePath);
  const destinationPath = path.join(outputDir, relativePath);
  if (!fs.existsSync(sourcePath)) {
    throw new Error(`Missing required deploy entry: ${relativePath}`);
  }
  const sourceStat = fs.statSync(sourcePath);
  ensureDir(path.dirname(destinationPath));
  if (sourceStat.isDirectory()) {
    fs.cpSync(sourcePath, destinationPath, { recursive: true });
    return;
  }
  fs.copyFileSync(sourcePath, destinationPath);
}

function formatMiB(bytes) {
  return `${(bytes / (1024 * 1024)).toFixed(2)} MiB`;
}

function main() {
  removeIfExists(outputDir);
  ensureDir(outputDir);
  PUBLIC_ENTRIES.forEach(copyEntry);

  const resourcePath = path.join(outputDir, "data", "entries-resources.json");
  const resourceBytes = fs.statSync(resourcePath).size;

  console.log(`Prepared Cloudflare assets in ${path.relative(root, outputDir)}`);
  console.log(`entries-resources.json: ${formatMiB(resourceBytes)}`);
}

main();
