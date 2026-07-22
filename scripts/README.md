# KH CRM 周报 — GitHub Actions 自动化部署

每周一北京时间 13:00 自动拉取 KH (Kangaroo Hoppers) 的 Klaviyo + Shopify 数据 → 生成 CRM 分析报告 → 推送到飞书文档 + Bitable + 运营群。

## 部署步骤

### 1. 创建 GitHub 仓库

```bash
# 在本目录下初始化
cd scripts/..
git init
git add .
git commit -m "init: KH CRM weekly report automation"

# 推送到 GitHub（需先创建空仓库）
gh repo create kh-crm-weekly-report --public --push
# 或手动创建后：
git remote add origin https://github.com/<你的用户名>/kh-crm-weekly-report.git
git push -u origin main
```

### 2. 配置 GitHub Secrets

在仓库 **Settings → Secrets and variables → Actions → New repository secret** 添加以下 5 个 Secret：

| Secret | 来源 | 用途 |
|--------|------|------|
| `KLAVIYO_PRIVATE_KEY` | KH Klaviyo 后台 → Settings → API Keys | 拉取 Campaign/Flow 数据 |
| `FEISHU_APP_ID` | 飞书开发者后台 → 创建自建应用 | lark-cli 鉴权（文档 & Bitable & 消息） |
| `FEISHU_APP_SECRET` | 同上 | 飞书应用密钥 |
| `FEISHU_CHAT_ID` | 运营群 → 设置 → 群 ID | 固定值：`oc_26d179f6e297fa35731cf03cd6a5a118` |
| `KH_SHOPIFY_STORE` | Shopify 店铺域名前缀 | `kangaroohoppers` |
| `KH_SHOPIFY_CLIENT_ID` | Shopify 后台 → 应用 → Dev Dashboard | OAuth Client ID |
| `KH_SHOPIFY_CLIENT_SECRET` | 同上 | OAuth Client Secret |

### 3. Klaviyo API Key 权限

Key 需要以下 scope：
- `campaigns:read`
- `flows:read`
- `metrics:read`
- `profiles:read`

### 4. 飞书自建应用权限

自建应用需要以下权限：
- `docx:document:readonly` — 文档读取
- `docx:document:write` — 文档创建/写入
- `base:record:read` — Bitable 读取
- `base:record:write` — Bitable 写入
- `im:message` — 发送群消息
- `im:message.send_as_user` — 以用户身份发送（如需）

发布后需管理员审批。

---

## 工作流程

`.github/workflows/weekly-crm-report.yml` 自动执行：

1. **周一 13:00 CST**（`0 5 * * 1` UTC）触发
2. 安装依赖（node-fetch + @larksuite/cli）
3. 初始化 lark-cli（非交互式，通过 FEISHU_APP_ID/FEISHU_APP_SECRET）
4. 拉取 Klaviyo 上周数据（Campaigns + Flows）
5. 拉取 Shopify GMV（Admin GraphQL API）
6. 拉取飞书营销日历
7. 生成结构化 Markdown 报告
8. 发布到飞书文档（lark-cli docs +create/+update）
9. 写入 Bitable（lark-cli base +record-batch-create）
10. 推送到运营群（lark-cli im +messages-send）
11. 上传 Markdown 产物（30 天保留）

也支持 `workflow_dispatch` 手动触发，可自定义日期范围。

---

## 文件结构

```
.github/workflows/weekly-crm-report.yml   # GitHub Actions 工作流
scripts/
├── package.json                           # 依赖声明（node-fetch）
├── config.mjs                             # 日期计算工具
├── pull-klaviyo.mjs                       # Klaviyo REST API v3 数据拉取
├── pull-shopify.mjs                       # Shopify Admin API GMV 查询
├── pull-calendar.mjs                      # 飞书 Bitable 营销日历读取
├── generate-report.mjs                    # Markdown 报告生成
├── feishu-publish.mjs                     # （本地备用）飞书文档发布
├── feishu-notify.mjs                      # （本地备用）飞书群消息推送
└── *.md / *.json                          # 运行时生成（已 gitignore）
```

## 本地测试

在本地（王敏园的机器上）可以用 lark-cli 测试飞书操作：

```bash
# 生成测试报告
cd scripts
node pull-klaviyo.mjs --start 2026-07-13 --end 2026-07-19
node pull-shopify.mjs --start 2026-07-13 --end 2026-07-19
node generate-report.mjs --start 2026-07-13 --end 2026-07-19

# 飞书发布（需 lark-cli 已登录）
WEEK=W29
lark-cli docs +create \
  --content "<title>KH CRM Weekly Performance Report - ${WEEK}</title><p></p>" \
  --api-version v2 \
  --parent-token KezUf0UI2lR27KdfBK8c4napnUh

lark-cli docs +update \
  --doc <DOC_ID> \
  --command append \
  --content @kh-crm-weekly-${WEEK}.md \
  --doc-format markdown \
  --api-version v2
```
