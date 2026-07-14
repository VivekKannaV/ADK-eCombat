-- Drop tables if they exist to start fresh
DROP TABLE IF EXISTS conversation_turns CASCADE;
DROP TABLE IF EXISTS session_history CASCADE;
DROP TABLE IF EXISTS orders CASCADE;
DROP TABLE IF EXISTS products CASCADE;

-- Create Products Table
CREATE TABLE products (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) UNIQUE NOT NULL,
    description TEXT,
    price NUMERIC(10, 2) NOT NULL,
    stock_quantity INTEGER NOT NULL CHECK (stock_quantity >= 0),
    category VARCHAR(50) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create Orders Table
CREATE TABLE orders (
    id SERIAL PRIMARY KEY,
    customer_name VARCHAR(100) NOT NULL,
    product_id INTEGER REFERENCES products(id) ON DELETE CASCADE,
    quantity INTEGER NOT NULL CHECK (quantity > 0),
    total_price NUMERIC(10, 2) NOT NULL,
    status VARCHAR(20) DEFAULT 'Pending' CHECK (status IN ('Pending', 'Processing', 'Shipped', 'Delivered', 'Cancelled')),
    order_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create Session History Table (conversation turns — one row per message)
CREATE TABLE conversation_turns (
    id           SERIAL PRIMARY KEY,
    session_id   VARCHAR(255)             NOT NULL,
    user_id      VARCHAR(255),
    role         VARCHAR(50)              NOT NULL CHECK (role IN ('user', 'assistant', 'tool', 'system')),
    content      TEXT                     NOT NULL,
    tool_calls   JSONB,
    timestamp    TIMESTAMPTZ              NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_conversation_turns_session
    ON conversation_turns (session_id, timestamp ASC);

-- Insert Electronics products sample data (15 entries)
INSERT INTO products (name, description, price, stock_quantity, category) VALUES
('iPhone 15 Pro Max',                   'Apple flagship smartphone with A17 Pro chip, titanium design, and 5x optical zoom camera.',         1199.00, 50,  'Smartphones'),
('Samsung Galaxy S24 Ultra',            'Samsung flagship phone featuring Galaxy AI, Snapdragon 8 Gen 3, and integrated S Pen.',             1299.00, 45,  'Smartphones'),
('Google Pixel 8 Pro',                  'Google smartphone with advanced AI camera capabilities, Tensor G3 chip, and bright Actua display.', 999.00,  30,  'Smartphones'),
('MacBook Pro 16-inch M3 Max',          'Apple high-performance notebook with M3 Max chip, 36GB unified memory, and 1TB SSD.',               3499.00, 15,  'Laptops'),
('Dell XPS 15 9530',                    'Dell premium laptop with 13th Gen Intel Core i7, 16GB RAM, 512GB SSD, and NVIDIA RTX 4050.',        1899.00, 20,  'Laptops'),
('Lenovo ThinkPad X1 Carbon Gen 11',    'Business class ultrabook with Intel Core i7, 16GB RAM, 512GB SSD, and robust design.',              1699.00, 25,  'Laptops'),
('Sony WH-1000XM5',                     'Sony premium wireless noise-cancelling over-ear headphones with 30-hour battery life.',             398.00,  80,  'Audio'),
('Apple AirPods Pro (2nd Generation)',  'Apple wireless earbuds with active noise cancellation, adaptive audio, and USB-C charging case.',   249.00,  120, 'Audio'),
('Bose QuietComfort Ultra Earbuds',     'Bose flagship wireless earbuds with world-class noise cancellation and immersive audio.',           299.00,  65,  'Audio'),
('Apple Watch Series 9',                'Apple smartwatch with S9 SIP, double tap gesture, bright Retina display, and health tracking.',     399.00,  90,  'Wearables'),
('Samsung Galaxy Watch 6',              'Samsung LTE smartwatch with sleep tracking, body composition analysis, and heart rate monitor.',    299.00,  75,  'Wearables'),
('Garmin Forerunner 965',               'Garmin premium GPS running and triathlon smartwatch with bright AMOLED display.',                   599.00,  40,  'Wearables'),
('Philips Hue Starter Kit',             'Smart lighting starter kit with 3 A19 LED color changing bulbs and the Hue bridge.',                189.99,  35,  'Smart Home'),
('Amazon Echo Dot (5th Gen)',           'Compact smart speaker with Alexa, offering vibrant sound and smart home integration.',              49.99,   200, 'Smart Home'),
('Nest Learning Thermostat (3rd Gen)',  'Smart thermostat that learns your schedule and preferences to save energy.',                        249.00,  55,  'Smart Home');

-- Insert Sample orders data using subqueries for dynamic product ID and price mapping
INSERT INTO orders (customer_name, product_id, quantity, total_price, status) VALUES
('Alice Smith',   (SELECT id FROM products WHERE name = 'iPhone 15 Pro Max'),          1, 1 * (SELECT price FROM products WHERE name = 'iPhone 15 Pro Max'),          'Delivered'),
('Bob Jones',     (SELECT id FROM products WHERE name = 'Sony WH-1000XM5'),            2, 2 * (SELECT price FROM products WHERE name = 'Sony WH-1000XM5'),            'Shipped'),
('Charlie Brown', (SELECT id FROM products WHERE name = 'Amazon Echo Dot (5th Gen)'),  5, 5 * (SELECT price FROM products WHERE name = 'Amazon Echo Dot (5th Gen)'),  'Processing'),
('Diana Prince',  (SELECT id FROM products WHERE name = 'MacBook Pro 16-inch M3 Max'), 1, 1 * (SELECT price FROM products WHERE name = 'MacBook Pro 16-inch M3 Max'), 'Pending'),
('Evan Wright',   (SELECT id FROM products WHERE name = 'Apple Watch Series 9'),       1, 1 * (SELECT price FROM products WHERE name = 'Apple Watch Series 9'),       'Cancelled');
