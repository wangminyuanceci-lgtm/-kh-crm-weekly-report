/**
 * Shopify GMV 拉取脚本 (Admin GraphQL API)
 * 支持两种鉴权方式：
 *   1. STATIC TOKEN: SHOPIFY_ACCESS_TOKEN 环境变量
 *   2. CLIENT CREDENTIALS: SHOPIFY_CLIENT_ID + SHOPIFY_CLIENT_SECRET 环境变量
 */

import fetch from 'node-fetch';
import { parseDates, getPrevWeek } from './config.mjs';
import { writeFileSync } from 'fs';

const STORE = process.env.SHOPIFY_STORE || 'kangaroohoppers';
const API_VERSION = process.env.SHOPIFY_API_VERSION || '2026-04';

// ─── 获取访问令牌 ───────────────────────────────────────────
async function getAccessToken() {
  // 方式1: 直接使用静态 Token
  if (process.env.SHOPIFY_ACCESS_TOKEN) {
    console.log('🔑 使用静态 Access Token');
    return process.env.SHOPIFY_ACCESS_TOKEN;
  }

  // 方式2: Client Credentials Grant (OAuth)
  const clientId = process.env.SHOPIFY_CLIENT_ID;
  const clientSecret = process.env.SHOPIFY_CLIENT_SECRET;
  if (clientId && clientSecret) {
    console.log('🔑 使用 Client Credentials Grant');
    const tokenRes = await fetch(
      `https://${STORE}.myshopify.com/admin/oauth/access_token`,
      {
        method: 'POST',
        headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
        body: new URLSearchParams({
          grant_type: 'client_credentials',
          client_id: clientId,
          client_secret: clientSecret
        })
      }
    );
    if (!tokenRes.ok) {
      const text = await tokenRes.text();
      throw new Error(`OAuth token 获取失败: ${tokenRes.status} ${text.slice(0, 200)}`);
    }
    const tokenJson = await tokenRes.json();
    return tokenJson.access_token;
  }

  throw new Error('缺少 Shopify 认证信息：请设置 SHOPIFY_ACCESS_TOKEN 或 SHOPIFY_CLIENT_ID + SHOPIFY_CLIENT_SECRET');
}

// ─── GraphQL 查询 ──────────────────────────────────────────
async function shopifyQuery(token, query) {
  const res = await fetch(
    `https://${STORE}.myshopify.com/admin/api/${API_VERSION}/graphql.json`,
    {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-Shopify-Access-Token': token
      },
      body: JSON.stringify({ query })
    }
  );
  const json = await res.json();
  if (json.errors) throw new Error(JSON.stringify(json.errors));
  return json.data;
}

async function getOrdersTotal(token, startDate, endDate) {
  let total = 0;
  let hasNext = true;
  let after = null;

  while (hasNext) {
    const cursor = after ? `, after: "${after}"` : '';
    const query = `
    {
      orders(first: 250, query: "created_at:>=${startDate} created_at:<=${endDate}"${cursor}) {
        edges {
          cursor
          node {
            totalPriceSet { shopMoney { amount } }
          }
        }
        pageInfo { hasNextPage endCursor }
      }
    }`;
    const data = await shopifyQuery(token, query);
    const edges = data.orders.edges || [];
    for (const e of edges) {
      total += parseFloat(e.node.totalPriceSet.shopMoney.amount || 0);
    }
    hasNext = data.orders.pageInfo.hasNextPage;
    after = data.orders.pageInfo.endCursor;
  }
  return total;
}

// ─── 主函数 ────────────────────────────────────────────────
async function main() {
  const { start, end, week } = parseDates();
  const prev = getPrevWeek(start, end);

  console.log(`📅 GMV 窗口: ${start} ~ ${end} (${week})`);

  const token = await getAccessToken();

  // 本周 GMV
  console.log('  查询本周 GMV...');
  const totalGmv = await getOrdersTotal(token, start, end);

  // 对比周 GMV
  console.log(`  查询对比周 GMV (${prev.start} ~ ${prev.end})...`);
  const prevGmv = await getOrdersTotal(token, prev.start, prev.end);

  // WoW
  const wow = prevGmv > 0 ? ((totalGmv - prevGmv) / prevGmv * 100).toFixed(1) : 'NEW';
  const wowSign = wow !== 'NEW' && parseFloat(wow) >= 0 ? '+' : '';

  console.log(`  本周 GMV: $${Math.round(totalGmv).toLocaleString()}`);
  console.log(`  对比周: $${Math.round(prevGmv).toLocaleString()}`);
  console.log(`  WoW: ${wowSign}${wow}%`);

  writeFileSync('shopify-gmv.txt', String(Math.round(totalGmv)));
  writeFileSync('shopify-data.json', JSON.stringify({
    week, window: { start, end }, prevWindow: prev,
    gmv: Math.round(totalGmv), prevGmv: Math.round(prevGmv),
    wow: wow !== 'NEW' ? parseFloat(wow) : null
  }, null, 2));

  console.log('✅ GMV 数据已保存');
}

main().catch(e => { console.error('❌', e); process.exit(1); });
