// Direct Feishu API script - CommonJS version
const https = require('https');
const fs = require('fs');
const { execSync } = require('child_process');

const APP_ID = 'cli_aa87d12afa39dcbd';

function fetch(url, options = {}) {
  return new Promise((resolve, reject) => {
    const u = new URL(url);
    const opts = {
      hostname: u.hostname,
      path: u.pathname + u.search,
      method: options.method || 'GET',
      headers: options.headers || { 'Content-Type': 'application/json' },
    };
    const req = https.request(opts, (res) => {
      let data = '';
      res.on('data', chunk => data += chunk);
      res.on('end', () => {
        try { resolve(JSON.parse(data)); } catch(e) { resolve({ raw: data }); }
      });
    });
    req.on('error', reject);
    if (options.body) req.write(JSON.stringify(options.body));
    req.end();
  });
}

async function main() {
  // Get secret from Windows Credential Manager
  let secret = null;
  try {
    const result = execSync(
      'powershell -Command "& {Get-StoredCredential -Target \'appsecret:cli_aa87d12afa39dcbd\' | Select-Object -ExpandProperty Password}"',
      { encoding: 'utf8', timeout: 10000, shell: 'cmd.exe', windowsHide: true }
    );
    secret = result.trim();
    console.log('Got secret from keychain');
  } catch(e) {
    console.log('Failed to get secret:', e.message.substring(0, 200));
    process.exit(1);
  }

  if (!secret || secret.length < 5) {
    console.log('Invalid secret');
    process.exit(1);
  }

  // Get tenant access token
  console.log('Getting tenant access token...');
  const tokenResp = await fetch('https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal', {
    method: 'POST',
    body: { app_id: APP_ID, app_secret: secret }
  });

  if (!tokenResp.tenant_access_token) {
    console.log('Failed to get token:', JSON.stringify(tokenResp));
    process.exit(1);
  }

  const token = tokenResp.tenant_access_token;
  console.log('Got tenant access token');

  // Fetch reference document raw content
  const refDocId = 'UnifdbHjqojDnexGEy8cosKFnSh';
  console.log(`Fetching doc ${refDocId}...`);
  const docResp = await fetch(
    `https://open.feishu.cn/open-apis/docx/v1/documents/${refDocId}/raw_content`,
    { headers: { 'Authorization': `Bearer ${token}` } }
  );

  console.log('Response status:', JSON.stringify(docResp).substring(0, 300));
  if (docResp.data && docResp.data.content) {
    const content = docResp.data.content;
    console.log('Content length:', content.length);
    console.log('First 3000 chars:');
    console.log(content.substring(0, 3000));
    fs.writeFileSync('ref_doc_content.txt', content);
    console.log('\nSaved to ref_doc_content.txt');
  } else {
    console.log('Full response:', JSON.stringify(docResp).substring(0, 3000));
    fs.writeFileSync('ref_doc_response.json', JSON.stringify(docResp, null, 2));
  }
}

main().catch(e => console.error('Error:', e.message));
