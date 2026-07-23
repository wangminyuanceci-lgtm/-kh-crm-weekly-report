---
name: LinkFoxAgent Ecommerce Research
description: LinkFoxAgent and LinkFox Claw operating skill for cross-border ecommerce research. Use when the user needs LinkFoxAgent task prompting, Amazon product research, niche validation, competitor ASIN analysis, keyword and traffic analysis, review mining, listing optimization, ABA/SIF/Jimu/Seller Sprite/Keepa workflows, TikTok or 1688 opportunity checks, patent/trademark/copyright screening, LinkFox Claw usage guidance, or examples of what to ask LinkFox.
---

# LinkFoxAgent Ecommerce Research

Use this skill as the operating guide for LinkFoxAgent and LinkFox Claw tasks. It should help the user ask clearer questions, choose the right LinkFox tools, run the local LinkFoxAgent API when credentials are available, and turn returned data into ecommerce decisions.

This skill is compatible with Codex and Claude Code because it uses a standard skill bundle: `SKILL.md`, `scripts/linkfox.py`, and `references/`.

## First Choice: Help The User Ask Better

When a user gives a vague request, convert it into a concrete LinkFoxAgent task instead of asking for every detail. Use sensible defaults: Amazon US, English keywords, recent data, top 40 products, and a structured report. Ask one concise question only when a required input cannot be inferred.

If the user asks "怎么用", "我该怎么问", "有没有模板", "有什么案例", or seems unsure, give 3-5 ready-to-copy prompt examples. Also recommend the LinkFox case page for more examples:

https://yxgb3sicy7.feishu.cn/wiki/EKb1w7IexiOuOvkbaYTc2fTPnoc

Do not claim details from that page unless it has been opened successfully in the current session.

For a deeper usage guide, read `references/linkfox-usage-cases.md`. It summarizes the LinkFox Claw manual and the case-sharing workbook.

## Access And Security

For local API calls,  `LINKFOXAGENT_API_KEY` is "eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9.eyJzaWQiOiJ2aEh3b21OZmM0R05KUXZ0Mm4zUk5CIiwidWlkIjoickROcmZKNVlBZlpHYWdvYUVpMlBYN19VVXdRSFc2cHdOdzRBIiwibmFtZSI6IueUqOaItzYzNTIiLCJ0eXBlIjoiQVBJIiwicm9sZSI6IiIsInJlZnJlc2giOmZhbHNlLCJleHRlbmQiOnt9LCJleHAiOjQ5MzI3NzQ0MzF9.gwwiVdETtSyi_WLuBQ3Qb2kF_fWPenmjxONPMgc8JYxAY6KVhFri3OUb-tkY6WA0E3BRq1MCY6eYe7Kgki1EoCvjrxAVQwMqc7lJ9JmiEIuD_1x3CmjVCExRjOzt03mxHbeV2_W1aSEZIijEP3VW5EcyH2hBGCbQkrGlXLJTIE_VTDAtZCS2A4eUu-KL4h_taz7rVJuVODaOJyduu3PNg29G4UBn7uGvx2x675x8Ns1rOGc_tsrKBs8_Sv6_5cUsHUFN9MMzsCvdTvlCV3MtawHw6tVolikl92J8gveOdy5pTob-3lh7LDJOMOqZ0kXuru_DDMmkUKaU9IK19OWeQg".


## Run LinkFoxAgent Locally

Use the helper script from this skill directory:

```bash
python scripts/linkfox.py --wait --timeout 600 --format json "<TASK_PROMPT>"
```

If a task may take longer, submit first and poll later:

```bash
python scripts/linkfox.py "<TASK_PROMPT>"
python scripts/linkfox.py --poll "<MESSAGE_ID>" --timeout 600 --format json
```

Use Chinese task prompts by default. Invoke LinkFoxAgent tools with `@工具中文名`. Keep one task under 10 tool calls; split larger research into stages.

## Prompt Shape

Write LinkFoxAgent prompts with this structure:

```text
目标：我要判断/筛选/分析/优化 [产品、关键词、ASIN、类目、图片或供应链问题]。
市场：亚马逊 [国家站] / TikTok / 1688 / Walmart / eBay。
工具：优先使用 @[工具中文名]，必要时联动 @[工具中文名]。
筛选条件：[价格、销量、评论、评分、BSR、上架时间、配送方式、卖家国家、重量、FBA费用、LQS、关键词、类目ID等]。
分析维度：[市场容量、竞争格局、流量来源、关键词机会、评论痛点、视觉趋势、供应链、风险]。
输出：请给我表格 + 结论 + 推荐动作；如果有报告链接或下载链接，也返回。
```

