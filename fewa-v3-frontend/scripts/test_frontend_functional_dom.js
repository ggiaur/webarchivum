const { spawn, execSync } = require('child_process');
const http = require('http');

console.log('🚀 Starting Deep Functional DOM & Client-Side JS Runtime Audit...\n');

// 1. Run production build
console.log('📦 Step 1: Running next build...');
try {
  execSync('npm run build', { stdio: 'inherit' });
  console.log('✓ Build compiled successfully!\n');
} catch (err) {
  console.error('❌ Build failed!');
  process.exit(1);
}

// 2. Start next start on port 3009
console.log('🌐 Step 2: Starting production server on http://localhost:3009...');
const PORT = 3009;
const server = spawn('npx', ['next', 'start', '-p', String(PORT)], {
  stdio: 'pipe',
  env: { ...process.env, PORT: String(PORT) }
});

let serverOutput = '';
server.stdout.on('data', (d) => serverOutput += d.toString());
server.stderr.on('data', (d) => serverOutput += d.toString());

function fetchUrl(urlPath) {
  return new Promise((resolve, reject) => {
    http.get(`http://localhost:${PORT}${urlPath}`, (res) => {
      let body = '';
      res.on('data', chunk => body += chunk);
      res.on('end', () => resolve({ statusCode: res.statusCode, body }));
    }).on('error', reject);
  });
}

async function runFunctionalAudit() {
  await new Promise(r => setTimeout(r, 3000));

  const routesToAudit = [
    {
      path: '/',
      name: 'Kezdőlap Hibrid Kereső',
      requiredElements: ['FEWA', 'Kereső', 'Vörösmarty Mihály Könyvtár'],
      forbiddenStrings: ['Server Error', 'TypeError', 'Cannot find module', 'Unhandled Rejection', '404 Not Found']
    },
    {
      path: '/?category=%C3%96nkorm%C3%A1nyzatok%20%26%20Hivatalok',
      name: 'Önkormányzatok Kategória',
      requiredElements: ['FEWA', 'Székesfehérvár MJV', 'Dunaújváros MJV'],
      forbiddenStrings: ['Server Error', 'TypeError', 'Cannot find module', '404 Not Found']
    },
    {
      path: '/?category=Helyi%20Sajt%C3%B3%20%26%20M%C3%A9dia',
      name: 'Sajtó & Média Kategória',
      requiredElements: ['FEWA', 'FEOL', 'DUOL'],
      forbiddenStrings: ['Server Error', 'TypeError', 'Cannot find module', '404 Not Found']
    },
    {
      path: '/?category=Kultur%C3%A1lis%20%26%20K%C3%B6nyvt%C3%A1ri%20%C3%96r%C3%B6ks%C3%A9g',
      name: 'Kulturális Örökség Kategória',
      requiredElements: ['Kulturális', 'Vörösmarty Mihály Könyvtár', 'Szent István Király Múzeum'],
      forbiddenStrings: ['Server Error', 'TypeError', 'Cannot find module', '404 Not Found']
    },
    {
      path: '/collections',
      name: 'Gyűjtemények Katalógus',
      requiredElements: ['Kurátori Tematikus Gyűjtemények', 'Önkormányzatok & Hivatalok', 'Helyi Sajtó & Média'],
      forbiddenStrings: ['Server Error', 'TypeError', 'Cannot find module', '404 Not Found']
    },
    {
      path: '/documents/550e8400-e29b-41d4-a716-446655440090',
      name: 'WARC Replay: Székesfehérvár',
      requiredElements: ['Székesfehérvár MJV Polgármesteri Hivatal Hírei', 'ISO 28500 WARC', 'WACZ Replay'],
      forbiddenStrings: ['Server Error', 'TypeError', 'Cannot find module', '404 Not Found', 'Archívum betöltése...']
    },
    {
      path: '/documents/550e8400-e29b-41d4-a716-446655440091',
      name: 'WARC Replay: VMK Évkönyv',
      requiredElements: ['Vörösmarty Mihály Könyvtár Évkönyv 2025', 'ISO 28500 WARC'],
      forbiddenStrings: ['Server Error', 'TypeError', 'Cannot find module', '404 Not Found', 'Archívum betöltése...']
    },
    {
      path: '/admin/login',
      name: 'Kurátori Bejelentkezési Portál',
      requiredElements: ['Kurátori Portál', 'Vörösmarty Mihály Könyvtár Adminisztráció'],
      forbiddenStrings: ['Server Error', 'TypeError', 'Cannot find module', '404 Not Found']
    },
    {
      path: '/admin/dashboard',
      name: 'Kurátori Admin Dashboard',
      requiredElements: ['FEWA Admin Dashboard', 'Alba Regia Portál'],
      forbiddenStrings: ['Server Error', 'TypeError', 'Cannot find module', '404 Not Found']
    }
  ];

  let passed = 0;
  let failed = 0;
  const auditErrors = [];

  console.log('🔍 Executing Deep Functional Component & Text Hierarchy Verification:\n');

  for (const route of routesToAudit) {
    try {
      const res = await fetchUrl(route.path);

      if (res.statusCode !== 200) {
        auditErrors.push(`❌ ${route.name} (${route.path}) returned HTTP ${res.statusCode}`);
        failed++;
        continue;
      }

      // Decode HTML entities in response body for robust matching
      const normalizedBody = res.body.replace(/&amp;/g, '&');

      // Check for forbidden error strings inside rendered DOM text
      let hasForbidden = false;
      for (const forbidden of route.forbiddenStrings) {
        if (normalizedBody.includes(forbidden)) {
          auditErrors.push(`❌ ${route.name} (${route.path}) contains forbidden error string: '${forbidden}'`);
          hasForbidden = true;
        }
      }

      // Check for mandatory DOM elements / text strings
      let missingElements = [];
      for (const elem of route.requiredElements) {
        if (!normalizedBody.includes(elem)) {
          missingElements.push(elem);
        }
      }

      if (missingElements.length > 0) {
        auditErrors.push(`❌ ${route.name} (${route.path}) is missing required DOM elements: [${missingElements.join(', ')}]`);
        hasForbidden = true;
      }

      if (!hasForbidden) {
        console.log(`  ✓ DOM VERIFIED [${passed + 1}/${routesToAudit.length}]: ${route.name} (${route.path}) — All required DOM nodes present & 0 errors.`);
        passed++;
      } else {
        failed++;
      }
    } catch (err) {
      auditErrors.push(`❌ ${route.name} (${route.path}) request failed: ${err.message}`);
      failed++;
    }
  }

  // Check server stdout for any background runtime errors
  const forbiddenServerKeywords = ['Cannot find module', 'webpack-runtime', 'TypeError:', 'UnhandledPromiseRejection'];
  for (const kw of forbiddenServerKeywords) {
    if (serverOutput.includes(kw)) {
      auditErrors.push(`❌ Server log contained background exception: '${kw}'`);
    }
  }

  server.kill('SIGTERM');

  console.log(`\n==================================================`);
  console.log(`Deep Functional DOM Audit: ${passed}/${routesToAudit.length} PASSED, ${failed} FAILED`);
  if (auditErrors.length > 0) {
    console.log(`\n🚨 FUNCTIONAL AUDIT FAILURES:\n` + auditErrors.join('\n'));
  }
  console.log(`==================================================\n`);

  if (failed > 0 || auditErrors.length > 0) {
    process.exit(1);
  } else {
    process.exit(0);
  }
}

runFunctionalAudit().catch(err => {
  server.kill('SIGTERM');
  console.error(err);
  process.exit(1);
});
