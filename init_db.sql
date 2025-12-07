-- Create database
CREATE DATABASE IF NOT EXISTS lab_inventory_db;
USE lab_inventory_db;

-- Users table
CREATE TABLE IF NOT EXISTS users (
    id INT AUTO_INCREMENT PRIMARY KEY,
    username VARCHAR(80) UNIQUE NOT NULL,
    email VARCHAR(120) UNIQUE NOT NULL,
    password VARCHAR(255) NOT NULL,
    role ENUM('admin', 'trainer') NOT NULL,
    lab_id INT,
    lab_name VARCHAR(255),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Labs table
CREATE TABLE IF NOT EXISTS labs (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(255) NOT NULL UNIQUE,
    location VARCHAR(255),
    description TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Categories table
CREATE TABLE IF NOT EXISTS categories (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    description TEXT,
    lab_id INT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (lab_id) REFERENCES labs(id) ON DELETE CASCADE,
    UNIQUE KEY unique_category_lab (name, lab_id)
);

-- Components table
CREATE TABLE IF NOT EXISTS components (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    category_id INT NOT NULL,
    lab_id INT NOT NULL,
    quantity INT DEFAULT 0,
    min_stock_level INT DEFAULT 0,
    unit VARCHAR(50),
    description TEXT,
    component_type VARCHAR(100) DEFAULT 'Other',
    date_added TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (category_id) REFERENCES categories(id) ON DELETE CASCADE,
    FOREIGN KEY (lab_id) REFERENCES labs(id) ON DELETE CASCADE
);

-- Transactions table
CREATE TABLE IF NOT EXISTS transactions (
    id INT AUTO_INCREMENT PRIMARY KEY,
    component_id INT NOT NULL,
    lab_id INT NOT NULL,
    campus VARCHAR(255),
    person_name VARCHAR(255) NOT NULL,
    purpose VARCHAR(500) NOT NULL,
    qty_issued INT DEFAULT 0,
    qty_returned INT DEFAULT 0,
    pending_qty INT DEFAULT 0,
    status ENUM('Issued', 'Partially Returned', 'Completed') DEFAULT 'Issued',
    issue_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    quantity_before INT,
    quantity_after INT,
    transaction_quantity INT,
    last_action ENUM('issue', 'return') DEFAULT 'issue',
    notes TEXT,
    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (component_id) REFERENCES components(id) ON DELETE CASCADE,
    FOREIGN KEY (lab_id) REFERENCES labs(id) ON DELETE CASCADE
);

-- Insert initial admin user
INSERT INTO users (username, email, password, role, lab_name) 
VALUES ('admin', 'admin@lab.com', 'admin123', 'admin', 'Main Lab')
ON DUPLICATE KEY UPDATE username=username;

-- Create indexes for performance
CREATE INDEX idx_components_lab ON components(lab_id);
CREATE INDEX idx_components_category ON components(category_id);
CREATE INDEX idx_transactions_component ON transactions(component_id);
CREATE INDEX idx_transactions_status ON transactions(status);
CREATE INDEX idx_transactions_date ON transactions(issue_date);
