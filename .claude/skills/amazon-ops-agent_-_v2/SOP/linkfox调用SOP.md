# linkfox 调用 SOP — 外部数据接入

> 触发:本地 5 份数据文件看不到所需信息时
> 前置:`linkfoxagent` skill 已装好(API key 在 `~/.claude/settings.json` 用户级 env)
> 验证可用:在对话框直接调用 linkfoxagent skill 测试

---

## 何时该调 linkfox

本地数据文件**看得到**的(不要调 linkfox,直接读 reports/data 即可):
- 自家销售额/订单/客单价/Sessions/转化率
- 自家广告 Spend/Sales/ACOS/CVR
- 自家库存量/可售天数
- 自家关键词 Search Term 表现

本地数据文件**看不到**的(需调 linkfox):

| 需求 | 调用类型 |
|---|---|
| 竞品 ASIN 当前价格 | 竞品价格查询 |
| 竞品 ASIN BSR 历史趋势(30/60/90 天) | BSR 趋势 |
| 自家 ASIN 历史 BSR 走势 | BSR 趋势 |
| 关键词外部搜索量 | 关键词分析 |
| Listing 评分/评论历史 | Listing 监控 |
| 新冲品判断(某 ASIN 是不是最近几周冲入 Top 10) | BSR 趋势 |
| 自家 ASIN 历史价格变化 | 价格历史 |

---

## 调用模式

### 模式 A:数据缺口型(Agent 主动判断要调)

下钻过程中发现"现有数据回答不了" → 主动告诉用户"我要调 linkfox 查 X" → 调用 → 把结果融入分析。

### 模式 B:用户指定型(用户明确说"查竞品")

```
用户: 查 ASIN B0XXXXX 的过去 30 天 BSR 趋势
Agent: [调用 linkfoxagent skill] → 返回数据 → 1 句话提炼结论
```

---

## 调用 prompt 模板

### 1. 竞品价格查询

```
查 ASIN [B0XXXXX] 当前售价 + 是否有 Coupon/Deal + 主图是否有促销标
```

### 2. BSR 趋势

```
查 ASIN [B0XXXXX] 过去 [30/60/90] 天的 BSR 趋势,告诉我:
- 起始 BSR / 当前 BSR / 最高 / 最低
- 关键变化点(如从 XXX 跌到 XXX 发生在哪一周)
```

### 3. 新冲品判断

```
查类目 [XXX] Top 20 ASIN 列表,标出过去 30 天内首次进入 Top 20 的新品
```

### 4. 关键词外部搜索量

```
查关键词 "[keyword]" 在 Amazon 美国的:
- 月搜索量
- Top 3 排名 ASIN
- 是否有明显的季节性
```

### 5. Listing 评分历史

```
查 ASIN [B0XXXXX] 过去 90 天的:
- 评分变化(从 X.X 到 X.X)
- 评论数增长
- 是否有差评集中涌入的时段
```

---

## 结果用法(重要)

### ✅ 该这么用

1. **提炼成 1-2 句结论** 写到归因里
   > "linkfox 显示 B07XXX 30 天 BSR 从 1500 → 720,新竞品冲击是排名下降主因"

2. **作为根因证据** 写到 actions.md 的 `根因:` 字段
   ```markdown
   - 根因: 单周 ACOS 240%, 8 周均值 95% (linkfox: 竞品 B07XXX 新冲入 Top 5)
   ```

3. **支撑动作建议** 给具体数字而非笼统判断
   > "竞品价 $279(linkfox)→ 建议跟随定价 $279"

### ❌ 不要这么用

- 原样贴大段 JSON / 表格(运营看不懂,污染上下文)
- 复制 linkfox 返回的全部字段(只挑 2-3 个关键数字)
- 把外部数据当唯一证据(要和本地数据交叉验证)

---

## 兜底

`linkfoxagent` skill 调失败时:

1. 报错 → 检查 API key:`echo $LINKFOXAGENT_API_KEY | head -c 30`
2. 仍失败 → 告诉用户"linkfox 暂时不可用,本次归因只能基于本地数据,需要外部数据时手动查 Amazon 后台 / Helium10 / Jungle Scout"
3. 不要因为外部数据缺就拒绝出诊断 — 本地数据足以做 80% 的判断
