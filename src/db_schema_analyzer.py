import psycopg2
from psycopg2.extras import RealDictCursor
import os
from typing import List, Dict, Optional
import json


class DatabaseSchemaAnalyzer:
    def __init__(self):
        self.conn = None
        self.cursor = None
        self.db_schema = os.getenv('DB_SCHEMA', 'public')
        self.connect()
        
    def connect(self):
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
    
    def get_relevant_tables(self, query: str, limit: int = 10) -> List[Dict]:
        """
        Find relevant tables based on query using comment tables
        """
        search_terms = query.lower().split()
        
        # Search in table comments
        table_query = f"""
        SELECT DISTINCT 
            t.table_name,
            t.comment as table_comment,
            t.schema_name,
            COUNT(*) OVER (PARTITION BY t.table_name) as relevance_score
        FROM {self.db_schema}.comment_on_table t
        WHERE LOWER(t.comment) LIKE ANY(%s) 
           OR LOWER(t.table_name) LIKE ANY(%s)
        ORDER BY relevance_score DESC, t.table_name
        LIMIT %s
        """
        
        # Create search patterns
        patterns = [f'%{term}%' for term in search_terms]
        
        self.cursor.execute(table_query, (patterns, patterns, limit))
        relevant_tables = self.cursor.fetchall()
        
        return relevant_tables
    
    def get_relevant_columns(self, table_names: List[str], query: str) -> Dict[str, List[Dict]]:
        """
        Get relevant columns for selected tables using comment tables
        """
        if not table_names:
            return {}
        
        search_terms = query.lower().split()
        patterns = [f'%{term}%' for term in search_terms]
        
        column_query = f"""
        SELECT 
            c.table_name,
            c.column_name,
            c.comment as column_comment,
            c.schema_name
        FROM {self.db_schema}.comment_on_column c
        WHERE c.table_name = ANY(%s)
          AND (LOWER(c.comment) LIKE ANY(%s) 
               OR LOWER(c.column_name) LIKE ANY(%s))
        ORDER BY c.table_name, c.column_name
        """
        
        self.cursor.execute(column_query, (table_names, patterns, patterns))
        columns = self.cursor.fetchall()
        
        # Group columns by table
        columns_by_table = {}
        for col in columns:
            table = col['table_name']
            if table not in columns_by_table:
                columns_by_table[table] = []
            columns_by_table[table].append(col)
        
        # Also get all columns for tables if not enough relevant ones found
        for table in table_names:
            if table not in columns_by_table or len(columns_by_table[table]) < 3:
                all_cols_query = """
                SELECT 
                    column_name,
                    data_type,
                    is_nullable,
                    column_default
                FROM information_schema.columns
                WHERE table_name = %s
                ORDER BY ordinal_position
                LIMIT 20
                """
                self.cursor.execute(all_cols_query, (table,))
                basic_cols = self.cursor.fetchall()
                
                if table not in columns_by_table:
                    columns_by_table[table] = []
                
                for col in basic_cols:
                    if not any(c['column_name'] == col['column_name'] for c in columns_by_table[table]):
                        columns_by_table[table].append({
                            'table_name': table,
                            'column_name': col['column_name'],
                            'data_type': col['data_type'],
                            'column_comment': None
                        })
        
        return columns_by_table
    
    def get_table_relationships(self, table_names: List[str]) -> List[Dict]:
        """
        Get foreign key relationships for relevant tables
        """
        if not table_names:
            return []
        
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
        """
        
        self.cursor.execute(fk_query, (table_names, table_names))
        return self.cursor.fetchall()
    
    def get_optimized_schema_context(self, query: str) -> str:
        """
        Get optimized schema context for the query
        """
        # Find relevant tables
        relevant_tables = self.get_relevant_tables(query, limit=10)
        
        if not relevant_tables:
            return "No relevant tables found for the query."
        
        table_names = [t['table_name'] for t in relevant_tables]
        
        # Get relevant columns
        columns_by_table = self.get_relevant_columns(table_names, query)
        
        # Get relationships
        relationships = self.get_table_relationships(table_names)
        
        # Build context string
        context = "Database Schema Context:\n\n"
        
        for table in relevant_tables:
            table_name = table['table_name']
            context += f"Table: {table_name}\n"
            if table.get('table_comment'):
                context += f"  Description: {table['table_comment']}\n"
            
            # Add columns
            if table_name in columns_by_table:
                context += "  Columns:\n"
                for col in columns_by_table[table_name][:15]:  # Limit columns per table
                    context += f"    - {col['column_name']}"
                    if col.get('column_comment'):
                        context += f": {col['column_comment']}"
                    context += "\n"
            
            context += "\n"
        
        # Add relationships
        if relationships:
            context += "Relationships:\n"
            for rel in relationships[:10]:  # Limit relationships
                context += f"  - {rel['from_table']}.{rel['from_column']} -> {rel['to_table']}.{rel['to_column']}\n"
        
        return context
    
    def close(self):
        """Close database connection"""
        if self.cursor:
            self.cursor.close()
        if self.conn:
            self.conn.close()