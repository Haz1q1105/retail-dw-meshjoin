USE retail_dw;

-- Q1: Top 5 revenue-generating products on weekdays and weekends with monthly drill-down (year used: 2011)
WITH yearly AS (
    SELECT f.product_key, t.day_type,
           RANK() OVER (PARTITION BY t.day_type ORDER BY SUM(f.revenue) DESC) AS product_rank
    FROM fact_sales f
    JOIN dim_time t ON t.time_key = f.time_key
    WHERE t.year_num = 2011
    GROUP BY f.product_key, t.day_type
)
SELECT y.day_type, y.product_rank, p.product_name, t.month_num, SUM(f.revenue) AS month_revenue
FROM yearly y
JOIN fact_sales f ON f.product_key = y.product_key
JOIN dim_time t ON t.time_key = f.time_key AND t.day_type = y.day_type AND t.year_num = 2011
JOIN dim_product p ON p.product_key = y.product_key
WHERE y.product_rank <= 5
GROUP BY y.day_type, y.product_rank, p.product_name, t.month_num
ORDER BY y.day_type, y.product_rank, t.month_num;

-- Q2: Customer demographics by purchase amount with city category
SELECT c.gender, c.age_group, c.city_category, SUM(f.revenue) AS purchase_amount
FROM fact_sales f
JOIN dim_customer c ON c.customer_key = f.customer_key
GROUP BY c.gender, c.age_group, c.city_category
ORDER BY c.city_category, c.gender, c.age_group;

-- Q3: Product category sales by occupation
SELECT p.product_category, c.occupation, SUM(f.revenue) AS total_sales
FROM fact_sales f
JOIN dim_product p ON p.product_key = f.product_key
JOIN dim_customer c ON c.customer_key = f.customer_key
GROUP BY p.product_category, c.occupation
ORDER BY p.product_category, total_sales DESC;

-- Q4: Total purchases by gender and age group with quarterly trend (year used: 2011)
SELECT c.gender, c.age_group, t.quarter_num, SUM(f.revenue) AS total_sales
FROM fact_sales f
JOIN dim_customer c ON c.customer_key = f.customer_key
JOIN dim_time t ON t.time_key = f.time_key
WHERE t.year_num = 2011
GROUP BY c.gender, c.age_group, t.quarter_num
ORDER BY c.gender, c.age_group, t.quarter_num;

-- Q5: Top 5 occupations by product category sales
WITH ranked AS (
    SELECT p.product_category, c.occupation, SUM(f.revenue) AS total_sales,
           RANK() OVER (PARTITION BY p.product_category ORDER BY SUM(f.revenue) DESC) AS occupation_rank
    FROM fact_sales f
    JOIN dim_product p ON p.product_key = f.product_key
    JOIN dim_customer c ON c.customer_key = f.customer_key
    GROUP BY p.product_category, c.occupation
)
SELECT product_category, occupation_rank, occupation, total_sales
FROM ranked
WHERE occupation_rank <= 5
ORDER BY product_category, occupation_rank;

-- Q6: City category performance by marital status with monthly breakdown (latest six months in the DW: July 2011 to December 2011)
SELECT c.city_category, c.marital_status, t.year_num, t.month_num, SUM(f.revenue) AS total_purchase
FROM fact_sales f
JOIN dim_customer c ON c.customer_key = f.customer_key
JOIN dim_time t ON t.time_key = f.time_key
WHERE t.full_date BETWEEN '2011-07-01' AND '2011-12-31'
GROUP BY c.city_category, c.marital_status, t.year_num, t.month_num
ORDER BY c.city_category, c.marital_status, t.year_num, t.month_num;

-- Q7: Average purchase amount by stay duration and gender
SELECT c.gender, c.stay_in_current_city_years, ROUND(AVG(f.revenue), 2) AS average_purchase
FROM fact_sales f
JOIN dim_customer c ON c.customer_key = f.customer_key
GROUP BY c.gender, c.stay_in_current_city_years
ORDER BY c.stay_in_current_city_years, c.gender;

-- Q8: Top revenue-generating cities by product category
SELECT p.product_category, c.city_category, SUM(f.revenue) AS total_revenue,
       RANK() OVER (PARTITION BY p.product_category ORDER BY SUM(f.revenue) DESC) AS city_rank
FROM fact_sales f
JOIN dim_product p ON p.product_key = f.product_key
JOIN dim_customer c ON c.customer_key = f.customer_key
GROUP BY p.product_category, c.city_category
ORDER BY p.product_category, city_rank;

