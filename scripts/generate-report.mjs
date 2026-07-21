/**
 * KH CRM 周报生成脚本
 * 从 klaviyo-data.json + shopify-data.json + calendar-data.json 生成完整报告
 */

import { readFileSync, writeFileSync, existsSync } from 'fs';
import { parseDates } from './config.mjs';

// ─── 工具函数 ───────────────────────────────────────────────
const fmtMoney = (v) => v ? `$${Number(v).toLocaleString('en-US', { minimumFractionDigits: 0, maximumFractionDigits: 0 })}` : '$0';
const fmtDec = (v, d = 2) => v ? `$${Number(v).toFixed(d)}` : '$0.00';
const fmtPct = (v, d = 1) => v != null ? `${(v * 100).toFixed(d)}%` : 'N/A';
const fmtSmallPct = (v) => v != null ? `${(v * 100).toFixed(2)}%` : 'N/A';
const safeNum = (v) => (v != null && !isNaN(v)) ? Number(v) : 0;

// ─── 行业基准 ───────────────────────────────────────────────
const BENCHMARKS = {
  campaign: {
    open_rate: { green: 0.30, yellow: 0.20, red: 0.20 },
    click_rate: { green: 0.012, yellow: 0.006, red: 0.006 },
    ctor: { green: 0.04, yellow: 0.025, red: 0.025 },
    cvr: { green: 0.0008, yellow: 0.0004, red: 0.0004 },
    rpr: { green: 0.50, yellow: 0.20, red: 0.20 },
    unsub_rate: { green: 0.003, yellow: 0.006, red: 0.006 }
  }
};

function statusIcon(value, metric, type = 'campaign') {
  const b = BENCHMARKS[type][metric];
  if (value == null) return '—';
  if (metric === 'unsub_rate') {
    if (value < b.green) return '🟢';
    if (value < b.yellow) return '🟡';
    return '🔴';
  }
  if (value >= b.green) return '🟢';
  if (value >= b.yellow) return '🟡';
  return '🔴';
}

