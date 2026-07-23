# data/ — 每周输入数据

## 数据源优先级(2026-05 起)

| 数据 | 优先源 | 兜底源 |
|---|---|---|
| 产品销售数据 | MySQL `amazon_sales` | `产品销售数据.xlsx` |
| 产品分类表 | MySQL `product_map` | `产品分类表.xlsx` |
| BI 广告数据 | MySQL `bi_ad_weekly` | `BI数据集.xlsx` |
| 广告位报告 | MySQL `ad_placement` | `广告位报告.xlsx` |
| BulkSheetExport(7 sheet) | — | `BulkSheetExport.xlsx`(强制 Excel) |
| 产品库存 | — | `产品库存.xlsx`(强制 Excel) |

MySQL 连不上 / 表不存在 / SELECT 返回空 时,自动回退到对应 Excel,控制台会打印 `[源] xxx: MySQL / Excel` 标识。

MySQL 表内列名必须与 Excel 列名一致(如 `品线` / `父ASIN` / `实收销售额`),loader 用 `SELECT *` 不做字段映射。

### 环境变量配置

```
DB_HOST              MySQL 主机
DB_PORT              MySQL 端口(默认 3306)
DB_USER              用户名
DB_PASS              密码
DB_NAME              数据库名
DB_TABLE_SALES       销售表名      (默认 amazon_sales)
DB_TABLE_PRODUCT_MAP 产品分类表名  (默认 product_map)
DB_TABLE_BI_AD       BI 广告表名   (默认 bi_ad_weekly)
DB_TABLE_PLACEMENT   广告位表名    (默认 ad_placement)
```

依赖:`pip install pymysql`(纯 Python,免编译)。

---

每周一份子目录:`data-YYYYMMDD/`(取该周数据导出日期),内含 5 份 xlsx。

## 必有的 5 份文件(命名固定)

| 文件名 | 来源 | 内容 |
|---|---|---|
| `产品销售数据.xlsx` | ERP / BI 导出 | 含 `品线`/`产品线`/`子ASIN`/`SKU`/`父ASIN`/`产品类型`/`实收销售额`/`客单价`/`ROAS`/`Sessions`/`转化率`/`订单量`/`销量`/`销售天数` |
| `产品分类表.xlsx` | 产品管理 | 含 `子ASIN`/`ASIN`/`品线`/`产品线`/`父ASIN` 映射 |
| `产品库存.xlsx` | ERP / 库存系统 | 含 `品线`/`产品线`/`子ASIN`/`SKU`/`父ASIN`/`产品类型`/`亚马逊可用库存量`/`可售天数`/`日销` |
| `BI数据集.xlsx` | BI 系统 | 含 `品线`/`产品线`/`广告类型`/`广告活动编号`/`Campaign Name`/`Advertised ASIN`/`Spend`/`Impressions`/`Clicks`/`Orders`/`Sales` |
| `BulkSheetExport.xlsx` | Amazon 卖家中心 → Bulk Operations | 含 7 个 sheet(下面详述) |

## BulkSheetExport.xlsx 必有的 7 个 Sheet

1. `Sponsored Products Campaigns`
2. `Sponsored Brands Campaigns`
3. `Sponsored Display Campaigns`
4. `SP Search Term Report`
5. `SB Search Term Report`
6. `广告位报告`(中文 sheet 名,Placement Report)

完整字段说明见根目录 [SKILL.md](../SKILL.md)。

---

## 目录命名约定

- 用 `data-MMDD/`(无 0 前缀年份)以匹配脚本默认值
- 例:5/19 那周数据 → `data-0519/`,5/26 那周 → `data-0526/`
- 历史周保留方便回查 — 不删

## 校验脚本

```bash
python scripts/test.py --data-dir data/data-MMDD
```

会校验 5 个文件齐全 + 关键字段完整。

## 不放入此目录的

- ❌ 临时下载/解压文件
- ❌ 包含 `~$` 前缀的 Excel 锁文件
- ❌ 其他格式数据(csv/json)

如本周数据有异常(列名变化、单位变化),记录到 `data-MMDD/CHANGELOG.md`(可选)。
