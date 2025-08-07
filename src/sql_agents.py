from crewai import Agent, Task, Crew
from langchain_openai import ChatOpenAI
import os
from typing import Optional
import psycopg2
from psycopg2.extras import RealDictCursor
import pandas as pd
from src.db_schema_analyzer import DatabaseSchemaAnalyzer


class SQLQueryAgent:
    def __init__(self):
        self.llm = ChatOpenAI(
            model="gpt-4-turbo-preview",
            temperature=0.1,
            api_key=os.getenv('OPENAI_API_KEY')
        )
        self.schema_analyzer = DatabaseSchemaAnalyzer()
        
        # Create agents
        self.schema_analyst = self._create_schema_analyst()
        self.sql_expert = self._create_sql_expert()
        self.query_validator = self._create_query_validator()
    
    def _create_schema_analyst(self) -> Agent:
        """Create schema analysis agent"""
        return Agent(
            role='Database Schema Analyst',
            goal='Analyze database schema and identify relevant tables and columns for the query',
            backstory="""You are an expert database analyst with deep knowledge of PostgreSQL.
            Your job is to understand the user's natural language query and identify which 
            tables and columns are most relevant to answer their question.""",
            llm=self.llm,
            verbose=True,
            allow_delegation=False
        )
    
    def _create_sql_expert(self) -> Agent:
        """Create SQL query generation agent"""
        return Agent(
            role='SQL Query Expert',
            goal='Generate optimized PostgreSQL queries based on schema analysis',
            backstory="""You are a PostgreSQL expert who writes efficient, accurate SQL queries.
            You excel at writing complex JOINs, aggregations, and window functions when needed.
            You always consider query performance and write clean, readable SQL.""",
            llm=self.llm,
            verbose=True,
            allow_delegation=False
        )
    
    def _create_query_validator(self) -> Agent:
        """Create query validation agent"""
        return Agent(
            role='Query Validator',
            goal='Validate and optimize SQL queries for correctness and performance',
            backstory="""You are a database performance expert who validates SQL queries.
            You check for syntax errors, potential performance issues, and suggest optimizations.
            You ensure queries are safe and won't cause database issues.""",
            llm=self.llm,
            verbose=True,
            allow_delegation=False
        )
    
    def generate_sql(self, user_query: str) -> dict:
        """
        Generate SQL query from natural language
        """
        try:
            # Get optimized schema context
            schema_context = self.schema_analyzer.get_optimized_schema_context(user_query)
            
            # Task 1: Analyze schema
            schema_task = Task(
                description=f"""
                Analyze the following user query and database schema to identify relevant tables and columns:
                
                User Query: {user_query}
                
                Schema Context:
                {schema_context}
                
                Provide a clear analysis of:
                1. Which tables are needed
                2. Which columns should be selected
                3. What joins might be required
                4. Any aggregations or filters needed
                """,
                agent=self.schema_analyst,
                expected_output="Detailed analysis of required tables, columns, and query structure"
            )
            
            # Task 2: Generate SQL
            sql_task = Task(
                description=f"""
                Based on the schema analysis, generate a PostgreSQL query for:
                
                User Query: {user_query}
                
                Requirements:
                - Use proper PostgreSQL syntax
                - Include necessary JOINs
                - Add appropriate WHERE clauses
                - Use aggregations if needed
                - Consider query performance
                - Return only the SQL query without explanations
                """,
                agent=self.sql_expert,
                expected_output="A valid PostgreSQL query",
                context=[schema_task]
            )
            
            # Task 3: Validate and optimize
            validation_task = Task(
                description="""
                Validate the generated SQL query:
                
                1. Check for syntax errors
                2. Verify table and column names
                3. Suggest performance optimizations
                4. Ensure query safety
                
                Return the final optimized query.
                """,
                agent=self.query_validator,
                expected_output="Validated and optimized SQL query",
                context=[sql_task]
            )
            
            # Create and run crew
            crew = Crew(
                agents=[self.schema_analyst, self.sql_expert, self.query_validator],
                tasks=[schema_task, sql_task, validation_task],
                verbose=True
            )
            
            result = crew.kickoff()
            
            # Extract SQL from result
            sql_query = self._extract_sql(str(result))
            
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
    
    def _extract_sql(self, text: str) -> str:
        """Extract SQL query from agent response"""
        # Look for SQL between markers or clean the text
        lines = text.split('\n')
        sql_lines = []
        in_sql = False
        
        for line in lines:
            if 'SELECT' in line.upper() or in_sql:
                in_sql = True
                if line.strip() and not line.startswith('#'):
                    sql_lines.append(line)
                if ';' in line:
                    break
        
        if sql_lines:
            return '\n'.join(sql_lines)
        
        # Fallback: return cleaned text
        return text.strip()
    
    def execute_query(self, sql_query: str) -> dict:
        """
        Execute SQL query and return results
        """
        try:
            conn = psycopg2.connect(
                host=os.getenv('DB_HOST', 'localhost'),
                port=os.getenv('DB_PORT', 5432),
                database=os.getenv('DB_NAME'),
                user=os.getenv('DB_USER'),
                password=os.getenv('DB_PASSWORD')
            )
            
            # Use pandas for better result handling
            df = pd.read_sql_query(sql_query, conn)
            conn.close()
            
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
    
    def close(self):
        """Clean up resources"""
        self.schema_analyzer.close()