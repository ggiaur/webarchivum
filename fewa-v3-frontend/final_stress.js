const { chromium } = require('playwright');
(async () => {
  const browser = await chromium.launch({ ignoreHTTPSErrors: true });
  let successes = 0;

  for (let i = 0; i < 5; i++) {
    const ctx = await browser.newContext({ ignoreHTTPSErrors: true, viewport: { width: 1400, height: 1200 } });
    const page = await ctx.newPage();
    await page.goto('https://teszt.vmk.hu/documents/58b99535-60a7-4a1a-bada-14bafda5a0d9/', { waitUntil: 'domcontentloaded' });
    await page.waitForTimeout(40000);

    let hasRealContent = false;
    for (const f of page.frames()) {
      try {
        const t = await f.textContent('body');
        if (t && (t.includes('Bodajk Kálvária') || t.includes('Üdvözöljük Fejér vármegyében'))) hasRealContent = true;
      } catch(e) {}
    }
    console.log(`[${i}] valós tartalom betöltött (40mp után)?`, hasRealContent);
    if (hasRealContent) successes++;
    await ctx.close();
  }
  console.log(`ÖSSZESEN: ${successes} siker (5-ből)`);
  await browser.close();
})();
