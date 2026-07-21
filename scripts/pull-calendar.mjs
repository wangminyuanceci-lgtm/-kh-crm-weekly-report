/**
 * 飞书营销日历拉取脚本
 * 从 Bitable 读取 Marketing Calendar 数据
 */

import fetch from 'node-fetch';
import { parseDates } from './config.mjs';
import { writeFileSync } from 'fs';

const APP_ID = process.env.FEISHU_APP_ID;
const APP_SECRET = process.env.FEISHU_APP_SECRET;

if (!APP_ID || !APP_SECRET) {
  console.warn('⚠️ 缺少 FEISHU_APP_ID 或 FEISHU_APP_SECRET，跳过日历查询');
  writeFileSync('calendar-data.json', JSON.stringify({ activities: [] }));
  process.exit(0);
}

const BASE_TOKEN = 'F2pVbsy0OaaocEsQeuYcJKkHnBI';
const TABLE_ID = 'tblladSdv4Aj4Zgm';

async function getTenantToken() {
  const res = await fetch('https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ app_id: APP_ID, app_secret: APP_SECRET })
  });
  const json = await res.json();
  if (json.code !== 0) throw new Error(`飞书授权失败: ${json.msg}`);
  return json.tenant_access_token;
}

async function main() {
  const { start, end, week } = parseDates();
  console.log(`📅 拉取营销日历: ${start} ~ ${end} (${week})`);

  const token = await getTenantToken();

  // 查询 Bitable 中的活动记录
  const res = await fetch(
    `https://open.feishu.cn/open-apis/bitable/v1/apps/${BASE_TOKEN}/tables/${TABLE_ID}/records?page_size=20`,
    { headers: { 'Authorization': `Bearer ${token}` } }
  );
  const json = await res.json();

  const records = json.data?.items || [];
  const activities = records.map(r => {
    const fields = r.fields;
    return {
      name: fields['活动名称'] || fields['邮件主题'] || '',
      date: fields['发送日期'] || fields['具体日期'] || '',
      type: fields['邮件主题类型'] || fields['活动类型'] || '',
      status: fields['是否完成'] ? '已完成' : '进行中'
    };
  });

  const result = { week, window: { start, end }, activities };
  writeFileSync('calendar-data.json', JSON.stringify(result, null, 2));
  console.log(`  找到 ${activities.length} 条活动记录`);
  console.log('✅ 日历数据已保存');
}

main().catch(e => { console.error('❌', e); process.exit(1); });
