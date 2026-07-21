/**
 * 飞书群消息推送脚本
 * 推送周报摘要到运营群
 */

import fetch from 'node-fetch';
import { readFileSync } from 'fs';
import { parseDates } from './config.mjs';

const APP_ID = process.env.FEISHU_APP_ID;
const APP_SECRET = process.env.FEISHU_APP_SECRET;
const CHAT_ID = process.env.FEISHU_CHAT_ID;

if (!APP_ID || !APP_SECRET) {
  console.warn('⚠️ 缺少 FEISHU_APP_ID 或 FEISHU_APP_SECRET，跳过群发');
  process.exit(0);
}

if (!CHAT_ID) {
  console.warn('⚠️ 缺少 FEISHU_CHAT_ID，跳过群发');
  process.exit(0);
}

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
}

async function main() {
  const { start, end, week } = parseDates();

  await getTenantToken();

  // 读取 klaviyo-data.json 获取摘要数据
  let totalRevenue = 0;
  let campaignRevenue = 0;
  let flowRevenue = 0;
  let topFlowName = '';
  let topFlowRevenue = 0;

  try {
    const data = JSON.parse(readFileSync('klaviyo-data.json', 'utf-8'));

    const campaigns = data.campaigns || [];
    const flows = data.flows || [];

    campaignRevenue = campaigns.reduce((s, c) => s + (c?.attributes?.conversion_value || 0), 0);
    flowRevenue = flows.reduce((s, f) => s + (f?.attributes?.conversion_value || 0), 0);
    totalRevenue = campaignRevenue + flowRevenue;

    // 找最大收入的 Flow
    for (const f of flows) {
      const rev = f?.attributes?.conversion_value || 0;
      if (rev > topFlowRevenue) {
        topFlowRevenue = rev;
        topFlowName = f.name || '';
      }
    }
  } catch {
    console.warn('⚠️ 无法读取 klaviyo-data.json');
  }

  // 计算 WoW 变化（用本地文件名判断是否有上周数据）
  let wowText = '';
  if (totalRevenue > 0) {
    try {
      const prevData = JSON.parse(readFileSync('klaviyo-data-prev.json', 'utf-8'));
      const prevTotal = (prevData.campaigns || []).reduce((s, c) => s + (c?.attributes?.conversion_value || 0), 0)
        + (prevData.flows || []).reduce((s, f) => s + (f?.attributes?.conversion_value || 0), 0);
      const change = prevTotal > 0 ? ((totalRevenue - prevTotal) / prevTotal * 100).toFixed(1) : '+NEW';
      wowText = change.startsWith('-') ? change : `+${change}`;
    } catch {
      wowText = 'NEW';
    }
  }

  // 格式化金额
  const fmtMoney = (v) => `$${Number(v || 0).toLocaleString('en-US', { minimumFractionDigits: 0, maximumFractionDigits: 0 })}`;

  // 构建消息
  const docUrl = `https://ritfitsports.feishu.cn/docx/?title=KH+CRM+Weekly+Performance+Report+-+${week}`;
  const message = [
    `📊 KH CRM ${week} 周报已发布`,
    `周期：${start} ~ ${end}`,
    '',
    '📈 核心数据：',
    `• EDM 总收入：${fmtMoney(totalRevenue)}（WoW ${wowText}%）`,
    `• Campaign 收入：${fmtMoney(campaignRevenue)} | Flow 收入：${fmtMoney(flowRevenue)}`,
    topFlowName ? `• 最大来源：${topFlowName}（${fmtMoney(topFlowRevenue)}）` : '',
    '',
    `📎 完整报告：${docUrl}`
  ].filter(Boolean).join('\n');

  // 发送消息
  const res = await fetch('https://open.feishu.cn/open-apis/im/v1/messages?receive_id_type=chat_id', {
    method: 'POST',
    headers: {
      'Authorization': `Bearer ${tenantToken}`,
      'Content-Type': 'application/json'
    },
    body: JSON.stringify({
      receive_id: CHAT_ID,
      msg_type: 'text',
      content: JSON.stringify({ text: message })
    })
  });

  const json = await res.json();
  if (json.code === 0) {
    console.log('✅ 群消息推送成功');
  } else {
    console.error(`❌ 群消息推送失败: ${json.msg}`);
    process.exit(1);
  }
}

main().catch(e => { console.error('❌', e); process.exit(1); });
