import os
import json
from openai import OpenAI
import psycopg2
from psycopg2.extras import RealDictCursor
import pandas as pd
from typing import Dict, List, Optional


class SimpleSQLAgent:
    def __init__(self):
        # Initialize OpenAI client with just the API key
        api_key = os.getenv('OPENAI_API_KEY')
        if not api_key:
            raise ValueError("OPENAI_API_KEY not found in environment variables")
        
        # Get database schema
        self.db_schema = os.getenv('DB_SCHEMA', 'public')
        
        # Remove any proxy settings that might interfere
        for proxy_var in ['HTTP_PROXY', 'HTTPS_PROXY', 'http_proxy', 'https_proxy']:
            if proxy_var in os.environ:
                del os.environ[proxy_var]
        
        try:
            self.client = OpenAI(api_key=api_key)
        except Exception as e:
            # If there's any error, try alternative initialization
            try:
                # Try without any extra parameters
                import openai
                self.client = OpenAI()
                self.client.api_key = api_key
            except:
                # Final fallback
                import openai
                openai.api_key = api_key
                self.client = openai
            
        self.conn = None
        self.cursor = None
        self.connect_db()
    
    def connect_db(self):
        """Establish database connection"""
        try:
            self.conn = psycopg2.connect(
                host=os.getenv('DB_HOST', 'localhost'),
                port=os.getenv('DB_PORT', 5432),
                database=os.getenv('DB_NAME'),
                user=os.getenv('DB_USER'),
                password=os.getenv('DB_PASSWORD')
            )
            self.cursor = self.conn.cursor(cursor_factory=RealDictCursor)
        except Exception as e:
            print(f"Database connection error: {e}")
            raise
    
    def get_relevant_schema(self, query: str, limit: int = 10) -> str:
        """Get relevant schema information using comment tables"""
        search_terms = query.lower().split()
        patterns = [f'%{term}%' for term in search_terms]
        
        # Find relevant tables
        table_query = f"""
        SELECT DISTINCT 
            t.table_name,
            t.comment as table_comment,
            t.schema_name
        FROM {self.db_schema}.comment_on_table t
        WHERE LOWER(t.comment) LIKE ANY(%s) 
           OR LOWER(t.table_name) LIKE ANY(%s)
        LIMIT %s
        """
        
        self.cursor.execute(table_query, (patterns, patterns, limit))
        relevant_tables = self.cursor.fetchall()
        
        if not relevant_tables:
            # Fallback: get some tables if no matches
            self.cursor.execute(f"""
                SELECT table_name, comment as table_comment, schema_name 
                FROM {self.db_schema}.comment_on_table 
                LIMIT 5
            """)
            relevant_tables = self.cursor.fetchall()
        
        schema_context = "Database Schema:\n\n"
        
        for table in relevant_tables:
            table_name = table['table_name']
            schema_name = table.get('schema_name', 'public')
            schema_context += f"Table: {schema_name}.{table_name}\n"
            if table.get('table_comment'):
                schema_context += f"  Description: {table['table_comment']}\n"
            
            # Get columns for this table
            col_query = f"""
            SELECT 
                c.column_name,
                c.comment as column_comment
            FROM {self.db_schema}.comment_on_column c
            WHERE c.table_name = %s
              AND (LOWER(c.comment) LIKE ANY(%s) 
                   OR LOWER(c.column_name) LIKE ANY(%s))
            LIMIT 15
            """
            
            self.cursor.execute(col_query, (table_name, patterns, patterns))
            columns = self.cursor.fetchall()
            
            # If no relevant columns, get all columns
            if not columns:
                self.cursor.execute("""
                    SELECT column_name, data_type
                    FROM information_schema.columns
                    WHERE table_name = %s
                    ORDER BY ordinal_position
                    LIMIT 15
                """, (table_name,))
                columns = self.cursor.fetchall()
            
            if columns:
                schema_context += "  Columns:\n"
                for col in columns:
                    schema_context += f"    - {col['column_name']}"
                    if col.get('column_comment'):
                        schema_context += f": {col['column_comment']}"
                    schema_context += "\n"
            
            schema_context += "\n"
        
        # Get relationships
        if relevant_tables:
            table_names = [t['table_name'] for t in relevant_tables]
            fk_query = """
            SELECT 
                tc.table_name as from_table,
                kcu.column_name as from_column,
                ccu.table_name AS to_table,
                ccu.column_name AS to_column
            FROM information_schema.table_constraints AS tc 
            JOIN information_schema.key_column_usage AS kcu
                ON tc.constraint_name = kcu.constraint_name
            JOIN information_schema.constraint_column_usage AS ccu
                ON ccu.constraint_name = tc.constraint_name
            WHERE tc.constraint_type = 'FOREIGN KEY' 
              AND (tc.table_name = ANY(%s) OR ccu.table_name = ANY(%s))
            LIMIT 10
            """
            
            self.cursor.execute(fk_query, (table_names, table_names))
            relationships = self.cursor.fetchall()
            
            if relationships:
                schema_context += "Relationships:\n"
                for rel in relationships:
                    schema_context += f"  - {rel['from_table']}.{rel['from_column']} -> {rel['to_table']}.{rel['to_column']}\n"
        
        return schema_context
    
    def generate_sql(self, user_query: str) -> Dict:
        """Generate SQL from natural language using OpenAI"""
        try:
            # Get relevant schema
            schema_context = self.get_relevant_schema(user_query)
            
            # Create prompt
            prompt = f"""You are a PostgreSQL expert. Generate a SQL query based on the user's question and the provided database schema.

User Question: {user_query}

{schema_context}

Instructions:
1. Generate ONLY the SQL query, no explanations
2. Use proper PostgreSQL syntax
3. Include necessary JOINs if multiple tables are involved
4. Use appropriate WHERE clauses and aggregations
5. Consider query performance

Return ONLY the SQL query without any markdown formatting or explanations."""

            # Call OpenAI
            if hasattr(self.client, 'chat'):
                # New OpenAI client
                response = self.client.chat.completions.create(
                    model="gpt-4-turbo-preview",
                    messages=[
                        {"role": "system", "content": "You are a PostgreSQL database expert. Generate only SQL queries."},
                        {"role": "user", "content": prompt}
                    ],
                    temperature=0.1,
                    max_tokens=500
                )
                sql_query = response.choices[0].message.content.strip()
            else:
                # Old OpenAI API
                response = self.client.ChatCompletion.create(
                    model="gpt-4-turbo-preview",
                    messages=[
                        {"role": "system", "content": "You are a PostgreSQL database expert. Generate only SQL queries."},
                        {"role": "user", "content": prompt}
                    ],
                    temperature=0.1,
                    max_tokens=500
                )
                sql_query = response['choices'][0]['message']['content'].strip()
            
            # Clean up the SQL (remove markdown if any)
            sql_query = sql_query.replace('```sql', '').replace('```', '').strip()
            
            return {
                'success': True,
                'query': sql_query,
                'schema_context': schema_context[:500]  # Truncate for display
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'query': None
            }
    
    def execute_query(self, sql_query: str) -> Dict:
        """Execute SQL query and return results"""
        try:
            # Use pandas for better result handling
            df = pd.read_sql_query(sql_query, self.conn)
            
            return {
                'success': True,
                'data': df.to_dict('records'),
                'columns': df.columns.tolist(),
                'row_count': len(df)
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'data': None
            }
    
    def validate_sql(self, sql_query: str) -> Dict:
        """Validate SQL query using EXPLAIN"""
        try:
            # Try to explain the query
            self.cursor.execute(f"EXPLAIN {sql_query}")
            plan = self.cursor.fetchall()
            
            return {
                'valid': True,
                'message': 'Query is valid'
            }
        except Exception as e:
            return {
                'valid': False,
                'message': str(e)
            }
    
    def close(self):
        """Close database connection"""
        if self.cursor:
            self.cursor.close()
        if self.conn:
            self.conn.close()