const { chromium } = require('playwright');
(async () => {
  const browser = await chromium.launch({ ignoreHTTPSErrors: true });
  for (let i = 0; i < 5; i++) {
    const ctx = await browser.newContext({ ignoreHTTPSErrors: true, viewport: { width: 1400, height: 1200 } });
    const page = await ctx.newPage();
    let sawRegisteredLog = false;
    page.on('console', m => { if(m.text().includes('registered')) sawRegisteredLog = true; });
    await page.goto('https://teszt.vmk.hu/documents/58b99535-60a7-4a1a-bada-14bafda5a0d9/', { waitUntil: 'domcontentloaded' });
    await page.waitForTimeout(35000);
    const swState = await page.evaluate(async () => {
      const reg = await navigator.serviceWorker.getRegistration('https://teszt.vmk.hu/replay/');
      return reg ? { found: true, activeState: reg.active ? reg.active.state : null } : { found: false };
    });
    console.log(`[${i}] 35mp után: regisztrált log látszott=${sawRegisteredLog}, SW=${JSON.stringify(swState)}`);
    await ctx.close();
  }
  await browser.close();
})();
