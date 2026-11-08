create database if not exists Retail_dw;
use Retail_dw;

DROP VIEW  IF EXISTS STORE_QUARTERLY_SALES;
DROP TABLE IF EXISTS fact_sales;
DROP TABLE IF EXISTS dim_customer, dim_product, dim_supplier, dim_store, dim_time;
DROP TABLE IF EXISTS customer_md, product_md, periodic_sales_data, shed_table;

CREATE TABLE dim_store 
(
    store_key INT AUTO_INCREMENT PRIMARY KEY,
    store_id  INT NOT NULL UNIQUE,
    store_name VARCHAR(50) NOT NULL,
    city VARCHAR(30) NOT NULL
);

CREATE TABLE dim_customer 
(
    customer_key INT AUTO_INCREMENT PRIMARY KEY,
    customer_id  varchar(50) unique NOT NULL,
    gender varchar(10),
    age_group varchar(50),
    occupation varchar(20),
    city_category varchar(1),
    stay_in_current_city_years varchar(3),
    marital_status varchar(10)
);

CREATE TABLE dim_product
(
  product_key int auto_increment primary key,
  product_id varchar(20) not null unique ,
  product_name varchar(100),
  product_category varchar(35)
  
);

create table dim_supplier
(
   supplier_key int auto_increment primary key,
   supplier_id varchar(10) not null unique,
   supplier_name varchar(50)

);

create table dim_time
(
time_key int auto_increment primary key,
full_datetime datetime not null unique,
full_date date,
hour_of_day TINYINT,
day_of_month TINYINT,
month_num TINYINT,
quarter_num TINYINT,
year_num SMALLINT,
day_name VARCHAR(20),
day_type varchar(20),
season varchar(20),
half_year varchar(2)

);

create table fact_sales
(
 sale_key BIGINT auto_increment primary key,
 transaction_id varchar(10) not null,
 customer_key int not null,
 product_key int not null,
 supplier_key int not null,
 store_key int not null,
 time_key int not null,
 quantity int not null,
 revenue decimal(12,2) not null,
 sales_mode varchar(15),
 processing_mode varchar(15),
 foreign key (customer_key) REFERENCES dim_customer(customer_key),
 FOREIGN KEY (product_key) REFERENCES dim_product(product_key),
 FOREIGN KEY (supplier_key) REFERENCES dim_supplier(supplier_key),
 FOREIGN KEY (store_key) REFERENCES dim_store(store_key),
 FOREIGN KEY (time_key) REFERENCES dim_time(time_key)
);

-- ===== Working tables (used during ETL, not part of the star) =====

-- Customer Master Data, read by MESHJOIN 500 rows at a time
create table customer_md
(
    customer_id varchar(50) primary key,
    gender varchar(10),
    age_group varchar(50),
    occupation varchar(20),
    city_category varchar(1),
    stay_in_current_city_years varchar(3),
    marital_status varchar(10)
);

-- Product Master Data, read by MESHJOIN 500 rows at a time
create table product_md
(
    product_id varchar(20) primary key,
    product_name varchar(100),
    product_category varchar(35),
    supplier_id varchar(10),
    supplier_name varchar(50)
);

-- Staging table for store (periodic) sales, released in 48 hourly groups
create table periodic_sales_data
(
    id int auto_increment primary key,
    transaction_id varchar(10) not null,
    customer_id varchar(50) not null,
    product_id varchar(20) not null,
    quantity int not null,
    unit_price decimal(10,2) not null,
    event_time datetime not null,
    sales_mode varchar(15) not null,
    release_hour int not null,
    released tinyint not null default 0
);

-- Periodic transactions shed to disk when MESHJOIN is too busy
create table shed_table
(
    id int auto_increment primary key,
    transaction_id varchar(10) not null,
    customer_id varchar(50) not null,
    product_id varchar(20) not null,
    quantity int not null,
    unit_price decimal(10,2) not null,
    event_time datetime not null,
    sales_mode varchar(15) not null,
    shed_time datetime not null
);
