import os
import psycopg2
from psycopg2.extras import RealDictCursor
import pandas as pd
from typing import Dict, List
import requests
import json
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class MinimalSQLAgent:
    def __init__(self):
        self.api_key = os.getenv('OPENAI_API_KEY')
        if not self.api_key:
            raise ValueError("OPENAI_API_KEY not found in environment variables")
        
        self.db_schema = os.getenv('DB_SCHEMA', 'public')
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
          --LIMIT %s
        """
        
        # Log the final query for debugging
        logger.info(f"Executing table search query:")
        logger.info(f"Query: {table_query}")
        logger.info(f"Schema: {self.db_schema}")
        logger.info(f"Search patterns: {patterns}")
        logger.info(f"Limit: {limit}")
        
        self.cursor.execute(table_query, (patterns, patterns, limit))
        relevant_tables = self.cursor.fetchall()
        
        if not relevant_tables:
            # Fallback: get some tables if no matches
            logger.warning(f"No tables found for patterns: {patterns}")
            fallback_query = f"""
                SELECT table_name, comment as table_comment, schema_name 
                FROM {self.db_schema}.comment_on_table 
                --  LIMIT 5
            """
            logger.info(f"Using fallback query: {fallback_query}")
            self.cursor.execute(fallback_query)
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
             -- LIMIT 15
            """
            
            logger.debug(f"Getting columns for table {table_name}")
            self.cursor.execute(col_query, (table_name,))
            columns = self.cursor.fetchall()
            
            if columns:
                schema_context += "  Columns:\n"
                for col in columns:
                    schema_context += f"    - {col['column_name']}"
                    if col.get('column_comment'):
                        schema_context += f": {col['column_comment']}"
                    schema_context += "\n"
            
            schema_context += "\n"
        
        return schema_context
    
    def generate_sql(self, user_query: str) -> Dict:
        """Generate SQL from natural language using OpenAI API directly"""
        try:
            logger.info(f"Generating SQL for user query: {user_query}")
            
            # Get relevant schema
            schema_context = self.get_relevant_schema(user_query)
            logger.info(f"Schema context length: {len(schema_context)} characters")
            
            # Create prompt
            prompt = f"""You are a PostgreSQL expert. Generate a SQL query based on the user's question and the provided database schema.

User Question: {user_query}

{schema_context}

Instructions:
1. Generate ONLY the SQL query, no explanations
2. Use proper PostgreSQL syntax
3. The schema contains highly denormalized tables, meaning most tables include both id and their corresponding name fields (e.g., catchment_id and catchment_name are in the same table)
4. Assume tables are mostly self-contained, so joins are not always necessary unless clearly required.
5. If a join is needed, first check if fiscal_year_id exists in the involved tables and prioritize joins using it.
6. Columns like *_id are usually foreign keys, and *_name columns contain descriptive values for the corresponding IDs.
7. Always aim to provide readable and efficient SQL queries, using clear aliases and avoiding unnecessary complexity.
8. Use appropriate WHERE clauses and aggregations
9. Consider query performance

Return ONLY the SQL query without any markdown formatting or explanations."""

            # Call OpenAI API directly using requests
            headers = {
                'Authorization': f'Bearer {self.api_key}',
                'Content-Type': 'application/json'
            }
            
            data = {
                'model': 'gpt-4-turbo-preview',
                'messages': [
                    {"role": "system", "content": "You are a PostgreSQL database expert. Generate only SQL queries."},
                    {"role": "user", "content": prompt}
                ],
                'temperature': 0.1,
                'max_tokens': 500
            }
            
            logger.info("Calling OpenAI API...")
            response = requests.post(
                'https://api.openai.com/v1/chat/completions',
                headers=headers,
                json=data
            )
            
            if response.status_code == 200:
                result = response.json()
                sql_query = result['choices'][0]['message']['content'].strip()
                
                # Clean up the SQL (remove markdown if any)
                sql_query = sql_query.replace('```sql', '').replace('```', '').strip()
                
                logger.info(f"Generated SQL query: {sql_query}")
                
                return {
                    'success': True,
                    'query': sql_query,
                    'schema_context': schema_context[:500]
                }
            else:
                logger.error(f"OpenAI API error: {response.status_code} - {response.text}")
                return {
                    'success': False,
                    'error': f"OpenAI API error: {response.status_code} - {response.text}",
                    'query': None
                }
            
        except Exception as e:
            logger.error(f"Error generating SQL: {str(e)}")
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