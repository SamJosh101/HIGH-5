-- HIGH 5 – one-time MySQL setup (run as the MySQL root user).
--   mysql -u root -p < docs/setup_mysql.sql
-- Replace CHANGE_THIS_PASSWORD with a strong password and put the same value
-- in DB_PASSWORD in your .env file. Do NOT commit your edited copy.

CREATE DATABASE IF NOT EXISTS high5_db CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

CREATE USER IF NOT EXISTS 'high5_user'@'localhost' IDENTIFIED BY 'CHANGE_THIS_PASSWORD';

GRANT ALL PRIVILEGES ON high5_db.* TO 'high5_user'@'localhost';
-- Django's test runner creates and drops a separate test database:
GRANT ALL PRIVILEGES ON test_high5_db.* TO 'high5_user'@'localhost';

FLUSH PRIVILEGES;
