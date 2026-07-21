/**
 * 飞书文档发布脚本
 * 使用飞书 Open API 创建并发布报告文档
 */

import fetch from 'node-fetch';
import { readFileSync } from 'fs';
import { parseDates } from './config.mjs';

const APP_ID = process.env.FEISHU_APP_ID;
const APP_SECRET = process.env.FEISHU_APP_SECRET;

if (!APP_ID || !APP_SECRET) {
  console.warn('⚠️ 缺少 FEISHU_APP_ID 或 FEISHU_APP_SECRET，跳过飞书发布');
  process.exit(0);
}

const FOLDER_TOKEN = 'KezUf0UI2lR27KdfBK8c4napnUh';

let tenantToken = null;

async function getTenantToken() {
  const res = await fetch('https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ app_id: APP_ID, app_secret: APP_SECRET })
  });
  const json = await res.json();
  if (json.code !== 0) throw new Error(`飞书授权失败: ${json.msg}`);
  tenantToken = json.tenant_access_token;
  console.log('✅ 飞书 tenant_access_token 获取成功');
}

async function api(method, path, body) {
  const res = await fetch(`https://open.feishu.cn/open-apis${path}`, {
    method,
    headers: {
      'Authorization': `Bearer ${tenantToken}`,
      'Content-Type': 'application/json'
    },
    body: body ? JSON.stringify(body) : undefined
  });
  const json = await res.json();
  if (json.code !== 0) throw new Error(`飞书 API ${path}: ${JSON.stringify(json)}`);
  return json;
}

async function main() {
  const { start, end, week } = parseDates();

  await getTenantToken();

  // 步骤一：创建文档标题
  const title = `KH CRM Weekly Performance Report - ${week}`;
  console.log(`📝 创建文档: ${title}`);

  const createRes = await api('POST', '/docx/v1/documents', {
    folder_token: FOLDER_TOKEN,
    title
  });
  const docId = createRes.data.document.document_id;
  console.log(`   document_id: ${docId}`);

  // 步骤二：读取本地报告并追加正文
  const reportFile = `kh-crm-weekly-${week}.md`;
  let content;
  try {
    content = readFileSync(reportFile, 'utf-8');
  } catch {
    console.warn(`⚠️ 找不到 ${reportFile}，跳过追加`);
    console.log(`\n📎 飞书文档链接: https://ritfitsports.feishu.cn/docx/${docId}`);
    return;
  }

  // 飞书 API 追加 markdown 内容
  const updateRes = await api('POST', `/docx/v1/documents/${docId}/raw_content`, {
    raw_content: JSON.stringify({ content })
  });

  if (updateRes.code === 0) {
    console.log('✅ 正文追加成功');
  }

  console.log(`\n📎 飞书文档链接: https://ritfitsports.feishu.cn/docx/${docId}`);

  // 输出 docId 供后续脚本使用
  console.log(`DOC_ID=${docId}`);
}

main().catch(e => { console.error('❌', e); process.exit(1); });
