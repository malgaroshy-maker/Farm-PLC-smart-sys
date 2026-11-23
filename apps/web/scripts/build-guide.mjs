#!/usr/bin/env node
/**
 * Operator guide generator (Milestone G6).
 * One source, src/content/guide.json (also rendered in the app's Help page), produces:
 *   - docs/OPERATOR_GUIDE.md (Arabic part, then English part)
 *   - public/guide/operator-guide-ar.pdf and operator-guide-en.pdf (A4, via headless Chrome/Edge)
 * Fonts and screenshots are embedded in the print HTML, so the PDF never depends on a network.
 *
 *   pnpm --filter @algaroshy/web guide          # markdown + both PDFs
 *   node scripts/build-guide.mjs --md-only       # markdown only (no browser needed)
 */
import { execFileSync } from 'node:child_process';
import { existsSync, mkdtempSync, readFileSync, rmSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';

const WEB = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const ROOT = resolve(WEB, '../..');
const guide = JSON.parse(readFileSync(join(WEB, 'src/content/guide.json'), 'utf8'));
const LANGS = ['ar', 'en'];
const UI = {
  ar: { contents: 'المحتويات', page: 'صفحة', version: 'الإصدار', farm: 'مزرعة الجروشي', otherLang: 'English version below' },
  en: { contents: 'Contents', page: 'page', version: 'Version', farm: 'Algaroshy Farm', otherLang: '' },
};

// ─── Markdown ────────────────────────────────────────────────────────────
function blockMd(b, lang) {
  const v = b[lang];
  if (b.type === 'steps') return v.map((x, i) => `${i + 1}. ${x}`).join('\n');
  if (b.type === 'list') return v.map((x) => `- ${x}`).join('\n');
  if (b.type === 'warn') return `> ⚠️ ${v}`;
  if (b.type === 'note') return `> ℹ️ ${v}`;
  return v;
}

function markdown() {
  const out = [
    '<!-- Generated from apps/web/src/content/guide.json by apps/web/scripts/build-guide.mjs. Edit the JSON, not this file. -->',
    '',
    `# ${guide.title.ar}`,
    `# ${guide.title.en}`,
    '',
    `**${UI.ar.version} / ${UI.en.version}:** ${guide.version} · PDF: [العربية](../apps/web/public/guide/operator-guide-ar.pdf) · [English](../apps/web/public/guide/operator-guide-en.pdf) · In the app: the **?** button in the top bar.`,
    '',
  ];
  for (const lang of LANGS) {
    const rtl = lang === 'ar';
    out.push('---', '', rtl ? '<div dir="rtl">' : '', '', `## ${lang === 'ar' ? 'العربية' : 'English'}`, '', guide.intro[lang], '');
    for (const part of guide.parts) {
      out.push(`### ${part.title[lang]}`, '');
      for (const s of part.sections) {
        out.push(`#### ${s.title[lang]}`, '');
        if (s.image) out.push(`<img src="../apps/web/public/${s.image}" alt="${s.title[lang]}" width="360">`, '');
        for (const b of s.body) out.push(blockMd(b, lang), '');
      }
    }
    if (rtl) out.push('</div>', '');
  }
  return out.filter((l, i, a) => !(l === '' && a[i - 1] === '')).join('\n');
}

// ─── Print HTML ──────────────────────────────────────────────────────────
const esc = (s) => String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
const b64 = (p) => readFileSync(p).toString('base64');

function fontsCss() {
  const dir = join(WEB, 'node_modules/@fontsource/ibm-plex-sans-arabic/files');
  const ranges = {
    arabic: 'U+0600-06FF, U+0750-077F, U+0870-088E, U+08A0-08FF, U+FB50-FDFF, U+FE70-FEFF',
    latin: 'U+0000-00FF, U+0131, U+0152-0153, U+02BB-02BC, U+02C6, U+02DA, U+02DC, U+2000-206F, U+2074, U+20AC, U+2122, U+2191, U+2193, U+2212, U+2215, U+FEFF, U+FFFD',
  };
  let css = '';
  for (const [subset, range] of Object.entries(ranges)) {
    for (const w of [400, 700]) {
      const f = join(dir, `ibm-plex-sans-arabic-${subset}-${w}-normal.woff2`);
      css += `@font-face{font-family:'Plex';font-weight:${w};src:url(data:font/woff2;base64,${b64(f)}) format('woff2');unicode-range:${range};}\n`;
    }
  }
  return css;
}

function blockHtml(b, lang) {
  const v = b[lang];
  if (b.type === 'steps') return `<ol>${v.map((x) => `<li>${esc(x)}</li>`).join('')}</ol>`;
  if (b.type === 'list') return `<ul>${v.map((x) => `<li>${esc(x)}</li>`).join('')}</ul>`;
  if (b.type === 'warn' || b.type === 'note') return `<p class="${b.type}">${esc(v)}</p>`;
  return `<p>${esc(v)}</p>`;
}

function printHtml(lang) {
  const rtl = lang === 'ar';
  const logo = join(WEB, 'public/map/logo.webp');
  let n = 0;
  const toc = guide.parts
    .map(
      (p) =>
        `<li><b>${esc(p.title[lang])}</b><ol>${p.sections.map((s) => `<li>${esc(s.title[lang])}</li>`).join('')}</ol></li>`,
    )
    .join('');
  const body = guide.parts
    .map((p) => {
      const secs = p.sections
        .map((s) => {
          n += 1;
          const img = s.image
            ? `<figure><img src="data:image/jpeg;base64,${b64(join(WEB, 'public', s.image))}" alt=""></figure>`
            : '';
          return `<section class="sec"><h3><span class="num">${n}</span>${esc(s.title[lang])}</h3>${img}${s.body.map((b) => blockHtml(b, lang)).join('')}</section>`;
        })
        .join('');
      return `<div class="part"><h2>${esc(p.title[lang])}</h2>${secs}</div>`;
    })
    .join('');
  return `<!doctype html><html lang="${lang}" dir="${rtl ? 'rtl' : 'ltr'}"><head><meta charset="utf-8">
<title>${esc(guide.title[lang])}</title>
<style>
${fontsCss()}
@page { size: A4; margin: 14mm 14mm 16mm; }
html, body { background: #fff; color: #1b1f22; -webkit-print-color-adjust: exact; print-color-adjust: exact; }
body { font-family: 'Plex', 'Segoe UI', Tahoma, sans-serif; font-size: 10.5pt; line-height: 1.65; margin: 0; }
.cover { min-height: 250mm; display: flex; flex-direction: column; align-items: center; justify-content: center; text-align: center; gap: 6mm; }
.cover img { width: 34mm; }
.cover h1 { font-size: 22pt; margin: 0; color: #00687a; }
.cover .farm { font-size: 14pt; font-weight: 700; }
.cover .ver { color: #5b676a; }
.toc { break-before: page; }
.toc h2 { color: #00687a; }
.toc ol { margin: 1mm 0 4mm; }
.part { break-before: page; }
h2 { font-size: 16pt; color: #00687a; border-bottom: 1.2mm solid #00e5ff; padding-bottom: 2mm; margin: 0 0 5mm; }
h3 { font-size: 12.5pt; margin: 6mm 0 2mm; display: flex; align-items: center; gap: 2.5mm; break-after: avoid; }
.num { display: inline-flex; align-items: center; justify-content: center; width: 7mm; height: 7mm; border-radius: 50%; background: #00687a; color: #fff; font-size: 9pt; flex-shrink: 0; }
figure { margin: 2mm 0 3mm; text-align: center; break-inside: avoid; }
figure img { max-height: 88mm; max-width: 100%; border: 0.3mm solid #c9d1d3; border-radius: 3mm; }
p, li { orphans: 3; widows: 3; }
p { margin: 1.5mm 0; }
ol, ul { margin: 1.5mm 0; padding-inline-start: 7mm; }
li { margin: 0.8mm 0; }
.note, .warn { padding: 2mm 3mm; border-radius: 2mm; border-inline-start: 1.2mm solid; break-inside: avoid; }
.note { background: #e6fbff; border-color: #00a5bd; }
.warn { background: #fff3e6; border-color: #e07b00; }
.end { margin-top: 8mm; padding-top: 3mm; border-top: 0.3mm solid #c9d1d3; color: #5b676a; font-size: 9pt; text-align: center; }
</style></head><body>
<div class="cover">
  <img src="data:image/webp;base64,${b64(logo)}" alt="">
  <div class="farm">${esc(UI[lang].farm)}</div>
  <h1>${esc(guide.title[lang])}</h1>
  <p>${esc(guide.intro[lang])}</p>
  <div class="ver">${esc(UI[lang].version)}: ${esc(guide.version)}</div>
</div>
<div class="toc"><h2>${esc(UI[lang].contents)}</h2><ol>${toc}</ol></div>
${body}
<div class="end">${esc(UI[lang].farm)} · ${esc(guide.title[lang])} · ${esc(UI[lang].version)} ${esc(guide.version)}</div>
</body></html>`;
}

function findBrowser() {
  const c = [
    process.env.CHROME_PATH,
    'C:/Program Files/Google/Chrome/Application/chrome.exe',
    'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe',
    '/usr/bin/google-chrome',
    '/usr/bin/chromium',
    '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
  ].filter(Boolean);
  return c.find((p) => existsSync(p));
}

// ─── Main ────────────────────────────────────────────────────────────────
writeFileSync(join(ROOT, 'docs/OPERATOR_GUIDE.md'), markdown(), 'utf8');
console.log('wrote docs/OPERATOR_GUIDE.md');

if (!process.argv.includes('--md-only')) {
  const browser = findBrowser();
  if (!browser) {
    console.error('No Chrome/Edge found (set CHROME_PATH); PDFs not generated.');
    process.exit(1);
  }
  const tmp = mkdtempSync(join(tmpdir(), 'farm-guide-'));
  try {
    for (const lang of LANGS) {
      const html = join(tmp, `guide-${lang}.html`);
      const pdf = join(WEB, `public/guide/operator-guide-${lang}.pdf`);
      writeFileSync(html, printHtml(lang), 'utf8');
      execFileSync(browser, [
        '--headless=new',
        '--disable-gpu',
        '--no-pdf-header-footer',
        `--user-data-dir=${join(tmp, 'profile')}`,
        `--print-to-pdf=${pdf}`,
        pathToFileURL(html).href,
      ], { stdio: 'ignore', timeout: 120_000 });
      if (!existsSync(pdf)) throw new Error(`PDF not written: ${pdf}`);
      console.log(`wrote public/guide/operator-guide-${lang}.pdf`);
    }
  } finally {
    rmSync(tmp, { recursive: true, force: true });
  }
}
