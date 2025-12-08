import pymysql
from config import Config

class Database:
    def __init__(self):
        self.config = Config()
        
    def get_connection(self):
        return pymysql.connect(
            host=self.config.MYSQL_HOST,
            user=self.config.MYSQL_USER,
            password=self.config.MYSQL_PASSWORD,
            database=self.config.MYSQL_DB,
            cursorclass=pymysql.cursors.DictCursor
        )
    
    def init_db(self):
        """Initialize database tables"""
        connection = self.get_connection()
        try:
            with connection.cursor() as cursor:
                # Create users table
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS users (
                        id INT AUTO_INCREMENT PRIMARY KEY,
                        username VARCHAR(80) UNIQUE NOT NULL,
                        password VARCHAR(255) NOT NULL,
                        role ENUM('admin', 'trainer') DEFAULT 'trainer',
                        lab_id INT,
                        lab_name VARCHAR(255),
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                ''')
                
                # Create labs table
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS labs (
                        id INT AUTO_INCREMENT PRIMARY KEY,
                        name VARCHAR(255) NOT NULL,
                        location VARCHAR(255),
                        description TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                ''')
                
                # Create categories table
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS categories (
                        id INT AUTO_INCREMENT PRIMARY KEY,
                        name VARCHAR(255) NOT NULL,
                        description TEXT,
                        lab_id INT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (lab_id) REFERENCES labs(id) ON DELETE SET NULL
                    )
                ''')
                
                # Create components table
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS components (
                        id INT AUTO_INCREMENT PRIMARY KEY,
                        name VARCHAR(255) NOT NULL,
                        description TEXT,
                        category_id INT,
                        lab_id INT,
                        quantity INT DEFAULT 0,
                        min_stock_level INT DEFAULT 0,
                        unit VARCHAR(50),
                        component_type VARCHAR(100),
                        date_added TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                        FOREIGN KEY (category_id) REFERENCES categories(id) ON DELETE SET NULL,
                        FOREIGN KEY (lab_id) REFERENCES labs(id) ON DELETE SET NULL
                    )
                ''')
                
                # Create transactions table
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS transactions (
                        id INT AUTO_INCREMENT PRIMARY KEY,
                        component_id INT,
                        lab_id INT,
                        campus VARCHAR(255),
                        person_name VARCHAR(255),
                        purpose VARCHAR(255),
                        qty_issued INT DEFAULT 0,
                        qty_returned INT DEFAULT 0,
                        pending_qty INT DEFAULT 0,
                        status ENUM('Issued', 'Partially Returned', 'Completed') DEFAULT 'Issued',
                        issue_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        quantity_before INT,
                        quantity_after INT,
                        transaction_quantity INT,
                        last_action ENUM('issue', 'return'),
                        notes TEXT,
                        last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                        FOREIGN KEY (component_id) REFERENCES components(id) ON DELETE SET NULL,
                        FOREIGN KEY (lab_id) REFERENCES labs(id) ON DELETE SET NULL
                    )
                ''')
                
                # Create admin user if not exists
                cursor.execute('''
                    INSERT IGNORE INTO users (username, password, role) 
                    VALUES ('admin', 'admin123', 'admin')
                ''')
                
            connection.commit()
            print("Database initialized successfully!")
            
        except Exception as e:
            print(f"Error initializing database: {e}")
        finally:
            connection.close()

# Singleton instance
db_instance = Database()
