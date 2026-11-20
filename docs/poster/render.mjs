// Render docs/poster/out/poster.html to a 22 x 36 in PDF and a preview PNG.
// Run from frontend/ (it has Playwright): node ../docs/poster/render.mjs
import { createRequire } from "node:module";
const { chromium } = createRequire(process.cwd() + "/")("@playwright/test");
import { fileURLToPath } from "node:url";
import path from "node:path";
const out = path.join(path.dirname(fileURLToPath(import.meta.url)), "out");
const browser = await chromium.launch();
const page = await browser.newPage({ viewport: { width: 2112, height: 3456 } });
await page.goto("file://" + path.join(out, "poster.html"));
await page.waitForLoadState("load");
const overflow = await page.evaluate(() => document.body.scrollHeight);
console.log("content height px:", overflow, "(page is 3456)");
await page.pdf({ path: path.join(out, "FaultIQ_poster.pdf"), width: "22in", height: "36in", printBackground: true, pageRanges: "1" });
await page.screenshot({ path: path.join(out, "preview.png"), fullPage: true });
await browser.close();
