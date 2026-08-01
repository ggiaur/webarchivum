const { spawn, execSync } = require('child_process');
const http = require('http');

console.log('🚀 Starting Comprehensive 14-Route Frontend Audit...\n');

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

async function runTests() {
  await new Promise(r => setTimeout(r, 3000));

  const routes = [
    { path: '/', expectedStatus: 200, name: 'Home Page Main' },
    { path: '/?category=%C3%96nkorm%C3%A1nyzatok%20%26%20Hivatalok', expectedStatus: 200, name: 'Category: Önkormányzatok' },
    { path: '/?category=Helyi%20Sajt%C3%B3%20%26%20M%C3%A9dia', expectedStatus: 200, name: 'Category: Sajtó & Média' },
    { path: '/?category=Kultur%C3%A1lis%20%26%20K%C3%B6nyvt%C3%A1ri%20%C3%96r%C3%B6ks%C3%A9g', expectedStatus: 200, name: 'Category: Kulturális Örökség' },
    { path: '/collections', expectedStatus: 200, name: 'Collections Overview' },
    { path: '/documents/550e8400-e29b-41d4-a716-446655440090', expectedStatus: 200, name: 'Doc: Székesfehérvár MJV' },
    { path: '/documents/550e8400-e29b-41d4-a716-446655440091', expectedStatus: 200, name: 'Doc: VMK Évkönyv' },
    { path: '/documents/550e8400-e29b-41d4-a716-446655440092', expectedStatus: 200, name: 'Doc: Dunaújváros MJV' },
    { path: '/documents/550e8400-e29b-41d4-a716-446655440093', expectedStatus: 200, name: 'Doc: Mór Város' },
    { path: '/documents/550e8400-e29b-41d4-a716-446655440094', expectedStatus: 200, name: 'Doc: FEOL Megyei Sajtó' },
    { path: '/documents/550e8400-e29b-41d4-a716-446655440095', expectedStatus: 200, name: 'Doc: DUOL Hírlap' },
    { path: '/documents/550e8400-e29b-41d4-a716-446655440096', expectedStatus: 200, name: 'Doc: SZIKM Múzeum' },
    { path: '/admin/login', expectedStatus: 200, name: 'Admin Login Page' },
    { path: '/admin/dashboard', expectedStatus: 200, name: 'Admin Dashboard Page' }
  ];

  let passed = 0;
  let failed = 0;
  const errorsDetected = [];

  for (const route of routes) {
    try {
      const res = await fetchUrl(route.path);

      if (res.statusCode !== route.expectedStatus) {
        errorsDetected.push(`Route ${route.path} returned status ${res.statusCode}, expected ${route.expectedStatus}`);
        failed++;
        continue;
      }

      const errorKeywords = ['Server Error', 'Cannot find module', 'webpack-runtime', 'TypeError', 'Unhandled Rejection'];
      for (const kw of errorKeywords) {
        if (res.body.includes(kw)) {
          errorsDetected.push(`Route ${route.path} contained runtime error keyword '${kw}' in response body!`);
        }
      }

      if (res.body.length > 500 && errorsDetected.length === 0) {
        console.log(`  ✓ PASSED [${passed + 1}/${routes.length}]: ${route.name} (${route.path}) -> HTTP ${res.statusCode} (${res.body.length} bytes)`);
        passed++;
      } else {
        console.error(`  ❌ FAILED: ${route.name} (${route.path})`);
        failed++;
      }
    } catch (err) {
      console.error(`  ❌ FAILED: ${route.name} (${route.path}) -> ${err.message}`);
      failed++;
    }
  }

  const forbiddenLogKeywords = ['Cannot find module', 'webpack-runtime', 'TypeError:', 'UnhandledPromiseRejection'];
  for (const kw of forbiddenLogKeywords) {
    if (serverOutput.includes(kw)) {
      errorsDetected.push(`Server log contains forbidden error keyword: '${kw}'`);
    }
  }

  server.kill('SIGTERM');

  console.log(`\n==================================================`);
  console.log(`Comprehensive Audit Results: ${passed}/${routes.length} PASSED, ${failed} FAILED`);
  if (errorsDetected.length > 0) {
    console.log(`\n🚨 DETECTED RUNTIME ERRORS:\n` + errorsDetected.join('\n'));
  }
  console.log(`==================================================\n`);

  if (failed > 0 || errorsDetected.length > 0) {
    process.exit(1);
  } else {
    process.exit(0);
  }
}

runTests().catch(err => {
  server.kill('SIGTERM');
  console.error(err);
  process.exit(1);
});