// ─── 主函数 ────────────────────────────────────────────────
function main() {
  const { start, end, week } = parseDates();

  // 读取数据文件
  if (!existsSync('klaviyo-data.json')) {
    console.error('❌ 缺少 klaviyo-data.json，请先运行 pull-klaviyo.mjs');
    process.exit(1);
  }
  const data = JSON.parse(readFileSync('klaviyo-data.json', 'utf-8'));

  let shopify = { gmv: 0, prevGmv: 0, wow: null };
  if (existsSync('shopify-data.json')) {
    shopify = JSON.parse(readFileSync('shopify-data.json', 'utf-8'));
  }

  let calendar = { activities: [] };
  if (existsSync('calendar-data.json')) {
    calendar = JSON.parse(readFileSync('calendar-data.json', 'utf-8'));
  }

  const campaigns = (data.campaigns || []).filter(c => !c.error);
  const flows = (data.flows || []).filter(f => !f.error);

  // ─── 汇总计算 ────────────────────────────────────────────
  const campaignRevenue = campaigns.reduce((s, c) => s + safeNum(c?.attributes?.conversion_value), 0);
  const flowRevenue = flows.reduce((s, f) => s + safeNum(f?.attributes?.conversion_value), 0);
  const totalRevenue = campaignRevenue + flowRevenue;
  const campaignRecipients = campaigns.reduce((s, c) => s + safeNum(c?.attributes?.recipients), 0);
  const campaignRPR = campaignRecipients > 0 ? campaignRevenue / campaignRecipients : 0;

  // 按收入排序
  const sortedCampaigns = [...campaigns].sort((a, b) => safeNum(b?.attributes?.conversion_value) - safeNum(a?.attributes?.conversion_value));
  const sortedFlows = [...flows].sort((a, b) => safeNum(b?.attributes?.conversion_value) - safeNum(a?.attributes?.conversion_value));
  const topCampaign = sortedCampaigns[0];
  const topFlow = sortedFlows[0];

  // WoW 变化
  const gmvWow = shopify.wow != null
    ? (shopify.wow >= 0 ? `+${shopify.wow.toFixed(1)}%` : `${shopify.wow.toFixed(1)}%`)
    : 'NEW';
  const prevCampaignRevenue = prevCampaignTotal(data);
  const campWowText = calcWow(campaignRevenue, prevCampaignRevenue);
  const prevFlowRevenue = prevFlowTotal(data);
  const flowWowText = calcWow(flowRevenue, prevFlowRevenue);

  // ─── 生成 Markdown ────────────────────────────────────────
  const lines = [];

  // 页头
  lines.push(`> 周窗口：${start} ~ ${end}（${week}）｜生成：${new Date().toISOString().slice(0, 10)} US/Eastern｜数据：Klaviyo + Shopify`);
  lines.push('');

  // ═══ 一、核心要点 ═══
  lines.push('# 一、核心要点');
  lines.push('');

  // 本周数据总结
  lines.push('## 本周数据总结');
  lines.push('');
  const summaryPoints = [];
  summaryPoints.push(`1. EDM 总收入 ${fmtMoney(totalRevenue)}${totalRevenue > 0 ? '，' + (campWowText !== 'NEW' ? `Campaign WoW ${campWowText}` : `Flow 为收入主力`) : ''}`);
  if (topCampaign) {
    const tc = topCampaign.attributes || {};
    const tcName = topCampaign.name || tc.name || '';
    summaryPoints.push(`2. 最高收入 Campaign：**${tcName}**（${fmtMoney(tc.conversion_value)}，RPR ${fmtDec(tc.revenue_per_recipient)}）`);
  }
  if (topFlow) {
    const tf = topFlow.attributes || {};
    const tfName = topFlow.name || tf.name || '';
    const pct = totalRevenue > 0 ? (safeNum(tf.conversion_value) / totalRevenue * 100).toFixed(0) : 0;
    summaryPoints.push(`3. 最大 Flow：**${tfName}**（${fmtMoney(tf.conversion_value)}，占 EDM ${pct}%）`);
  }
  summaryPoints.push(`4. Shopify 整店 GMV：${fmtMoney(shopify.gmv)}（WoW ${gmvWow}）`);
  summaryPoints.forEach(p => lines.push(p));
  lines.push('');

  // 营销活动
  if (calendar.activities.length > 0) {
    lines.push('## 营销活动背景');
    lines.push('');
    lines.push('| 活动 | 类型 | 状态 |');
    lines.push('|---|---|---|');
    for (const a of calendar.activities.slice(0, 5)) {
      lines.push(`| ${a.name} | ${a.type || '—'} | ${a.status} |`);
    }
    lines.push('');
  }

  // 收入快照
  lines.push('## 收入快照');
  lines.push('');
  lines.push('| KPI | 本周数值 |');
  lines.push('|---|---|');
  lines.push(`| EDM 总收入 | ${fmtMoney(totalRevenue)} |`);
  lines.push(`| Campaign 收入 | ${fmtMoney(campaignRevenue)}（WoW ${campWowText}） |`);
  lines.push(`| Flow 收入 | ${fmtMoney(flowRevenue)}（WoW ${flowWowText}） |`);
  lines.push(`| Campaign 收件人 | ${campaignRecipients.toLocaleString()} |`);
  lines.push(`| Campaign RPR | ${fmtDec(campaignRPR)} |`);
  lines.push(`| Shopify GMV | ${fmtMoney(shopify.gmv)}（WoW ${gmvWow}） |`);
  if (shopify.gmv > 0 && totalRevenue > 0) {
    const ratio = (totalRevenue / shopify.gmv * 100).toFixed(0);
    lines.push(`| EDM 占整店收入比 | ${ratio}% |`);
  }
  lines.push('');

  // ═══ 二、数据诊断 ═══
  lines.push('# 二、数据诊断与行动建议');
  lines.push('');

  // 2.1 Campaign
  lines.push('## 2.1 Campaign 活动邮件');
  lines.push('');

  lines.push('### 行业基准 — 高客单价健身器材 DTC');
  lines.push('');
  lines.push('| 指标 | 健康 🟢 | 观察 🟡 | 告警 🔴 |');
  lines.push('|---|---|---|---|');
  lines.push('| Open Rate | > 30% | 20-30% | < 20% |');
  lines.push('| Click Rate | > 1.2% | 0.6-1.2% | < 0.6% |');
  lines.push('| CTOR | > 4% | 2.5-4% | < 2.5% |');
  lines.push('| CVR | > 0.08% | 0.04-0.08% | < 0.04% |');
  lines.push('| RPR | > $0.50 | $0.20-$0.50 | < $0.20 |');
  lines.push('| Unsub Rate | < 0.3% | 0.3-0.6% | ≥ 0.6% |');
  lines.push('');

  if (sortedCampaigns.length > 0) {
    lines.push('### 本周发送邮件');
    lines.push('');
    lines.push('| 名称 | 收件人 | 打开率 | 点击率 | CTOR | CVR | RPR | AOV | 收入 | 退订率 |');
    lines.push('|---|---|---|---|---|---|---|---|---|---|');

    for (const c of sortedCampaigns) {
      const a = c.attributes || {};
      const name = a.name || c.name || '';
      const recipients = safeNum(a.recipients);
      const or = safeNum(a.open_rate);
      const cr = safeNum(a.click_rate);
      const ctor = safeNum(a.click_to_open_rate);
      const cvr = safeNum(a.conversion_rate);
      const rpr = safeNum(a.revenue_per_recipient);
      const aov = safeNum(a.average_order_value);
      const rev = safeNum(a.conversion_value);
      const unsub = safeNum(a.unsubscribe_rate);

      lines.push(`| ${name} | ${recipients.toLocaleString()} | ${fmtPct(or)} ${statusIcon(or, 'open_rate')} | ${fmtPct(cr)} ${statusIcon(cr, 'click_rate')} | ${fmtPct(ctor)} ${statusIcon(ctor, 'ctor')} | ${fmtPct(cvr, 2)} ${statusIcon(cvr, 'cvr')} | ${fmtDec(rpr)} ${statusIcon(rpr, 'rpr')} | ${fmtMoney(aov)} | ${fmtMoney(rev)} | ${fmtPct(unsub)} ${statusIcon(unsub, 'unsub_rate')} |`);
    }
    lines.push('');
  } else {
    lines.push('⚠️ 本周无 Campaign 数据');
    lines.push('');
  }

  // 2.2 Flows
  lines.push('## 2.2 自动化流程');
  lines.push('');

  if (sortedFlows.length > 0) {
    lines.push('| 流程名 | 本周收入 | 触达人数 | RPR | AOV | 健康状态 |');
    lines.push('|---|---|---|---|---|---|');

    for (const f of sortedFlows) {
      const a = f.attributes || {};
      const name = a.name || f.name || '';
      const rev = safeNum(a.conversion_value);
      const recipients = safeNum(a.recipients);
      const rpr = safeNum(a.revenue_per_recipient);
      const aov = safeNum(a.average_order_value);
      const health = rev > 0 ? '🟢 正常' : '⚪ 零收入';

      lines.push(`| ${name} | ${fmtMoney(rev)} | ${recipients.toLocaleString()} | ${fmtDec(rpr)} | ${fmtMoney(aov)} | ${health} |`);
    }
    lines.push('');
  } else {
    lines.push('⚠️ 本周无 Flow 数据');
    lines.push('');
  }

  // 2.3 订阅者健康
  lines.push('## 2.3 订阅者健康');
  lines.push('');
  const avgUnsub = campaigns.length > 0
    ? campaigns.reduce((s, c) => s + safeNum(c?.attributes?.unsubscribe_rate), 0) / campaigns.length
    : 0;
  lines.push('| 指标 | 数值 | 评估 |');
  lines.push('|---|---|---|');
  lines.push(`| Campaign 平均退订率 | ${fmtPct(avgUnsub)} | ${avgUnsub < 0.003 ? '🟢 健康' : avgUnsub < 0.006 ? '🟡 观察' : '🔴 告警'} |`);
  lines.push(`| 最大单封退订率 | ${sortedCampaigns.length > 0 ? fmtPct(Math.max(...sortedCampaigns.map(c => safeNum(c?.attributes?.unsubscribe_rate)))) : 'N/A'} | — |`);
  lines.push('');

  // ═══ 三、优先行动 ═══
  lines.push('# 三、优先行动');
  lines.push('');
  lines.push('| 优先级 | 待办事项 | 方向 | ETA |');
  lines.push('|---|---|---|---|');
  lines.push('| P0 | 查看飞书完整报告获取详细分析 | — | — |');
  lines.push(`| P1 | 优化 Campaign CTOR（如低于行业基准） | Campaign | ${end.slice(0, 7)}-28 |`);
  lines.push(`| P2 | 跟进零收入 Flow 的触发配置检查 | Flow | ${end.slice(0, 7)}-30 |`);
  lines.push('');

  // 写入文件
  const filename = `kh-crm-weekly-${week}.md`;
  writeFileSync(filename, lines.join('\n'));
  console.log(`✅ 报告已生成: ${filename}`);

  // ─── 生成 Bitable JSON ──────────────────────────────────
  if (campaigns.length > 0) {
    const campRows = campaigns.map(c => {
      const a = c.attributes || {};
      const name = a.name || c.name || '';
      return [name, safeNum(a.recipients), safeNum(a.open_rate) * 100, safeNum(a.click_rate) * 100, safeNum(a.conversion_value), safeNum(a.revenue_per_recipient)];
    });
    const campJson = {
      fields: ['fldtiJHFVW', 'fldvpTn4qd', 'fldNJ4yHVZ', 'fldtHAd9wx'],
      rows: campRows.map(r => [r[0], r[2], r[3], r[4]])
    };
    writeFileSync('bitable-campaign.json', JSON.stringify(campJson, null, 2));
    console.log('✅ Bitable Campaign 数据已生成');
  }

  if (flows.length > 0) {
    const flowRows = flows.map(f => {
      const a = f.attributes || {};
      const name = a.name || f.name || '';
      return [name, safeNum(a.conversion_value), safeNum(a.recipients), safeNum(a.revenue_per_recipient), safeNum(a.average_order_value)];
    });
    const flowJson = {
      fields: ['fldMaP5ctZ', 'fldkYacEOe', 'fld12UFKyE', 'fld1bQ7LEA'],
      rows: flowRows.map(r => [r[0], r[1], r[2], r[3]])
    };
    writeFileSync('bitable-flow.json', JSON.stringify(flowJson, null, 2));
    console.log('✅ Bitable Flow 数据已生成');
  }
}

// ─── 辅助函数 ───────────────────────────────────────────────
function prevCampaignTotal(data) {
  // 简单版 — 实际场景可从 klaviyo-data-prev.json 读取
  return 0;
}

function prevFlowTotal(data) {
  return 0;
}

function calcWow(current, previous) {
  if (!previous || previous === 0) return 'NEW';
  const change = ((current - previous) / Math.abs(previous)) * 100;
  return change >= 0 ? `+${change.toFixed(1)}%` : `${change.toFixed(1)}%`;
}

main();
