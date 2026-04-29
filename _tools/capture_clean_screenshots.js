const puppeteer = require('puppeteer-core');
const path = require('path');

const OUT = path.join(process.cwd(), 'screenshots');
const URL = 'http://192.168.101.80:8000/wm1303.html';

const shots = [
  { name: 'status', selector: 'button, a, [role="tab"]', text: 'Status', wait: 2500 },
  { name: 'spectrum', selector: 'button, a, [role="tab"]', text: 'Spectrum', wait: 3500 },
  { name: 'dedup', selector: 'button, a, [role="tab"]', text: 'Dedup', wait: 3000 },
  { name: 'channels', selector: 'button, a, [role="tab"]', text: 'Channels', wait: 3000 },
  { name: 'bridge-rules', selector: 'button, a, [role="tab"]', text: 'Bridge Rules', wait: 3000 },
  { name: 'tracing', selector: 'button, a, [role="tab"]', text: 'Tracing', wait: 3000 },
];

async function clickTabByText(page, text) {
  const clicked = await page.evaluate((label) => {
    const norm = s => (s || '').replace(/\s+/g, ' ').trim().toLowerCase();
    const wanted = norm(label);
    const nodes = Array.from(document.querySelectorAll('button, a, [role="tab"]'));
    for (const el of nodes) {
      if (norm(el.innerText) === wanted || norm(el.textContent) === wanted) {
        el.click();
        return true;
      }
    }
    return false;
  }, text);
  if (!clicked) throw new Error(`Tab not found: ${text}`);
}

(async () => {
  const browser = await puppeteer.launch({
    executablePath: '/usr/bin/chromium',
    headless: true,
    args: ['--no-sandbox', '--disable-setuid-sandbox', '--disable-dev-shm-usage']
  });
  const page = await browser.newPage();
  await page.setViewport({ width: 1440, height: 2200, deviceScaleFactor: 1 });
  await page.goto(URL, { waitUntil: 'networkidle2', timeout: 30000 });
  await page.evaluate(() => window.scrollTo(0, 0));

  for (const shot of shots) {
    await clickTabByText(page, shot.text);
    await new Promise(r => setTimeout(r, shot.wait));
    await page.evaluate(() => window.scrollTo(0, 0));
    await page.screenshot({
      path: path.join(OUT, `${shot.name}.png`),
      fullPage: true,
      type: 'png'
    });
    console.log(`saved ${shot.name}.png`);
  }

  await browser.close();
})().catch(err => {
  console.error(err);
  process.exit(1);
});
