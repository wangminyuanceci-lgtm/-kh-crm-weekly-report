/**
 * Klaviyo 数据拉取脚本 (REST API v3)
 * 拉取：Campaigns、Flows、Segments + 近4周趋势
 */

import fetch from 'node-fetch';
import { parseDates, getPrevWeek } from './config.mjs';
import { writeFileSync } from 'fs';

const PRIVATE_KEY = process.env.KLAVIYO_PRIVATE_KEY;
if (!PRIVATE_KEY) {
  console.error('❌ 缺少 KLAVIYO_PRIVATE_KEY');
  process.exit(1);
}

const BASE = 'https://a.klaviyo.com/api';
const HEADERS = {
  'Authorization': `Klaviyo-API-Key ${PRIVATE_KEY}`,
  'Accept': 'application/json',
  'Revision': '2025-01-15'
};

async function api(path, params = {}) {
  const url = new URL(`${BASE}${path}`);
  Object.entries(params).forEach(([k, v]) => {
    if (Array.isArray(v)) v.forEach(item => url.searchParams.append(k, item));
    else url.searchParams.set(k, v);
  });

  const res = await fetch(url, { headers: HEADERS });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`Klaviyo API ${res.status}: ${text.slice(0, 200)}`);
  }
  return res.json();
}

async function main() {
  const { start, end, week } = parseDates();
  const prev = getPrevWeek(start, end);

  console.log(`📅 周窗口: ${start} ~ ${end} (${week})`);
  console.log(`📅 对比周: ${prev.start} ~ ${prev.end}`);

  // 1. 获取账号信息
  const account = await api('/accounts');
  const orgName = account?.data?.[0]?.attributes?.organization_name || 'KH';

  // 2. 获取转化指标 (Placed Order)
  const metrics = await api('/metrics', {
    'fields[metric]': ['name'].join(','),
    'page[size]': 50
  });
  const placedOrder = metrics.data.find(m => m.attributes.name === 'Placed Order');
  const conversionMetricId = placedOrder?.id;
  console.log(`📊 转化指标: ${placedOrder?.attributes?.name || '未找到'} (${conversionMetricId || 'N/A'})`);

  // 3. 拉取 Campaigns
  console.log('\n📨 拉取 Campaigns...');
  const campaigns = await api('/campaigns', {
    'filter': `and(equals(channel,"email"),greater-or-equal(scheduled_at,"${start}T00:00:00Z"),less-or-equal(scheduled_at,"${end}T23:59:59Z"))`,
    'fields[campaign]': 'name,status,send_time,scheduled_at',
    'page[size]': 50
  });
  console.log(`   找到 ${campaigns.data?.length || 0} 封 Campaign`);

  const campaignReports = [];
  for (const c of (campaigns.data || [])) {
    const cid = c.id;
    const cname = c.attributes.name;
    console.log(`   📄 ${cname}...`);

    try {
      if (!conversionMetricId) throw new Error('无转化指标');

      const report = await api(`/campaign-reports/${cid}`, {
        'statistics': ['recipients','open_rate','click_rate','click_to_open_rate','conversion_rate','conversion_value','revenue_per_recipient','average_order_value','unsubscribe_rate','unsubscribes','spam_complaint_rate','bounce_rate'].join(','),
        'conversion_metric_id': conversionMetricId,
        'timeframe': JSON.stringify({ value: { start, end } })
      });

      campaignReports.push({
        id: cid,
        name: cname,
        sendTime: c.attributes.send_time || c.attributes.scheduled_at,
        ...report
      });
    } catch (e) {
      console.warn(`   ⚠️ ${cname} 数据不可用: ${e.message}`);
      campaignReports.push({ id: cid, name: cname, error: e.message });
    }
  }

  // 4. 拉取 Flows
  console.log('\n🔁 拉取 Flows...');
  const flows = await api('/flows', {
    'filter': 'equals(status,"live")',
    'fields[flow]': 'name,status,trigger_type',
    'page[size]': 50
  });
  console.log(`   找到 ${flows.data?.length || 0} 个活跃 Flow`);

  const flowReports = [];
  for (const f of (flows.data || [])) {
    const fid = f.id;
    const fname = f.attributes.name;
    console.log(`   🔁 ${fname}...`);

    try {
      if (!conversionMetricId) { flowReports.push({ id: fid, name: fname, error: '无转化指标' }); continue; }

      const report = await api(`/flow-reports/${fid}`, {
        'statistics': ['recipients','open_rate','click_rate','click_to_open_rate','conversion_rate','conversion_value','revenue_per_recipient','average_order_value','unsubscribe_rate','unsubscribes'].join(','),
        'conversion_metric_id': conversionMetricId,
        'timeframe': JSON.stringify({ value: { start, end } })
      });

      flowReports.push({
        id: fid,
        name: fname,
        triggerType: f.attributes.trigger_type,
        ...report
      });
    } catch (e) {
      console.warn(`   ⚠️ ${fname} 数据不可用: ${e.message}`);
      flowReports.push({ id: fid, name: fname, error: e.message });
    }
  }

  // 5. 拉取 Segments
  console.log('\n👥 拉取 Segments...');
  const segments = await api('/segments', {
    'fields[segment]': 'name,is_active',
    'page[size]': 50
  });

  // 6. 输出结果
  const result = {
    week,
    window: { start, end },
    prevWindow: prev,
    account: { name: orgName },
    metrics: { conversionMetricId },
    campaigns: campaignReports,
    flows: flowReports,
    segments: segments.data || []
  };

  writeFileSync('klaviyo-data.json', JSON.stringify(result, null, 2));
  console.log(`\n✅ 数据已保存至 klaviyo-data.json`);
}

main().catch(e => { console.error('❌', e); process.exit(1); });
