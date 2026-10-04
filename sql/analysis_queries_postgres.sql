-- Olist E-Commerce Analysis - SQL queries
-- PostgreSQL version (generated from analysis_queries.sql by scripts/09_postgres.py).
-- Revenue = item price of delivered orders (freight is reported separately).

DROP VIEW IF EXISTS vw_order_items_enriched;
CREATE VIEW vw_order_items_enriched AS
SELECT
    oi.order_id,
    oi.order_item_id,
    o.order_status,
    o.order_purchase_timestamp,
    to_char(o.order_purchase_timestamp, 'YYYY-MM') AS order_month,
    c.customer_unique_id,
    c.customer_state,
    oi.seller_id,
    s.seller_state,
    COALESCE(t.product_category_name_english, p.product_category_name, 'unknown') AS category,
    oi.price,
    oi.freight_value
FROM order_items oi
JOIN orders o               ON o.order_id = oi.order_id
JOIN customers c            ON c.customer_id = o.customer_id
LEFT JOIN products p        ON p.product_id = oi.product_id
LEFT JOIN category_translation t ON t.product_category_name = p.product_category_name
LEFT JOIN sellers s         ON s.seller_id = oi.seller_id;

DROP VIEW IF EXISTS vw_order_delivery;
CREATE VIEW vw_order_delivery AS
SELECT
    o.order_id,
    o.customer_id,
    ROUND(EXTRACT(EPOCH FROM (o.order_delivered_customer_date - o.order_purchase_timestamp)) / 86400, 1) AS delivery_days,
    CASE
        WHEN o.order_delivered_customer_date IS NULL THEN 'Not Delivered'
        WHEN o.order_delivered_customer_date > o.order_estimated_delivery_date THEN 'Late'
        ELSE 'On Time'
    END AS delivery_status,
    r.review_score
FROM orders o
LEFT JOIN (
    SELECT order_id, AVG(review_score) AS review_score
    FROM reviews
    GROUP BY order_id
) r ON r.order_id = o.order_id;

-- name: 01_monthly_revenue_mom_growth
-- Monthly revenue, AOV, month-over-month growth and running total (CTE + LAG + SUM OVER)
WITH monthly AS (
    SELECT
        order_month,
        COUNT(DISTINCT order_id) AS orders,
        ROUND(SUM(price), 2)     AS revenue
    FROM vw_order_items_enriched
    WHERE order_status = 'delivered'
    GROUP BY order_month
)
SELECT
    order_month,
    orders,
    revenue,
    ROUND(revenue / orders, 2) AS avg_order_value,
    ROUND(100.0 * (revenue - LAG(revenue) OVER (ORDER BY order_month))
          / LAG(revenue) OVER (ORDER BY order_month), 2) AS mom_growth_pct,
    ROUND(SUM(revenue) OVER (ORDER BY order_month), 2) AS running_revenue
FROM monthly
ORDER BY order_month;

-- name: 02_category_revenue_share
-- Top categories with revenue share and rank (window aggregate + RANK)
SELECT
    category,
    COUNT(DISTINCT order_id) AS orders,
    ROUND(SUM(price), 2)     AS revenue,
    ROUND(100.0 * SUM(price) / SUM(SUM(price)) OVER (), 2) AS revenue_share_pct,
    RANK() OVER (ORDER BY SUM(price) DESC) AS revenue_rank
FROM vw_order_items_enriched
WHERE order_status = 'delivered'
GROUP BY category
ORDER BY revenue DESC
LIMIT 15;

-- name: 03_state_performance
-- Revenue, customers and AOV by customer state
SELECT
    customer_state,
    COUNT(DISTINCT customer_unique_id) AS customers,
    COUNT(DISTINCT order_id)           AS orders,
    ROUND(SUM(price), 2)               AS revenue,
    ROUND(SUM(price) / COUNT(DISTINCT order_id), 2) AS avg_order_value,
    ROUND(AVG(freight_value), 2)       AS avg_freight_per_item
FROM vw_order_items_enriched
WHERE order_status = 'delivered'
GROUP BY customer_state
ORDER BY revenue DESC;

-- name: 04_repeat_customer_rate
-- How many customers come back? (CTE + conditional aggregation)
WITH customer_orders AS (
    SELECT c.customer_unique_id, COUNT(DISTINCT o.order_id) AS order_count
    FROM orders o
    JOIN customers c ON c.customer_id = o.customer_id
    WHERE o.order_status = 'delivered'
    GROUP BY c.customer_unique_id
)
SELECT
    COUNT(*) AS total_customers,
    SUM(CASE WHEN order_count > 1 THEN 1 ELSE 0 END) AS repeat_customers,
    ROUND(100.0 * SUM(CASE WHEN order_count > 1 THEN 1 ELSE 0 END) / COUNT(*), 2) AS repeat_rate_pct
