/**
 * Shopify GMV 拉取脚本 (Admin GraphQL API)
 * 通过 Client Credentials Grant 认证
 */

import fetch from 'node-fetch';
import { parseDates, getPrevWeek } from './config.mjs';
import { writeFileSync } from 'fs';

const STORE = process.env.SHOPIFY_STORE || 'kangaroohoppers';
const TOKEN = process.env.SHOPIFY_ACCESS_TOKEN;

if (!TOKEN) {
  console.warn('⚠️ 缺少 SHOPIFY_ACCESS_TOKEN，跳过 GMV 查询');
  process.exit(0);
}

const API = `https://${STORE}.myshopify.com/admin/api/2024-10/graphql.json`;

async function shopify(query) {
  const res = await fetch(API, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'X-Shopify-Admin-Access-Token': TOKEN
    },
    body: JSON.stringify({ query })
  });
  const json = await res.json();
  if (json.errors) throw new Error(JSON.stringify(json.errors));
  return json.data;
}

async function main() {
  const { start, end, week } = parseDates();
  const prev = getPrevWeek(start, end);

  console.log(`📅 GMV 窗口: ${start} ~ ${end} (${week})`);

  // 查询本周 GMV
  const query = `
  {
    orders(first: 250, query: "created_at:>=${start} created_at:<=${end}") {
      edges {
        node {
          totalPriceSet {
            shopMoney {
              amount
            }
          }
        }
      }
    }
  }`;

  const data = await shopify(query);
  const orders = data.orders.edges || [];
  const totalGmv = orders.reduce((sum, o) => {
    return sum + parseFloat(o.node.totalPriceSet.shopMoney.amount || 0);
  }, 0);

  // 查询对比周 GMV
  const prevQuery = `
  {
    orders(first: 250, query: "created_at:>=${prev.start} created_at:<=${prev.end}") {
      edges {
        node {
          totalPriceSet {
            shopMoney {
              amount
            }
          }
        }
      }
    }
  }`;
  const prevData = await shopify(prevQuery);
  const prevOrders = prevData.orders.edges || [];
  const prevGmv = prevOrders.reduce((sum, o) => {
    return sum + parseFloat(o.node.totalPriceSet.shopMoney.amount || 0);
  }, 0);

  // WoW 变化
  const wow = prevGmv > 0 ? ((totalGmv - prevGmv) / prevGmv * 100).toFixed(1) : 'NEW';
  const wowSign = wow !== 'NEW' && parseFloat(wow) >= 0 ? '+' : '';

  console.log(`  本周 GMV: $${totalGmv.toLocaleString('en-US', { minimumFractionDigits: 2 })}`);
  console.log(`  对比周 GMV: $${prevGmv.toLocaleString('en-US', { minimumFractionDigits: 2 })}`);
  console.log(`  WoW: ${wowSign}${wow}%`);

  // 输出
  writeFileSync('shopify-gmv.txt', String(Math.round(totalGmv)));
  writeFileSync('shopify-data.json', JSON.stringify({
    week,
    window: { start, end },
    prevWindow: prev,
    gmv: Math.round(totalGmv),
    prevGmv: Math.round(prevGmv),
    wow: wow !== 'NEW' ? parseFloat(wow) : null,
    orderCount: orders.length
  }, null, 2));

  console.log('✅ GMV 数据已保存');
}

main().catch(e => { console.error('❌', e); process.exit(1); });
