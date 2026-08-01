const { chromium } = require('playwright');
const { spawn, execSync } = require('child_process');

console.log('🎭 Starting Strict Playwright Real Headless Browser Automation Audit...\n');

// 1. Run production build
console.log('📦 Step 1: Running next build...');
try {
  execSync('npm run build', { stdio: 'inherit' });
  console.log('✓ Build compiled successfully!\n');
} catch (err) {
  console.error('❌ Build failed!');
  process.exit(1);
}

// 2. Start next start on port 3010
console.log('🌐 Step 2: Starting production server on http://localhost:3010...');
const PORT = 3010;
const server = spawn('npx', ['next', 'start', '-p', String(PORT)], {
  stdio: 'pipe',
  env: { ...process.env, PORT: String(PORT) }
});

let serverLogs = '';
server.stdout.on('data', (d) => serverLogs += d.toString());
server.stderr.on('data', (d) => serverLogs += d.toString());

async function runPlaywrightAudit() {
  await new Promise(r => setTimeout(r, 3000));

  const browser = await chromium.launch({
    headless: true,
    args: ['--no-sandbox', '--disable-setuid-sandbox']
  });

  const routesToTest = [
    {
      url: `http://localhost:${PORT}/`,
      name: 'Kezdőlap (Home Page)',
      selectors: ['.logo-title', 'input[placeholder*="Keresés"]', 'button']
    },
    {
      url: `http://localhost:${PORT}/?category=%C3%96nkorm%C3%A1nyzatok%20%26%20Hivatalok`,
      name: 'Kategória: Önkormányzatok',
      selectors: ['.badge', 'h3', 'a[href*="/documents/"]']
    },
    {
      url: `http://localhost:${PORT}/collections`,
      name: 'Gyűjtemények Katalógusa',
      selectors: ['h1', '.glass-card', 'a[href*="/?category="]']
    },
    {
      url: `http://localhost:${PORT}/documents/550e8400-e29b-41d4-a716-446655440090`,
      name: 'WACZ Replay Dokumentum 1',
      selectors: ['h1', 'iframe', 'button']
    },
    {
      url: `http://localhost:${PORT}/documents/550e8400-e29b-41d4-a716-446655440091`,
      name: 'WACZ Replay Dokumentum 2',
      selectors: ['h1', 'iframe', 'button']
    },
    {
      url: `http://localhost:${PORT}/admin/login`,
      name: 'Kurátori Bejelentkezés',
      selectors: ['input[type="email"]', 'input[type="password"]', 'button']
    },
    {
      url: `http://localhost:${PORT}/admin/dashboard`,
      name: 'Kurátori Dashboard',
      selectors: ['h1', 'table', 'button']
    }
  ];

  let passed = 0;
  let failed = 0;
  const errorDetails = [];

  for (const route of routesToTest) {
    const context = await browser.newContext();
    const page = await context.newPage();

    const consoleErrors = [];
    const pageErrors = [];

    page.on('console', msg => {
      if (msg.type() === 'error') {
        consoleErrors.push(msg.text());
      }
    });

    page.on('pageerror', err => {
      pageErrors.push(err.message);
    });

    try {
      const response = await page.goto(route.url, { waitUntil: 'networkidle', timeout: 10000 });

      if (!response || response.status() !== 200) {
        errorDetails.push(`❌ ${route.name} (${route.url}) -> HTTP ${response ? response.status() : 'NO_RESPONSE'}`);
        failed++;
        await context.close();
        continue;
      }

      // Verify DOM Selectors & Visibility
      let missingSelector = false;
      for (const sel of route.selectors) {
        const isVisible = await page.isVisible(sel).catch(() => false);
        if (!isVisible) {
          errorDetails.push(`❌ ${route.name} (${route.url}) -> Missing or hidden selector: '${sel}'`);
          missingSelector = true;
        }
      }

      // Check for console / JS page errors
      if (consoleErrors.length > 0) {
        errorDetails.push(`❌ ${route.name} (${route.url}) -> Browser Console Errors:\n   ` + consoleErrors.join('\n   '));
      }
      if (pageErrors.length > 0) {
        errorDetails.push(`❌ ${route.name} (${route.url}) -> Uncaught Page Errors:\n   ` + pageErrors.join('\n   '));
      }

      if (!missingSelector && consoleErrors.length === 0 && pageErrors.length === 0) {
        console.log(`  ✓ PLAYWRIGHT VERIFIED [${passed + 1}/${routesToTest.length}]: ${route.name} -> HTTP 200 & 0 Console Errors & All Selectors Visible.`);
        passed++;
      } else {
        failed++;
      }
    } catch (err) {
      errorDetails.push(`❌ ${route.name} (${route.url}) -> Exception: ${err.message}`);
      failed++;
    }

    await context.close();
  }

  await browser.close();
  server.kill('SIGTERM');

  console.log(`\n==================================================`);
  console.log(`Playwright Browser Automation Audit: ${passed}/${routesToTest.length} PASSED, ${failed} FAILED`);
  if (errorDetails.length > 0) {
    console.log(`\n🚨 DETECTED BROWSER FAILURES:\n` + errorDetails.join('\n'));
  }
  console.log(`==================================================\n`);

  if (failed > 0 || errorDetails.length > 0) {
    process.exit(1);
  } else {
    process.exit(0);
  }
}

runPlaywrightAudit().catch(err => {
  server.kill('SIGTERM');
  console.error(err);
  process.exit(1);
});