FROM customer_orders;

-- name: 05_late_delivery_vs_review
-- Does late delivery hurt review score?
SELECT
    delivery_status,
    COUNT(*)                     AS orders,
    ROUND(AVG(delivery_days), 1) AS avg_delivery_days,
    ROUND(AVG(review_score), 2)  AS avg_review_score,
    ROUND(100.0 * SUM(CASE WHEN review_score <= 2 THEN 1 ELSE 0 END) / COUNT(review_score), 2) AS bad_review_pct
FROM vw_order_delivery
WHERE delivery_status <> 'Not Delivered'
GROUP BY delivery_status;

-- name: 06_seller_scorecard
-- Top 20 sellers by revenue with late % and review score (multi-table join + HAVING)
SELECT
    e.seller_id,
    e.seller_state,
    COUNT(DISTINCT e.order_id) AS orders,
    ROUND(SUM(e.price), 2)     AS revenue,
    ROUND(100.0 * COUNT(DISTINCT CASE WHEN d.delivery_status = 'Late' THEN e.order_id END)
          / COUNT(DISTINCT e.order_id), 2) AS late_pct,
    ROUND(AVG(d.review_score), 2) AS avg_review_score
FROM vw_order_items_enriched e
JOIN vw_order_delivery d ON d.order_id = e.order_id
WHERE e.order_status = 'delivered'
GROUP BY e.seller_id, e.seller_state
HAVING COUNT(DISTINCT e.order_id) >= 30
ORDER BY revenue DESC
LIMIT 20;

-- name: 07_payment_type_mix
-- Payment method share and average installments
SELECT
    payment_type,
    COUNT(DISTINCT order_id)     AS orders,
    ROUND(SUM(payment_value), 2) AS payment_value,
    ROUND(100.0 * SUM(payment_value) / SUM(SUM(payment_value)) OVER (), 2) AS value_share_pct,
    ROUND(AVG(payment_installments), 1) AS avg_installments
FROM payments
GROUP BY payment_type
ORDER BY payment_value DESC;

-- name: 08_top3_categories_per_state
-- Top 3 categories inside each state (ROW_NUMBER with PARTITION BY)
WITH state_category AS (
    SELECT customer_state, category, ROUND(SUM(price), 2) AS revenue
    FROM vw_order_items_enriched
    WHERE order_status = 'delivered'
    GROUP BY customer_state, category
),
ranked AS (
    SELECT *, ROW_NUMBER() OVER (PARTITION BY customer_state ORDER BY revenue DESC) AS rn
    FROM state_category
)
SELECT customer_state, rn AS category_rank, category, revenue
FROM ranked
WHERE rn <= 3
ORDER BY customer_state, rn;

-- name: 09_rfm_scores
-- RFM scoring in SQL using NTILE (segment counts)
WITH last_date AS (
    SELECT MAX(order_purchase_timestamp) AS max_ts FROM orders
),
rfm AS (
    SELECT
        customer_unique_id,
        ((SELECT max_ts FROM last_date)::date - MAX(order_purchase_timestamp)::date) AS recency_days,
        COUNT(DISTINCT order_id) AS frequency,
        SUM(price)               AS monetary
    FROM vw_order_items_enriched
    WHERE order_status = 'delivered'
    GROUP BY customer_unique_id
),
scored AS (
    SELECT *,
        NTILE(5) OVER (ORDER BY recency_days DESC) AS r_score,
        NTILE(5) OVER (ORDER BY monetary)          AS m_score
    FROM rfm
)
SELECT
    r_score,
    m_score,
    COUNT(*)                    AS customers,
    ROUND(AVG(recency_days), 0) AS avg_recency_days,
    ROUND(AVG(frequency), 2)    AS avg_frequency,
    ROUND(AVG(monetary), 2)     AS avg_monetary
FROM scored
GROUP BY r_score, m_score
ORDER BY r_score DESC, m_score DESC;

-- name: 10_delivery_time_by_state
-- Slowest states: average delivery days and late % (subquery join)
SELECT
    c.customer_state,
    COUNT(*)                       AS delivered_orders,
    ROUND(AVG(d.delivery_days), 1) AS avg_delivery_days,
    ROUND(100.0 * SUM(CASE WHEN d.delivery_status = 'Late' THEN 1 ELSE 0 END) / COUNT(*), 2) AS late_pct,
    ROUND(AVG(d.review_score), 2)  AS avg_review_score
FROM vw_order_delivery d
JOIN customers c ON c.customer_id = d.customer_id
WHERE d.delivery_status <> 'Not Delivered'
GROUP BY c.customer_state
ORDER BY avg_delivery_days DESC;