-- Q9: Monthly sales growth by product category (year used: 2011)
WITH monthly AS (
    SELECT p.product_category, t.month_num, SUM(f.revenue) AS month_sales
    FROM fact_sales f
    JOIN dim_product p ON p.product_key = f.product_key
    JOIN dim_time t ON t.time_key = f.time_key
    WHERE t.year_num = 2011
    GROUP BY p.product_category, t.month_num
),
with_prev AS (
    SELECT product_category, month_num, month_sales,
           LAG(month_sales) OVER (PARTITION BY product_category ORDER BY month_num) AS prev_month_sales
    FROM monthly
)
SELECT product_category, month_num, month_sales, prev_month_sales,
       ROUND(100 * (month_sales - prev_month_sales) / prev_month_sales, 2) AS growth_pct
FROM with_prev
ORDER BY product_category, month_num;

-- Q10: Weekend vs weekday sales by age group (year used: 2011)
SELECT c.age_group, t.day_type, SUM(f.revenue) AS total_sales
FROM fact_sales f
JOIN dim_customer c ON c.customer_key = f.customer_key
JOIN dim_time t ON t.time_key = f.time_key
WHERE t.year_num = 2011
GROUP BY c.age_group, t.day_type
ORDER BY c.age_group, t.day_type;

-- Q11: Top 5 revenue-generating products on weekdays and weekends, grouped by month (year used: 2011)
WITH monthly AS (
    SELECT t.month_num, t.day_type, p.product_id, p.product_name, SUM(f.revenue) AS month_revenue,
           RANK() OVER (PARTITION BY t.month_num, t.day_type ORDER BY SUM(f.revenue) DESC) AS product_rank
    FROM fact_sales f
    JOIN dim_time t ON t.time_key = f.time_key
    JOIN dim_product p ON p.product_key = f.product_key
    WHERE t.year_num = 2011
    GROUP BY t.month_num, t.day_type, p.product_id, p.product_name
)
SELECT month_num, day_type, product_rank, product_name, month_revenue
FROM monthly
WHERE product_rank <= 5
ORDER BY month_num, day_type, product_rank;

-- Q12: Quarterly store revenue growth (year used: 2011)
WITH quarterly AS (
    SELECT s.store_name, t.quarter_num, SUM(f.revenue) AS quarter_revenue
    FROM fact_sales f
    JOIN dim_store s ON s.store_key = f.store_key
    JOIN dim_time t ON t.time_key = f.time_key
    WHERE t.year_num = 2011
    GROUP BY s.store_name, t.quarter_num
),
with_prev AS (
    SELECT store_name, quarter_num, quarter_revenue,
           LAG(quarter_revenue) OVER (PARTITION BY store_name ORDER BY quarter_num) AS prev_quarter_revenue
    FROM quarterly
)
SELECT store_name, quarter_num, quarter_revenue, prev_quarter_revenue,
       ROUND(100 * (quarter_revenue - prev_quarter_revenue) / prev_quarter_revenue, 2) AS growth_pct
FROM with_prev
ORDER BY store_name, quarter_num;

-- Q13: Detailed supplier sales contribution by store and product name
SELECT s.store_name, sp.supplier_name, p.product_name, SUM(f.revenue) AS total_sales,
       ROUND(100 * SUM(f.revenue) / SUM(SUM(f.revenue)) OVER (PARTITION BY s.store_name), 2) AS pct_of_store
FROM fact_sales f
JOIN dim_store s ON s.store_key = f.store_key
JOIN dim_supplier sp ON sp.supplier_key = f.supplier_key
JOIN dim_product p ON p.product_key = f.product_key
GROUP BY s.store_name, sp.supplier_name, p.product_name
ORDER BY s.store_name, sp.supplier_name, p.product_name;

-- Q14: Seasonal analysis of product sales
SELECT p.product_name, t.season, SUM(f.revenue) AS total_sales
FROM fact_sales f
JOIN dim_product p ON p.product_key = f.product_key
JOIN dim_time t ON t.time_key = f.time_key
GROUP BY p.product_name, t.season
ORDER BY p.product_name, t.season;

