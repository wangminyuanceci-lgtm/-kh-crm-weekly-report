---
name: shopify-readonly-query
description: Query a Shopify store through the Admin API in read-only mode. Use when the user asks Codex to inspect Shopify backend data such as products, variants, inventory, locations, orders, customers, reports, or sales data using a Dev Dashboard app with Client ID and Client Secret credentials.
---

# Shopify Readonly Query

## Credentials

Use these defaults unless the user provides replacements:

```text
SHOPIFY_SHOP=ritfitness
SHOPIFY_API_VERSION=2026-04
SHOPIFY_CLIENT_ID=6fe8be59268d68c0d7a8234f916f7054
SHOPIFY_CLIENT_SECRET=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
```

Prefer environment variables or a local secret manager over hardcoding secrets into generated code, logs, commits, or chat replies. If `SHOPIFY_CLIENT_SECRET` is still a placeholder, ask the user to paste the copied Secret from Shopify Dev Dashboard before making live API calls.

## Store Identifier

For this store, derive the Admin API shop value from the Shopify admin URL:

```text
Shopify admin URL: https://admin.shopify.com/store/ritfitness
SHOPIFY_SHOP: ritfitness
Admin API host: https://ritfitness.myshopify.com
```

Do not use the store display name `RitFit`, because it may be normalized into the wrong host such as `ritfit.myshopify.com`. Do not use the storefront custom domain `www.ritfitsports.com` for Admin API authentication; it is only the customer-facing website domain.

## Read-Only Rules

Only perform read operations against Shopify:

- GraphQL Admin API: allow only `query` operations. Reject any request containing `mutation`.
- REST Admin API: allow only `GET` requests. Reject `POST`, `PUT`, `PATCH`, and `DELETE`.
- Never request, add, or rely on any `write_*` scope.
- Never create, update, delete, fulfill, refund, cancel, tag, or modify Shopify resources.
- Never print access tokens, client secrets, or full authorization headers.

Expected app scopes should be read-only, for example:

```text
read_products,read_inventory,read_locations,read_orders
```

Optional read scopes can be used only when the user's task requires them, such as `read_customers`, `read_reports`, or approved `read_all_orders`.

## Authentication

For Dev Dashboard apps used on the merchant's own store, exchange the Client ID and Client Secret for a short-lived Admin API access token with the client credentials grant.

Token endpoint:

```text
POST https://{SHOPIFY_SHOP}.myshopify.com/admin/oauth/access_token
Content-Type: application/x-www-form-urlencoded

grant_type=client_credentials
&client_id={SHOPIFY_CLIENT_ID}
&client_secret={SHOPIFY_CLIENT_SECRET}
```

Use the returned `access_token` only in memory and send it to Admin API calls as:

```text
X-Shopify-Access-Token: {access_token}
```

Before querying, verify the token response `scope` value contains only read scopes required for the task. If any `write_` scope appears, stop and tell the user the app is not read-only.

## Query Workflow

1. Confirm `SHOPIFY_SHOP`, `SHOPIFY_CLIENT_ID`, and `SHOPIFY_CLIENT_SECRET` are available.
2. Exchange credentials for an access token.
3. Build the smallest GraphQL query that answers the user's question.
4. Run only read-only GraphQL `query` operations against:

```text
https://{SHOPIFY_SHOP}.myshopify.com/admin/api/{SHOPIFY_API_VERSION}/graphql.json
```

5. Paginate with `pageInfo.hasNextPage` and cursors when needed.
6. Return a concise business answer first, then include the key fields used. Do not expose secrets or raw tokens.

## Common Queries

Products:

```graphql
query Products($first: Int!, $after: String) {
  products(first: $first, after: $after) {
    edges {
      cursor
      node {
        id
        title
        handle
        status
        totalInventory
        createdAt
        updatedAt
      }
    }
    pageInfo {
      hasNextPage
      endCursor
    }
  }
}
```

Orders:

```graphql
query Orders($first: Int!, $after: String, $query: String) {
  orders(first: $first, after: $after, query: $query, sortKey: CREATED_AT, reverse: true) {
    edges {
      cursor
      node {
        id
        name
        createdAt
        displayFinancialStatus
        displayFulfillmentStatus
        totalPriceSet {
          shopMoney {
            amount
            currencyCode
          }
        }
      }
    }
    pageInfo {
      hasNextPage
      endCursor
    }
  }
}
```

Inventory by product:

```graphql
query ProductInventory($query: String!) {
  products(first: 20, query: $query) {
    edges {
      node {
        id
        title
        variants(first: 50) {
          edges {
            node {
              id
              title
              sku
              inventoryQuantity
            }
          }
        }
      }
    }
  }
}
```

Shop identity:

```graphql
query ShopInfo {
  shop {
    name
    myshopifyDomain
    primaryDomain {
      url
    }
    currencyCode
    timezoneAbbreviation
  }
}
```

## Error Handling

- If authentication fails, check that the app is installed on the target store and the shop subdomain is correct.
- If Shopify returns a permission error, report the missing read scope and do not suggest write scopes.
- If the user asks for historical orders older than 60 days and the query fails or returns incomplete data, explain that `read_all_orders` may need Shopify approval.
- If the user asks for an action that would modify Shopify, refuse that operation and offer a read-only alternative such as previewing matching records.
