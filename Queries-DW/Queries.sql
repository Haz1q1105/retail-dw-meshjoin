use retail_dw;

-- Queries from the DW  

-- Q2 Customer demographics by purchase amount with city category
select c.gender,c.age_group,c.city_category,SUM(f.revenue) as purchase_amount from
fact_sales f
JOIN dim_customer c on c.customer_key = f.customer_key
GROUP BY c.gender, c.age_group, c.city_category
ORDER BY c.city_category;

--  Q3 total sales for each product category, by customer occupation.
select p.product_category, c.occupation, SUM(f.revenue) as total_sales
from fact_sales f
JOIN dim_product p on p.product_key = f.product_key
JOIN dim_customer c on c.customer_key = f.customer_key
GROUP BY p.product_category, c.occupation 
ORDER BY total_sales desc;

-- Q4. Total purchases by gender and age group with quarterly trend
select c.gender, c.age_group, t.quarter_num, SUM(f.revenue) as total_sales
from fact_sales f
JOIN dim_customer c ON c.customer_key = f.customer_key
JOIN dim_time t ON t.time_key = f.time_key
WHERE t.year_num = 2011
GROUP BY c.gender, c.age_group, t.quarter_num
ORDER BY c.gender, c.age_group, t.quarter_num;

-- Q7 the average purchase amount, by years in current city and gender.
select c.gender , c.stay_in_current_city_years , ROUND(AVG(f.revenue), 2) AS average_purchase 
from fact_sales f
JOIN dim_customer c on c.customer_key = f.customer_key
GROUP BY c.gender , c.stay_in_current_city_years
ORDER BY c.stay_in_current_city_years, c.gender;

-- Q14. Seasonal analysis of product sales
select t.season,p.product_name , SUM(f.revenue) as total_sales 
from fact_sales f
JOIN dim_product p on p.product_key = f.product_key
JOIN dim_time t on t.time_key = f.time_key
GROUP BY p.product_name,t.season
ORDER BY p.product_name, t.season;

-- Q10 Weekend vs weekday sales by age group
select c.age_group,t.day_type, SUM(f.revenue) as totl_sale
from fact_sales f
JOIN dim_customer c ON c.customer_key = f.customer_key
JOIN dim_time t ON t.time_key = f.time_key
WHERE year_num = "2011"
GROUP BY c.age_group, t.day_type;


-- Q6. City category performance by marital status with monthly breakdown
-- Latest six months present in the DW: July 2011 to December 2011
-- (the last loaded date is 9 December 2011, so December is a partial month)
SELECT c.city_category, c.marital_status, t.year_num, t.month_num,
       SUM(f.revenue) AS total_purchase
FROM fact_sales f
JOIN dim_customer c ON c.customer_key = f.customer_key
JOIN dim_time t     ON t.time_key = f.time_key
WHERE t.full_date BETWEEN '2011-07-01' AND '2011-12-31'
GROUP BY c.city_category, c.marital_status, t.year_num, t.month_num
ORDER BY c.city_category, c.marital_status, t.year_num, t.month_num;

-- Q13. Detailed supplier sales contribution by store and product name
-- Grouped by store, then supplier, then product name.
-- pct_of_store = this row's share of that store's total revenue
SELECT s.store_name, sp.supplier_name, p.product_name,
       SUM(f.revenue) AS total_sales,
       ROUND(100 * SUM(f.revenue) / SUM(SUM(f.revenue)) OVER (PARTITION BY s.store_name), 2)
           AS pct_of_store
FROM fact_sales f
JOIN dim_store s     ON s.store_key = f.store_key
JOIN dim_supplier sp ON sp.supplier_key = f.supplier_key
JOIN dim_product p   ON p.product_key = f.product_key
GROUP BY s.store_name, sp.supplier_name, p.product_name
ORDER BY s.store_name, sp.supplier_name, p.product_name;

-- Q18. Revenue and volume by product for the two halves of the year
-- Loaded year used: 2011. H1 = January-June, H2 = July-December
SELECT p.product_id, p.product_name,
       SUM(CASE WHEN t.half_year = 'H1' THEN f.quantity ELSE 0 END) AS h1_quantity,
       SUM(CASE WHEN t.half_year = 'H1' THEN f.revenue  ELSE 0 END) AS h1_revenue,
       SUM(CASE WHEN t.half_year = 'H2' THEN f.quantity ELSE 0 END) AS h2_quantity,
       SUM(CASE WHEN t.half_year = 'H2' THEN f.revenue  ELSE 0 END) AS h2_revenue,
       SUM(f.quantity) AS year_quantity,
       SUM(f.revenue)  AS year_revenue
FROM fact_sales f
JOIN dim_product p ON p.product_key = f.product_key
JOIN dim_time t    ON t.time_key = f.time_key
WHERE t.year_num = 2011
GROUP BY p.product_id, p.product_name
ORDER BY year_revenue DESC;

-- Q20. View STORE_QUARTERLY_SALES: total quarterly sales by store
CREATE OR REPLACE VIEW STORE_QUARTERLY_SALES AS
SELECT s.store_name, t.year_num, t.quarter_num, SUM(f.revenue) AS total_sales
FROM fact_sales f
JOIN dim_store s ON s.store_key = f.store_key
JOIN dim_time t  ON t.time_key = f.time_key
GROUP BY s.store_name, t.year_num, t.quarter_num;

-- MySQL does not keep ORDER BY inside CREATE VIEW, so the ordering goes here
SELECT * FROM STORE_QUARTERLY_SALES
ORDER BY store_name, year_num, quarter_num;
