const { chromium } = require('playwright');

const frontendUrl = process.env.FRONTEND_URL || 'http://127.0.0.1:3001';
const email = process.env.DEMO_CURATOR_EMAIL || 'curator@vmk.hu';
const password = process.env.DEMO_CURATOR_PASSWORD || 'SecretPassword123!';

async function main() {
  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage();

  try {
    await page.goto(`${frontendUrl}/admin/login`, { waitUntil: 'networkidle' });
    await page.getByLabel('Könyvtáros Email').fill(email);
    await page.getByLabel('Jelszó').fill(password);
    await page.getByRole('button', { name: 'Bejelentkezés' }).click();
    await page.waitForURL('**/admin/dashboard', { timeout: 10_000 });

    const body = await page.locator('body').innerText();
    if (body.includes("Unexpected token '<'")) {
      throw new Error('The login page rendered a raw HTML/JSON parse error.');
    }
    if (!body.includes('FEWA Admin Dashboard')) {
      throw new Error('The authenticated dashboard did not render.');
    }
    console.log(`LOGIN_FLOW_PASS ${page.url()}`);
  } finally {
    await browser.close();
  }
}

main().catch((error) => {
  console.error(`LOGIN_FLOW_FAIL: ${error.message}`);
  process.exit(1);
});
