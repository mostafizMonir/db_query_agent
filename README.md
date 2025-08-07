# AI Database Query Agent 🤖

[![Python](https://img.shields.io/badge/Python-3.11-blue)](https://www.python.org/)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-Compatible-336791)](https://www.postgresql.org/)
[![OpenAI](https://img.shields.io/badge/OpenAI-GPT--4-00A67E)](https://openai.com/)
[![Docker](https://img.shields.io/badge/Docker-Ready-2496ED)](https://www.docker.com/)
[![Streamlit](https://img.shields.io/badge/Streamlit-UI-FF4B4B)](https://streamlit.io/)

An intelligent database query system that converts natural language questions into SQL queries for PostgreSQL databases using OpenAI GPT-4.

## Features

- **Natural Language to SQL**: Ask questions in plain English and get SQL queries
- **Smart Schema Analysis**: Uses comment tables to understand database structure
- **Token Optimization**: Only analyzes relevant tables and columns to minimize API costs
- **Multi-Agent System**: 
  - Schema Analyst: Identifies relevant tables and columns
  - SQL Expert: Generates optimized queries
  - Query Validator: Ensures query correctness and performance
- **Streamlit UI**: User-friendly chat interface
- **Docker Support**: Easy deployment with Docker Compose

## Architecture

The system uses your `comment_on_table` and `comment_on_column` tables to understand the database schema semantically. This allows it to:
1. Find relevant tables based on user queries
2. Identify important columns
3. Understand relationships between tables
4. Generate accurate SQL queries

## Setup

### 1. Clone and Navigate
```bash
cd db_query_agent
```

### 2. Configure Environment
Copy `.env.example` to `.env` and fill in your credentials:
```bash
cp .env.example .env
```

Edit `.env`:
```env
OPENAI_API_KEY=your_openai_api_key_here
DB_HOST=postgres  # Use 'postgres' for Docker, or your host for external DB
DB_PORT=5432
DB_NAME=your_database
DB_USER=your_user
DB_PASSWORD=your_password
```

### 3. Run with Docker Compose

```bash
# Build and start services
docker-compose up --build

# Or run in background
docker-compose up -d --build
```

The application will be available at `http://localhost:8501`

## Usage

1. Open `http://localhost:8501` in your browser
2. Ensure all environment variables are configured (check sidebar)
3. Type your question in natural language, e.g.:
   - "How many catchments are in Uganda?"
   - "Show me total population by district"
   - "List all water resources with their capacity"
4. Click "Generate SQL" to see the query
5. Click "Execute Query" to run it and see results

## Database Schema Requirements

Your database should have these comment tables populated:

```sql
-- Table comments
CREATE TABLE comment_on_table (
    id TEXT,
    table_name TEXT,
    comment TEXT,
    schema_name TEXT
);

-- Column comments
CREATE TABLE comment_on_column (
    id TEXT,
    table_name TEXT,
    column_name TEXT,
    comment TEXT,
    schema_name TEXT
);
```

## Token Optimization Strategies

1. **Selective Schema Loading**: Only loads relevant tables based on query
2. **Column Filtering**: Only includes columns mentioned in comments or names matching query terms
3. **Relationship Pruning**: Only loads foreign keys for relevant tables
4. **Context Limiting**: Truncates schema context to essential information
5. **Caching**: Reuses schema analysis for similar queries

## Project Structure

```
db_query_agent/
├── app.py                 # Streamlit UI
├── src/
│   ├── db_schema_analyzer.py  # Schema analysis with comment tables
│   └── sql_agents.py          # CrewAI agents for SQL generation
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
├── init.sql              # Sample database setup
└── .env                  # Configuration (create from .env.example)
```

## Troubleshooting

### Database Connection Issues
- Ensure PostgreSQL is running and accessible
- Check credentials in `.env` file
- For Docker, use `postgres` as DB_HOST
- For external DB, use actual hostname/IP

### Token Costs
- The system uses GPT-4-turbo for accuracy
- Each query analyzes only relevant schema portions
- Consider using GPT-3.5-turbo for lower costs (modify in `sql_agents.py`)

### Performance
- First query may be slower due to initialization
- Subsequent queries benefit from connection pooling
- Large result sets may take time to render

## Development

### Running Locally
```bash
pip install -r requirements.txt
streamlit run app.py
```

### Modifying Agents
Edit `src/sql_agents.py` to customize:
- Agent roles and goals
- LLM model selection
- Temperature settings
- Task descriptions

## Security Notes

- Never commit `.env` file with real credentials
- Use read-only database users when possible
- Consider query result limits for production
- Implement rate limiting for API calls