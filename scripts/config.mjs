/**
 * 日期计算工具
 */

/**
 * 获取 ISO 周数
 */
export function getISOWeek(dateStr) {
  const d = new Date(dateStr);
  const dayNum = (d.getDay() + 6) % 7;
  d.setDate(d.getDate() - dayNum + 3);
  const jan4 = new Date(d.getFullYear(), 0, 4);
  const weekNum = 1 + Math.round(((d - jan4) / 86400000 - 3 + (jan4.getDay() + 6) % 7) / 7);
  return `W${String(weekNum).padStart(2, '0')}`;
}

/**
 * 获取当前周窗口（默认 KH）
 */
export function parseDates() {
  const args = process.argv.slice(2);
  const startIdx = args.indexOf('--start');
  const endIdx = args.indexOf('--end');
  const start = startIdx !== -1 ? args[startIdx + 1] : null;
  const end = endIdx !== -1 ? args[endIdx + 1] : null;

  if (start && end) return { start, end, week: getISOWeek(end) };

  // 自动计算上周一到上周日 (UTC+8)
  const now = new Date();
  const dayOfWeek = now.getDay(); // 0=Sun
  const daysSinceMonday = dayOfWeek === 0 ? 6 : dayOfWeek - 1;
  const lastMonday = new Date(now);
  lastMonday.setDate(now.getDate() - daysSinceMonday - 7);
  const lastSunday = new Date(now);
  lastSunday.setDate(now.getDate() - daysSinceMonday - 1);

  const fmt = (d) => d.toISOString().slice(0, 10);
  return {
    start: fmt(lastMonday),
    end: fmt(lastSunday),
    week: getISOWeek(fmt(lastSunday))
  };
}

/**
 * 计算对比周
 */
export function getPrevWeek(start, end) {
  const s = new Date(start);
  const e = new Date(end);
  s.setDate(s.getDate() - 7);
  e.setDate(e.getDate() - 7);
  return {
    start: s.toISOString().slice(0, 10),
    end: e.toISOString().slice(0, 10)
  };
}

/**
 * 获取近四周起始
 * 以 end 为基准，往前推 4 周
 */
export function getFourWeeksRange(end) {
  const e = new Date(end);
  const s = new Date(e);
  s.setDate(s.getDate() - 27); // 4周 = 28天，取整周到上周一
  const e2 = new Date(e);
  e2.setDate(e2.getDate());
  return {
    start: s.toISOString().slice(0, 10),
    end: e.toISOString().slice(0, 10)
  };
}