-- Q15: Store-wise and supplier-wise monthly revenue volatility (months used: December 2010 to December 2011)
WITH monthly AS (
    SELECT s.store_name, sp.supplier_name, t.year_num, t.month_num, SUM(f.revenue) AS month_revenue
    FROM fact_sales f
    JOIN dim_store s ON s.store_key = f.store_key
    JOIN dim_supplier sp ON sp.supplier_key = f.supplier_key
    JOIN dim_time t ON t.time_key = f.time_key
    GROUP BY s.store_name, sp.supplier_name, t.year_num, t.month_num
),
with_prev AS (
    SELECT store_name, supplier_name, year_num, month_num, month_revenue,
           LAG(month_revenue) OVER (PARTITION BY store_name, supplier_name ORDER BY year_num, month_num) AS prev_month_revenue
    FROM monthly
)
SELECT store_name, supplier_name, year_num, month_num, month_revenue, prev_month_revenue,
       ROUND(100 * (month_revenue - prev_month_revenue) / prev_month_revenue, 2) AS volatility_pct
FROM with_prev
ORDER BY store_name, supplier_name, year_num, month_num;

-- Q16: Top 5 products purchased together (one shopping cart = one transaction_id, each cart counted once per pair)
WITH cart AS (
    SELECT DISTINCT transaction_id, product_key
    FROM fact_sales
)
SELECT pa.product_name AS product_a, pb.product_name AS product_b, COUNT(*) AS carts_together
FROM cart a
JOIN cart b ON b.transaction_id = a.transaction_id AND a.product_key < b.product_key
JOIN dim_product pa ON pa.product_key = a.product_key
JOIN dim_product pb ON pb.product_key = b.product_key
GROUP BY a.product_key, b.product_key, pa.product_name, pb.product_name
ORDER BY carts_together DESC
LIMIT 5;

-- Q17: Yearly revenue by store, supplier, and product with ROLLUP (year used: 2011)
SELECT s.store_name, sp.supplier_name, p.product_name, SUM(f.revenue) AS yearly_revenue
FROM fact_sales f
JOIN dim_store s ON s.store_key = f.store_key
JOIN dim_supplier sp ON sp.supplier_key = f.supplier_key
JOIN dim_product p ON p.product_key = f.product_key
JOIN dim_time t ON t.time_key = f.time_key
WHERE t.year_num = 2011
GROUP BY s.store_name, sp.supplier_name, p.product_name WITH ROLLUP;

-- Q18: Revenue and volume by product for the two halves of the year (year used: 2011, H1 = Jan-Jun, H2 = Jul-Dec)
SELECT p.product_id, p.product_name,
       SUM(CASE WHEN t.half_year = 'H1' THEN f.quantity ELSE 0 END) AS h1_quantity,
       SUM(CASE WHEN t.half_year = 'H1' THEN f.revenue ELSE 0 END) AS h1_revenue,
       SUM(CASE WHEN t.half_year = 'H2' THEN f.quantity ELSE 0 END) AS h2_quantity,
       SUM(CASE WHEN t.half_year = 'H2' THEN f.revenue ELSE 0 END) AS h2_revenue,
       SUM(f.quantity) AS year_quantity,
       SUM(f.revenue) AS year_revenue
FROM fact_sales f
JOIN dim_product p ON p.product_key = f.product_key
JOIN dim_time t ON t.time_key = f.time_key
WHERE t.year_num = 2011
GROUP BY p.product_id, p.product_name
ORDER BY year_revenue DESC;

-- Q19: High revenue spikes (days where a product's revenue is more than twice its own daily average)
WITH daily AS (
    SELECT f.product_key, t.full_date, SUM(f.revenue) AS day_revenue
    FROM fact_sales f
    JOIN dim_time t ON t.time_key = f.time_key
    GROUP BY f.product_key, t.full_date
),
with_avg AS (
    SELECT product_key, full_date, day_revenue,
           AVG(day_revenue) OVER (PARTITION BY product_key) AS avg_daily_revenue
    FROM daily
)
SELECT p.product_name, w.full_date, w.day_revenue,
       ROUND(w.avg_daily_revenue, 2) AS avg_daily_revenue,
       ROUND(w.day_revenue / w.avg_daily_revenue, 2) AS times_average
FROM with_avg w
JOIN dim_product p ON p.product_key = w.product_key
WHERE w.day_revenue > 2 * w.avg_daily_revenue
ORDER BY times_average DESC;

-- Q20: View STORE_QUARTERLY_SALES, total quarterly sales by store (ORDER BY is on the SELECT that reads the view)
CREATE OR REPLACE VIEW STORE_QUARTERLY_SALES AS
SELECT s.store_name, t.year_num, t.quarter_num, SUM(f.revenue) AS total_sales
FROM fact_sales f
JOIN dim_store s ON s.store_key = f.store_key
JOIN dim_time t ON t.time_key = f.time_key
GROUP BY s.store_name, t.year_num, t.quarter_num;

SELECT * FROM STORE_QUARTERLY_SALES
ORDER BY store_name, year_num, quarter_num;
