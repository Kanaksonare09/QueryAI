USE ai_assistant_demo;

-- ─── Regions ──────────────────────────────────────────────
INSERT INTO regions (name, country, timezone) VALUES
('North America East', 'USA', 'America/New_York'),
('North America West', 'USA', 'America/Los_Angeles'),
('Europe West', 'UK', 'Europe/London'),
('Europe Central', 'Germany', 'Europe/Berlin'),
('Asia Pacific', 'Singapore', 'Asia/Singapore'),
('Latin America', 'Brazil', 'America/Sao_Paulo');

-- ─── Employees ────────────────────────────────────────────
INSERT INTO employees (first_name, last_name, email, department, role, salary, region_id, hire_date) VALUES
('James', 'Wilson', 'j.wilson@nexacorp.com', 'Sales', 'VP of Sales', 145000, 1, '2018-03-15'),
('Sarah', 'Chen', 's.chen@nexacorp.com', 'Sales', 'Sales Manager', 98000, 2, '2019-07-01'),
('Michael', 'Torres', 'm.torres@nexacorp.com', 'Sales', 'Account Executive', 72000, 3, '2020-01-15'),
('Emily', 'Nakamura', 'e.nakamura@nexacorp.com', 'Sales', 'Account Executive', 74000, 5, '2020-06-01'),
('David', 'Brown', 'd.brown@nexacorp.com', 'Marketing', 'Marketing Director', 120000, 1, '2017-11-01'),
('Lisa', 'Anderson', 'l.anderson@nexacorp.com', 'Finance', 'CFO', 190000, 1, '2015-04-01'),
('Carlos', 'Martinez', 'c.martinez@nexacorp.com', 'Sales', 'Account Executive', 69000, 6, '2021-03-01'),
('Priya', 'Sharma', 'p.sharma@nexacorp.com', 'Engineering', 'CTO', 210000, 1, '2016-08-01');

-- ─── Categories ───────────────────────────────────────────
INSERT INTO categories (name, description, parent_id) VALUES
('Software', 'Software products and licenses', NULL),
('Hardware', 'Physical hardware products', NULL),
('Services', 'Professional and managed services', NULL),
('Analytics', 'Data analytics and BI tools', 1),
('Security', 'Cybersecurity solutions', 1),
('Cloud', 'Cloud infrastructure products', 1),
('Consulting', 'Strategy and implementation consulting', 3),
('Support', 'Technical support packages', 3);

-- ─── Products ─────────────────────────────────────────────
INSERT INTO products (name, description, sku, category_id, unit_price, cost_price, stock_quantity) VALUES
('NexaAnalytics Pro', 'Advanced business analytics platform with AI insights', 'NAP-001', 4, 4999.00, 1200.00, 999),
('NexaAnalytics Enterprise', 'Enterprise analytics suite with unlimited users', 'NAE-001', 4, 14999.00, 3500.00, 999),
('SecureShield Pro', 'Enterprise endpoint security solution', 'SSP-001', 5, 2999.00, 800.00, 999),
('CloudMatrix Basic', 'Entry-level cloud infrastructure management', 'CMB-001', 6, 999.00, 200.00, 999),
('CloudMatrix Enterprise', 'Full-scale cloud orchestration platform', 'CME-001', 6, 7999.00, 2000.00, 999),
('NexaAnalytics Starter', 'Small team analytics tool, up to 10 users', 'NAS-001', 4, 1299.00, 300.00, 999),
('Implementation Consulting 10hr', '10-hour expert implementation consulting block', 'CON-010', 7, 3500.00, 700.00, 999),
('Implementation Consulting 40hr', '40-hour expert implementation consulting block', 'CON-040', 7, 12000.00, 2500.00, 999),
('Premium Support Annual', 'Annual 24/7 premium support package', 'SUP-PRE', 8, 4800.00, 960.00, 999),
('SecureShield Ultimate', 'Ultimate security suite with SOC service', 'SSU-001', 5, 8999.00, 2200.00, 999),
('DataSensor Hardware Node', 'Edge computing data collection hardware node', 'HW-DSN', 2, 1200.00, 550.00, 450),
('NexaBI Dashboard', 'Self-service business intelligence dashboard', 'NBI-001', 4, 3499.00, 850.00, 999);

