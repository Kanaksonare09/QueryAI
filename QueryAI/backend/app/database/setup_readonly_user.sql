-- QueryAI V2 — Setup Read-Only Database User (MySQL)
-- 
-- Run this script as the database administrator (e.g. root) to create
-- a secure, read-only user for QueryAI's business database.
-- 
-- This ensures that even if SQL injection bypasses the AI and AST validators,
-- the database itself will reject any modifications.

-- 1. Create the user
CREATE USER 'queryai_readonly'@'localhost' IDENTIFIED BY 'secure_password_here';

-- 2. Grant SELECT only on the business database
GRANT SELECT ON ai_assistant_demo.* TO 'queryai_readonly'@'localhost';

-- 3. (Optional) Grant specific permissions needed for EXPLAIN and schema inspection
GRANT SHOW VIEW ON ai_assistant_demo.* TO 'queryai_readonly'@'localhost';
GRANT PROCESS ON *.* TO 'queryai_readonly'@'localhost';

-- 4. Apply changes
FLUSH PRIVILEGES;

-- To test:
-- mysql -u queryai_readonly -p
-- USE ai_assistant_demo;
-- SELECT * FROM customers LIMIT 1; -- Should work
-- DELETE FROM customers; -- Should fail (ERROR 1142: DELETE command denied)