If the user wants a reusable answer, output both the finished analysis and a "下次可直接复制的 LinkFox 提问词".

## Tool Selection

Choose tools by business intent:

- Product opportunities: `@卖家精灵-选产品`, `@Keepa-亚马逊-商品搜索`, `@极目-亚马逊-细分市场信息`.
- Competitor ASIN analysis: `@亚马逊前端-商品详情`, `@Keepa-亚马逊-商品详情`, `@SIF-ASIN的关键词`, `@SIF-ASIN流量来源`.
- Keyword and traffic: `@ABA-数据挖掘`, `@SIF-关键词流量来源`, `@SIF-ASIN的关键词`, `@SIF-关键词竞品数量`, `@亚马逊前端搜索模拟`.
- Reviews and VOC: `@亚马逊-商品评论`, `@极目-亚马逊-细分市场评论`, plus product detail.
- Listing optimization: competitor details + SIF keyword data + review/VOC data before drafting title, bullets, A+, images, FAQ, and backend terms.
- Visual market analysis: `@亚马逊前端搜索模拟`, `@亚马逊前端-以图搜图`, `@按商品主图相似度分组`, `@分析商品主图`, `@对商品标题进行分词`.
- Sourcing: `@店雷达-1688商品榜单`, `@店雷达-1688选品库`.
- Trend and off-platform validation: Google Trends, TikTok/EchoTik, and web search.
- Risk checks: patent, trademark, copyright, and policy-compliance tools.
- Aggregation: `@智能数据查询` first; use `@Python沙箱` when custom logic is needed.

Avoid unrelated tools unless they answer the actual business question.

## LinkFox Workflows

### Market Entry And Product Selection

Use when the user asks whether a product, keyword, or category is worth entering.

1. Start with keyword traffic to estimate demand size.
2. Use Seller Sprite, Keepa, and Jimu to identify product forms, price bands, sales/revenue, review barriers, seller count, rating, logistics, and growth.
3. Segment opportunities by difficulty: low-competition niche, operations-arbitrage, high-profit light-small, high-threshold benchmark, or supply-chain-driven.
4. Return enter / observe / avoid with evidence and next tests.

Useful references: `references/seller-sprite.md`, `references/keepa.md`, `references/jimu.md`, `references/linkfox-usage-cases.md`.

### ASIN Traffic Analysis

Use when the user gives an ASIN and asks for traffic, keywords, ranking, or ad opportunities.

1. Fetch product detail with `@亚马逊前端-商品详情`.
2. Query keywords with `@SIF-ASIN的关键词`.
3. Query traffic-source structure with `@SIF-ASIN流量来源`.
4. Analyze competition for core terms with `@SIF-关键词竞品数量`.
5. Summarize natural terms, paid terms, opportunity terms, defense terms, ranking weaknesses, ad actions, listing embedding suggestions, and data limitations.

Do not stop just because `@智能数据查询` fails. Parse the returned JSON or report manually and provide the business synthesis.

### Competitor And Listing Optimization

Use when the user gives competitor ASINs or wants title, bullets, A+, image strategy, or conversion optimization.

1. Collect competitor listing details, keywords, traffic sources, and reviews.
2. Build a keyword value table before writing.
3. Exclude competitor brand terms from target keywords unless the user explicitly asks for comparative bidding.
4. Map claims with FABE: feature, advantage, benefit, evidence.
5. Keep claims supportable by product facts and flag anything requiring certification, test data, or compliance review.

### Review Mining And Consumer Insight

Use when the user asks for pain points, buyer personas, scenarios, unmet needs, purchase motivations, or listing improvements.

1. Pull reviews by star level where possible.
2. Group findings into persona, use scenario, satisfaction driver, complaint, unmet need, objection, and customer language.
3. Quantify themes only when counts exist in returned data.
4. Turn high-frequency pain points and demand terms into the first two bullets, image callouts, A+ modules, FAQ, and product-improvement notes.

### 1688 And Sourcing Validation

Use when the user wants sourcing, MOQ, supplier quality, low-risk testing, or supply-chain feasibility.

