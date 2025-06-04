import mysql.connector
from mysql.connector import Error
from typing import List, Dict, Any


class DatabaseConnection:
    def __init__(self):
        self.connection = None
        self.host = "localhost"
        self.port = 3306
        self.user = "mendol"
        self.password = "mendol123"
        self.database = "caraba_products"

    def connect(self):
        """Establish connection to MySQL database"""
        try:
            self.connection = mysql.connector.connect(
                host=self.host,
                port=self.port,
                user=self.user,
                password=self.password,
                database=self.database,
            )
            print("Successfully connected to MySQL database!")
        except Error as e:
            print(f"Error connecting to MySQL database: {e}")

    def get_schema(self):
        """Get database schema information"""
        try:
            if not self.connection or not self.connection.is_connected():
                self.connect()

            cursor = self.connection.cursor()

            # Get all tables
            cursor.execute("SHOW TABLES")
            tables = cursor.fetchall()

            schema_info = {}
            for table in tables:
                table_name = table[0]
                # Get table structure
                cursor.execute(f"DESCRIBE {table_name}")
                columns = cursor.fetchall()
                schema_info[table_name] = [
                    {
                        "Field": col[0],
                        "Type": col[1],
                        "Null": col[2],
                        "Key": col[3],
                        "Default": col[4],
                        "Extra": col[5],
                    }
                    for col in columns
                ]

            return schema_info

        except Error as e:
            print(f"Error getting schema: {e}")
            return None
        finally:
            if cursor:
                cursor.close()
    
    def get_schema_text(self):
        schema_sections = []
        schema_info = self.get_schema()

        for table_name, columns in schema_info.items():
            column_details = []
            date_columns = []
            numeric_columns = []
            text_columns = []
            
            for col in columns:
                col_info = f"{col['Field']} ({col['Type']}"
                if col.get('Key') == 'PRI':
                    col_info += ", PRIMARY KEY"
                if col.get('Key') == 'UNI':
                    col_info += ", UNIQUE"
                if col.get('Null') == 'NO':
                    col_info += ", NOT NULL"
                if col.get('Default'):
                    col_info += f", DEFAULT: {col['Default']}"
                col_info += ")"
                column_details.append(f"    • {col_info}")
                
                # Categorize columns for smart suggestions
                col_type = col['Type'].lower()
                col_name = col['Field'].lower()
                
                if any(date_word in col_type for date_word in ['date', 'time', 'timestamp']):
                    date_columns.append(col['Field'])
                elif any(num_word in col_type for num_word in ['int', 'decimal', 'float', 'double', 'numeric']):
                    numeric_columns.append(col['Field'])
                elif any(text_word in col_type for text_word in ['varchar', 'text', 'char']):
                    text_columns.append(col['Field'])
            
            schema_sections.append(f"  {table_name}:\n" + "\n".join(column_details))
        schema_text = "DATABASE SCHEMA:\n" + "\n\n".join(schema_sections)
        return schema_text

    def execute_query(self, query: str) -> List[Dict[str, Any]]:
        """Execute a SELECT query and return results"""
        try:
            if not self.connection or not self.connection.is_connected():
                self.connect()

            cursor = self.connection.cursor(dictionary=True)
            cursor.execute(query)
            results = cursor.fetchall()
            return results

        except Error as e:
            print(f"Error executing query: {e}")
            return None
        finally:
            if cursor:
                cursor.close()

    def close(self):
        """Close database connection"""
        if self.connection and self.connection.is_connected():
            self.connection.close()
            print("Database connection closed.")


# Example usage
if __name__ == "__main__":
    # Create database connection instance
    db = DatabaseConnection()

    # Connect to database
    db.connect()

    # Get and print schema
    print("\nDatabase Schema:")
    schema = db.get_schema()
    if schema:
        for table_name, columns in schema.items():
            print(f"\nTable: {table_name}")
            for column in columns:
                print(f"  {column['Field']} ({column['Type']}) - {column['Key']} key")

    # Example query
    print("\nExample Query:")
    query = (
        "SELECT * FROM information_schema.tables WHERE table_schema = 'caraba_products'"
    )
    results = db.execute_query(query)
    if results:
        for row in results:
            print(row)

    # Close connection
    db.close()