-- ─── Customers ────────────────────────────────────────────
INSERT INTO customers (first_name, last_name, email, phone, region_id, segment, acquisition_date) VALUES
('Robert', 'Johnson', 'r.johnson@techcorp.io', '+1-555-0101', 1, 'Enterprise', '2020-01-15'),
('Amanda', 'Williams', 'a.williams@globalfin.com', '+1-555-0102', 2, 'Enterprise', '2020-03-22'),
('Thomas', 'Davies', 't.davies@londonmgmt.co.uk', '+44-20-5550103', 3, 'SMB', '2021-01-10'),
('Yuki', 'Tanaka', 'y.tanaka@asiapac.co', '+65-6555-0104', 5, 'Enterprise', '2020-07-05'),
('Isabella', 'Ferreira', 'i.ferreira@braziltech.com.br', '+55-11-55550105', 6, 'SMB', '2021-06-01'),
('Marcus', 'Schmidt', 'm.schmidt@deutschedata.de', '+49-30-55550106', 4, 'Enterprise', '2021-04-12'),
('Sophie', 'Laurent', 's.laurent@frenchbiz.fr', '+33-1-55550107', 3, 'SMB', '2022-02-28'),
('Kevin', 'Lee', 'k.lee@siliconval.com', '+1-408-5550108', 2, 'Enterprise', '2019-11-05'),
('Natasha', 'Petrov', 'n.petrov@eastbiz.com', '+44-20-5550109', 3, 'Individual', '2022-08-15'),
('Omar', 'Hassan', 'o.hassan@middleeast.ae', '+971-4-5550110', 5, 'SMB', '2023-01-10'),
('Grace', 'Kim', 'g.kim@koreacorp.kr', '+82-2-5550111', 5, 'Enterprise', '2020-09-20'),
('Lucas', 'Oliveira', 'l.oliveira@latam.io', '+55-21-55550112', 6, 'Individual', '2023-05-01');

-- ─── Orders (2024 — lower revenue period) ─────────────────
INSERT INTO orders (customer_id, employee_id, region_id, order_date, status, subtotal, discount_amount, tax_amount, total_amount) VALUES
-- Q1 2024
(1, 3, 1, '2024-01-12', 'completed', 29998.00, 2999.80, 2700.00, 29698.20),
(8, 2, 2, '2024-01-25', 'completed', 14999.00, 1499.90, 1350.00, 14849.10),
(4, 4, 5, '2024-02-08', 'completed', 7999.00, 0.00, 720.00, 8719.00),
(6, 3, 4, '2024-02-20', 'completed', 14999.00, 1499.90, 1350.00, 14849.10),
(3, 3, 3, '2024-03-05', 'completed', 5998.00, 599.80, 540.00, 5938.20),
(11, 4, 5, '2024-03-18', 'completed', 22997.00, 2299.70, 2070.00, 22767.30),
-- Q2 2024
(2, 2, 2, '2024-04-10', 'completed', 14999.00, 1499.90, 1350.00, 14849.10),
(1, 3, 1, '2024-04-28', 'completed', 7000.00, 0.00, 630.00, 7630.00),
(5, 7, 6, '2024-05-15', 'completed', 3498.00, 349.80, 315.00, 3463.20),
(7, 3, 3, '2024-06-02', 'completed', 1299.00, 0.00, 117.00, 1416.00),
(9, 3, 3, '2024-06-20', 'completed', 4800.00, 0.00, 432.00, 5232.00),
-- Q3 2024
(6, 3, 4, '2024-07-08', 'completed', 8999.00, 899.90, 810.00, 8909.10),
(11, 4, 5, '2024-07-22', 'completed', 4999.00, 0.00, 450.00, 5449.00),
(8, 2, 2, '2024-08-14', 'completed', 15500.00, 1550.00, 1395.00, 15345.00),
(1, 3, 1, '2024-09-03', 'completed', 12000.00, 1200.00, 1080.00, 11880.00),
(4, 4, 5, '2024-09-25', 'completed', 4800.00, 0.00, 432.00, 5232.00),
-- Q4 2024
(2, 2, 2, '2024-10-10', 'completed', 29998.00, 2999.80, 2700.00, 29698.20),
(12, 7, 6, '2024-10-28', 'completed', 1299.00, 0.00, 117.00, 1416.00),
(3, 3, 3, '2024-11-12', 'completed', 3500.00, 350.00, 315.00, 3465.00),
(10, 4, 5, '2024-12-05', 'completed', 2998.00, 0.00, 270.00, 3268.00),
(6, 3, 4, '2024-12-20', 'completed', 7998.00, 799.80, 720.00, 7918.20);

