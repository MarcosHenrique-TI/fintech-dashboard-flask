-- Users Table
CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    email VARCHAR(255) UNIQUE NOT NULL,
    password VARCHAR(255) NOT NULL
);

-- Categories Table
CREATE TABLE categories (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    type VARCHAR(50) NOT NULL, -- 'receita' ou 'despesa'
    user_id INTEGER NOT NULL
);

-- Transaction Table
CREATE TABLE transactions (
    id SERIAL PRIMARY KEY,
    amount NUMERIC(10, 2) NOT NULL, 
    transaction_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    description VARCHAR(100),
    category_id INTEGER NOT NULL
);

ALTER TABLE categories 
ADD CONSTRAINT fk_user 
FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE;

ALTER TABLE transactions
ADD CONSTRAINT fk_categories
FOREIGN KEY (category_id) REFERENCES categories(id) ON DELETE CASCADE;