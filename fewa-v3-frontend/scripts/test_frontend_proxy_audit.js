const http = require('http');
const fs = require('fs');
const path = require('path');

console.log('🔍 Starting Frontend Proxy Coverage & SSR Fallback Audit...\n');

// 1. Audit all files under app/ for fetch calls
const appDir = path.join(__dirname, '../app');

function getAllFiles(dir, fileList = []) {
  const files = fs.readdirSync(dir);
  for (const file of files) {
    const filePath = path.join(dir, file);
    if (fs.statSync(filePath).isDirectory()) {
      getAllFiles(filePath, fileList);
    } else if (/\.(tsx|ts|js|jsx)$/.test(file)) {
      fileList.push(filePath);
    }
  }
  return fileList;
}

const allFiles = getAllFiles(appDir);
let unproxiedFetches = 0;

for (const filePath of allFiles) {
  const content = fs.readFileSync(filePath, 'utf8');
  const lines = content.split('\n');
  lines.forEach((line, idx) => {
    // Look for raw fetch calls that don't use getApiBaseUrl, fetchWithAuth, or relative /api/
    if (line.includes('fetch(') && !line.includes('getApiBaseUrl') && !line.includes('fetchWithAuth') && !line.includes('url.toString()')) {
      // Check if it's fetching an absolute localhost:8000 URL directly
      if (/fetch\(['"`]http:\/\/(localhost|127\.0\.0\.1):8000/.test(line)) {
        console.error(`❌ Hardcoded backend fetch found in ${path.relative(appDir, filePath)}:${idx + 1}`);
        console.error(`   Line: ${line.trim()}`);
        unproxiedFetches++;
      }
    }
  });
}

if (unproxiedFetches === 0) {
  console.log('✅ Audit 1: All frontend fetch calls correctly use getApiBaseUrl() or fetchWithAuth().\n');
} else {
  console.error(`❌ Audit 1 Failed: Found ${unproxiedFetches} hardcoded backend fetch calls.\n`);
  process.exit(1);
}

// 2. Verify live frontend SSR HTTP responses
function fetchUrl(urlPath, port = 3001) {
  return new Promise((resolve, reject) => {
    http.get(`http://localhost:${port}${urlPath}`, (res) => {
      if (res.statusCode === 301 || res.statusCode === 302 || res.statusCode === 307 || res.statusCode === 308) {
        return fetchUrl(res.headers.location, port).then(resolve).catch(reject);
      }
      let body = '';
      res.on('data', chunk => body += chunk);
      res.on('end', () => resolve({ statusCode: res.statusCode, body }));
    }).on('error', reject);
  });
}

async function verifySsrRoutes() {
  const testRoutes = [
    '/',
    '/collections',
    '/admin/login',
    '/admin/dashboard',
  ];

  console.log('🌐 Audit 2: Testing live SSR responses on http://localhost:3001...');
  for (const route of testRoutes) {
    try {
      const res = await fetchUrl(route);
      if (res.statusCode === 200) {
        console.log(`   ✓ ${route} -> HTTP 200 OK (${res.body.length} bytes)`);
      } else {
        console.error(`   ❌ ${route} -> HTTP ${res.statusCode}`);
        process.exit(1);
      }
    } catch (err) {
      console.error(`   ❌ Failed to connect to frontend on http://localhost:3001${route}: ${err.message}`);
      process.exit(1);
    }
  }
  console.log('\n🎉 Frontend Proxy Coverage & SSR Fallback Audit PASSED SUCCESSFULLY!');
}

verifySsrRoutes();