-- ─── Orders (2025 — higher revenue period) ────────────────
INSERT INTO orders (customer_id, employee_id, region_id, order_date, status, subtotal, discount_amount, tax_amount, total_amount) VALUES
-- Q1 2025
(1, 3, 1, '2025-01-08', 'completed', 44997.00, 4499.70, 4050.00, 44547.30),
(8, 2, 2, '2025-01-20', 'completed', 22998.00, 2299.80, 2070.00, 22768.20),
(4, 4, 5, '2025-02-05', 'completed', 22997.00, 0.00, 2070.00, 25067.00),
(6, 3, 4, '2025-02-18', 'completed', 29998.00, 2999.80, 2700.00, 29698.20),
(11, 4, 5, '2025-03-03', 'completed', 33996.00, 3399.60, 3060.00, 33656.40),
(2, 2, 2, '2025-03-25', 'completed', 19998.00, 1999.80, 1800.00, 19798.20),
-- Q2 2025
(1, 3, 1, '2025-04-07', 'completed', 26999.00, 2699.90, 2430.00, 26729.10),
(8, 2, 2, '2025-04-22', 'completed', 14999.00, 1499.90, 1350.00, 14849.10),
(4, 4, 5, '2025-05-14', 'completed', 16998.00, 1699.80, 1530.00, 16828.20),
(6, 3, 4, '2025-05-30', 'completed', 8999.00, 899.90, 810.00, 8909.10),
(11, 4, 5, '2025-06-12', 'completed', 9998.00, 999.80, 900.00, 9898.20),
(3, 3, 3, '2025-06-28', 'completed', 5998.00, 599.80, 540.00, 5938.20),
-- Q3 2025
(2, 2, 2, '2025-07-10', 'completed', 14999.00, 1499.90, 1350.00, 14849.10),
(1, 3, 1, '2025-07-25', 'completed', 24000.00, 2400.00, 2160.00, 23760.00),
(5, 7, 6, '2025-08-08', 'completed', 6998.00, 699.80, 630.00, 6928.20),
(10, 4, 5, '2025-08-22', 'completed', 8999.00, 0.00, 810.00, 9809.00),
(7, 3, 3, '2025-09-05', 'completed', 4799.00, 479.90, 432.00, 4751.10),
(12, 7, 6, '2025-09-20', 'completed', 2998.00, 0.00, 270.00, 3268.00),
-- Q4 2025
(1, 3, 1, '2025-10-06', 'completed', 52996.00, 5299.60, 4770.00, 52466.40),
(8, 2, 2, '2025-10-20', 'completed', 29998.00, 2999.80, 2700.00, 29698.20),
(4, 4, 5, '2025-11-10', 'completed', 22997.00, 2299.70, 2070.00, 22767.30),
(6, 3, 4, '2025-11-28', 'completed', 17998.00, 1799.80, 1620.00, 17818.20),
(11, 4, 5, '2025-12-08', 'completed', 26997.00, 2699.70, 2430.00, 26727.30),
(2, 2, 2, '2025-12-20', 'completed', 19998.00, 1999.80, 1800.00, 19798.20);

-- ─── Order Items ──────────────────────────────────────────
-- 2024 Q1-Q2 items (orders 1-11)
INSERT INTO order_items (order_id, product_id, quantity, unit_price, discount_pct, line_total) VALUES
(1, 2, 1, 14999.00, 10, 13499.10), (1, 1, 1, 4999.00, 10, 4499.10), (1, 9, 1, 4800.00, 0, 4800.00),
(2, 2, 1, 14999.00, 10, 13499.10),
(3, 5, 1, 7999.00, 0, 7999.00),
(4, 2, 1, 14999.00, 10, 13499.10),
(5, 4, 2, 999.00, 10, 1798.20), (5, 6, 1, 1299.00, 0, 1299.00), (5, 7, 1, 3500.00, 0, 3500.00),
(6, 2, 1, 14999.00, 10, 13499.10), (6, 1, 1, 4999.00, 0, 4999.00), (6, 9, 1, 4800.00, 0, 4800.00),
(7, 2, 1, 14999.00, 10, 13499.10),
(8, 8, 1, 12000.00, 0, 12000.00),
(9, 6, 1, 1299.00, 10, 1169.10), (9, 4, 2, 999.00, 0, 1998.00),
(10, 6, 1, 1299.00, 0, 1299.00),
(11, 9, 1, 4800.00, 0, 4800.00);