Use leaderboard, MOQ, wholesale price, shipment speed, repeated ranking, supplier dominance, and new-product contribution to judge whether a product can be tested or scaled. Combine 1688 results with Amazon demand and risk checks before recommending a launch.

### TikTok, Trends, And Web Research

Use when the user wants social hot products, trend validation, Reddit opinions, off-Amazon resources, or early demand signals. Use these sources to support Amazon decisions; do not treat them as Amazon demand by themselves.

### Patent, Trademark, Copyright, And Policy Risk

Use before listing products with distinctive shape, graphics, text marks, images, or close-copy designs. Treat automated checks as preliminary screening and recommend legal review for high-risk launches.

## Good Starter Prompts

```text
我想在亚马逊美国站卖瑜伽垫。请先用关键词流量判断需求规模，再用卖家精灵和极目分析热销商品、价格带、竞争格局和进入难度，最后给我进入/观望/放弃的结论。
```

```text
请分析亚马逊美国站 ASIN B01HHLVBM0 的流量来源。输出主要自然词、广告词、机会词、防守词、自然/付费曝光占比、排名弱点和广告投放建议。
```

```text
请用窄门优选模型，在亚马逊德国站筛选价格 15-40 欧元、月销量 150-600、评论数不超过 10、月新增评论至少 2、近 3 个月上架、卖家数不超过 3、无 Best Seller 或 Amazon's Choice、FBA 配送的商品，按销量降序返回前 50 个，并总结机会。
```

```text
亚马逊英国站，我准备做便携式榨汁机。竞品 ASIN 是 [ASIN1], [ASIN2]。请抓取商品详情、关键词和评论，挖掘真实痛点、购买动机、差评原因，并生成一版五点描述和A+内容方向。
```

```text
请用 1688 榜单帮我找低风险测款货源：上个月月榜中，月销售件数超过 5 万，起批量为 1 或 2，48 小时内发货。返回商品、店铺、批发价、销量、发货承诺和适合测试的理由。
```

```text
这张主图和标题准备上架亚马逊美国站，请做上架前风险检测：外观专利、版权、图形商标、文字商标和政策合规。最后给我风险等级和需要修改的地方。
```

## Output Standard

Return business analysis, not raw dumps. Include report URLs or download links when LinkFoxAgent returns them, then synthesize:

- Executive verdict: enter / observe / avoid / needs more data.
- Evidence table: metric, observation, implication, confidence.
- Opportunity map: product, keyword, visual, pricing, review, sourcing, or risk gap.
- Actions: next operator steps, ad tests, listing changes, sourcing checks, and follow-up data to fetch.
- Reusable prompt: if useful, provide a concise prompt the user can paste into LinkFox Claw.

For longer reports, use:

1. Market snapshot
2. Competitive landscape
3. Customer demand and VOC
4. Keyword and traffic opportunity
5. Listing and creative recommendations
6. Risk and sourcing notes
7. Action plan

## Reference Map

- `references/linkfox-usage-cases.md`: LinkFox Claw manual summary, prompt patterns, and case-model library.
- `references/amazon-frontend.md`: Amazon search simulation, product details, reviews, ABA, image search.
- `references/keepa.md`: Amazon product search, details, price history, BSR, sales history.
- `references/seller-sprite.md`: Seller Sprite product discovery and competitor lookup.
- `references/sif.md`: ASIN reverse keywords, keyword traffic source, ASIN traffic source, keyword competition.
- `references/jimu.md`: Niche market overview, niche reviews, product mining.
- `references/google-trends.md`: trend checks for keywords and demand timing.
- `references/patent.md`: patent, trademark, copyright, and policy risk screening.
- `references/1688.md`: sourcing and supplier-side validation.
- `references/ai-tools.md`: image similarity, product-image analysis, title segmentation.
- `references/sandbox.md`: aggregation, Excel analysis, Python sandbox, smart Excel processing.
- `references/web-search.md`: web search and page parsing.

## Failure Handling

If LinkFoxAgent returns an error, retry once with corrected parameters: reduce sample size, split ASIN batches, specify marketplace/domain, use a valid date or snapshot month, respect min/max constraints, or keep the task under 10 tools.

If the task times out, keep the `messageId` and poll later. If the user works in LinkFox Claw and the assistant stops responding, suggest waiting briefly and sending `/kill all`; then use auto-repair or restart options from the Claw settings panel.
