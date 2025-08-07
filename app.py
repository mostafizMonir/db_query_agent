import streamlit as st
import pandas as pd
from dotenv import load_dotenv
import os
import sys
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Use MinimalSQLAgent which doesn't have OpenAI client issues
from src.sql_agent_minimal import MinimalSQLAgent as SimpleSQLAgent

# Load environment variables
load_dotenv()

# Page configuration
st.set_page_config(
    page_title="Database Query Agent",
    page_icon="🤖",
    layout="wide"
)

# Initialize session state
if 'chat_history' not in st.session_state:
    st.session_state.chat_history = []
if 'sql_agent' not in st.session_state:
    st.session_state.sql_agent = None

# Title and description
st.title("🤖 AI Database Query Assistant")
st.markdown("""
Ask questions about your database in natural language and get SQL queries and results.
The AI agent will analyze your database schema and generate optimized queries.
""")

# Sidebar for configuration
with st.sidebar:
    st.header("⚙️ Configuration")
    
    # Check environment variables
    env_vars = {
        'OpenAI API Key': 'OPENAI_API_KEY',
        'Database Host': 'DB_HOST',
        'Database Name': 'DB_NAME',
        'Database User': 'DB_USER'
    }
    
    all_configured = True
    for name, var in env_vars.items():
        if os.getenv(var):
            st.success(f"✅ {name} configured")
        else:
            st.error(f"❌ {name} not configured")
            all_configured = False
    
    if all_configured:
        if st.button("🔄 Reset Agent"):
            if st.session_state.sql_agent:
                st.session_state.sql_agent.close()
            st.session_state.sql_agent = None
            st.session_state.chat_history = []
            st.rerun()
    
    st.divider()
    
    # Display statistics
    st.header("📊 Statistics")
    st.metric("Total Queries", len(st.session_state.chat_history))
    
    # Clear history button
    if st.button("🗑️ Clear History"):
        st.session_state.chat_history = []
        st.rerun()

# Main area
if not all_configured:
    st.error("Please configure all environment variables in the .env file")
    st.code("""
# Required environment variables:
OPENAI_API_KEY=your_openai_api_key
DB_HOST=localhost
DB_PORT=5432
DB_NAME=your_database
DB_USER=your_user
DB_PASSWORD=your_password
    """)
else:
    # Initialize agent if needed
    if st.session_state.sql_agent is None:
        with st.spinner("Initializing AI agent..."):
            try:
                st.session_state.sql_agent = SimpleSQLAgent()
                st.success("✅ Agent initialized successfully!")
            except Exception as e:
                st.error(f"Failed to initialize agent: {str(e)}")
                st.stop()
    
    # Chat interface
    col1, col2 = st.columns([2, 1])
    
    with col1:
        st.header("💬 Chat")
        
        # Display chat history
        for item in st.session_state.chat_history:
            with st.container():
                st.markdown(f"**🧑 You:** {item['query']}")
                
                if item.get('sql'):
                    st.code(item['sql'], language='sql')
                
                if item.get('error'):
                    st.error(f"Error: {item['error']}")
                elif item.get('results'):
                    st.markdown("**📊 Results:**")
                    if item['results']['data']:
                        df = pd.DataFrame(item['results']['data'])
                        st.dataframe(df, use_container_width=True)
                        st.caption(f"Returned {item['results']['row_count']} rows")
                    else:
                        st.info("Query executed but returned no results")
                
                st.divider()
    
    with col2:
        st.header("📋 Query Examples")
        st.markdown("""
        Try these example queries:
        
        - How many catchments are in Uganda?
        - Show me all tables related to water resources
        - What is the total population by district?
        - List all projects with their status
        - Find tables containing user information
        """)
    
    # Query input
    with st.form("query_form", clear_on_submit=True):
        user_query = st.text_area(
            "Enter your question:",
            placeholder="e.g., How many catchments are in country Uganda?",
            height=100
        )
        
        col1, col2, col3 = st.columns([1, 1, 4])
        with col1:
            generate_sql = st.form_submit_button("🔍 Generate SQL", use_container_width=True)
        with col2:
            execute_sql = st.form_submit_button("▶️ Execute Query", use_container_width=True)
    
    # Process query
    if (generate_sql or execute_sql) and user_query:
        with st.spinner("🤔 Analyzing your query..."):
            # Generate SQL
            result = st.session_state.sql_agent.generate_sql(user_query)
            
            if result['success']:
                chat_item = {
                    'query': user_query,
                    'sql': result['query'],
                    'schema_context': result.get('schema_context', '')
                }
                
                # Execute if requested
                if execute_sql:
                    with st.spinner("⚡ Executing query..."):
                        exec_result = st.session_state.sql_agent.execute_query(result['query'])
                        
                        if exec_result['success']:
                            chat_item['results'] = exec_result
                        else:
                            chat_item['error'] = exec_result['error']
                
                st.session_state.chat_history.append(chat_item)
                st.rerun()
            else:
                st.error(f"Failed to generate SQL: {result['error']}")

# Footer
st.divider()
st.caption("Built with OpenAI GPT-4 and PostgreSQL")
st.caption("Note: The AI agent uses your database schema comments to understand table and column purposes for better query generation.")