-- 2024 Q3-Q4 items (orders 12-21)
INSERT INTO order_items (order_id, product_id, quantity, unit_price, discount_pct, line_total) VALUES
(12, 10, 1, 8999.00, 10, 8099.10),
(13, 1, 1, 4999.00, 0, 4999.00),
(14, 2, 1, 14999.00, 10, 13499.10), (14, 11, 1, 1200.00, 0, 1200.00),
(15, 8, 1, 12000.00, 10, 10800.00),
(16, 9, 1, 4800.00, 0, 4800.00),
(17, 2, 2, 14999.00, 10, 26998.20),
(18, 6, 1, 1299.00, 0, 1299.00),
(19, 7, 1, 3500.00, 10, 3150.00),
(20, 3, 1, 2998.00, 0, 2998.00),
(21, 5, 1, 7999.00, 10, 7199.10);

-- 2025 Q1 items (orders 22-27)
INSERT INTO order_items (order_id, product_id, quantity, unit_price, discount_pct, line_total) VALUES
(22, 2, 2, 14999.00, 10, 26998.20), (22, 10, 1, 8999.00, 10, 8099.10), (22, 9, 1, 4800.00, 0, 4800.00),
(23, 2, 1, 14999.00, 10, 13499.10), (23, 10, 1, 8999.00, 0, 8999.00),
(24, 2, 1, 14999.00, 0, 14999.00), (24, 10, 1, 8999.00, 0, 8999.00),
(25, 2, 2, 14999.00, 10, 26998.20), (25, 10, 1, 8999.00, 0, 8999.00),
(26, 2, 2, 14999.00, 10, 26998.20), (26, 9, 1, 4800.00, 0, 4800.00), (26, 12, 1, 3499.00, 10, 3149.10),
(27, 2, 1, 14999.00, 10, 13499.10), (27, 1, 1, 4999.00, 0, 4999.00), (27, 9, 1, 4800.00, 0, 4800.00);

-- 2025 Q2 items (orders 28-33)
INSERT INTO order_items (order_id, product_id, quantity, unit_price, discount_pct, line_total) VALUES
(28, 2, 1, 14999.00, 10, 13499.10), (28, 1, 1, 4999.00, 0, 4999.00), (28, 10, 1, 8999.00, 0, 8999.00),
(29, 2, 1, 14999.00, 10, 13499.10),
(30, 2, 1, 14999.00, 10, 13499.10), (30, 12, 1, 3499.00, 0, 3499.00),
(31, 10, 1, 8999.00, 10, 8099.10),
(32, 10, 1, 8999.00, 10, 8099.10), (32, 1, 1, 4999.00, 0, 4999.00),
(33, 1, 1, 4999.00, 10, 4499.10), (33, 4, 1, 999.00, 0, 999.00), (33, 3, 1, 2998.00, 0, 2998.00);

-- 2025 Q3-Q4 items (orders 34-45)
INSERT INTO order_items (order_id, product_id, quantity, unit_price, discount_pct, line_total) VALUES
(34, 2, 1, 14999.00, 10, 13499.10),
(35, 2, 1, 14999.00, 10, 13499.10), (35, 10, 1, 8999.00, 0, 8999.00), (35, 11, 1, 1200.00, 0, 1200.00),
(36, 1, 2, 4999.00, 10, 8998.20), (36, 12, 1, 3499.00, 0, 3499.00),
(37, 10, 1, 8999.00, 0, 8999.00),
(38, 12, 1, 3499.00, 10, 3149.10), (38, 9, 1, 4800.00, 0, 4800.00),
(39, 3, 1, 2998.00, 0, 2998.00),
(40, 2, 2, 14999.00, 10, 26998.20), (40, 10, 1, 8999.00, 10, 8099.10), (40, 9, 1, 4800.00, 0, 4800.00), (40, 8, 1, 12000.00, 10, 10800.00),
(41, 2, 2, 14999.00, 10, 26998.20), (41, 12, 1, 3499.00, 0, 3499.00),
(42, 2, 1, 14999.00, 10, 13499.10), (42, 10, 1, 8999.00, 10, 8099.10), (42, 11, 1, 1200.00, 0, 1200.00),
(43, 2, 1, 14999.00, 10, 13499.10), (43, 9, 1, 4800.00, 0, 4800.00),
(44, 2, 1, 14999.00, 10, 13499.10), (44, 10, 2, 8999.00, 10, 16198.20), (44, 9, 1, 4800.00, 0, 4800.00),
(45, 2, 1, 14999.00, 10, 13499.10), (45, 10, 1, 8999.00, 10, 8099.10), (45, 9, 1, 4800.00, 0, 4800.00);

-- ─── Update Customer Lifetime Values ──────────────────────
UPDATE customers c
SET lifetime_value = (
    SELECT COALESCE(SUM(o.total_amount), 0)
    FROM orders o WHERE o.customer_id = c.id
);
