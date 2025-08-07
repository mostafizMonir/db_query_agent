-- Initialize database with comment tables
-- This script creates the comment tables and adds sample data

-- Create schema if not exists
CREATE SCHEMA IF NOT EXISTS dm_schema;

-- Create comment_on_table
CREATE TABLE IF NOT EXISTS dm_schema.comment_on_table (
    id TEXT,
    table_name TEXT,
    comment TEXT,
    schema_name TEXT
);

-- Create comment_on_column
CREATE TABLE IF NOT EXISTS dm_schema.comment_on_column (
    id TEXT,
    table_name TEXT,
    column_name TEXT,
    comment TEXT,
    schema_name TEXT
);

-- Create sample tables for demonstration
CREATE TABLE IF NOT EXISTS catchments (
    id SERIAL PRIMARY KEY,
    catchment_name VARCHAR(255),
    country VARCHAR(100),
    area_km2 DECIMAL(10, 2),
    population INTEGER,
    water_source VARCHAR(100),
    status VARCHAR(50),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS districts (
    id SERIAL PRIMARY KEY,
    district_name VARCHAR(255),
    country VARCHAR(100),
    region VARCHAR(100),
    population INTEGER,
    area_km2 DECIMAL(10, 2)
);

CREATE TABLE IF NOT EXISTS water_resources (
    id SERIAL PRIMARY KEY,
    resource_name VARCHAR(255),
    resource_type VARCHAR(100),
    catchment_id INTEGER REFERENCES catchments(id),
    district_id INTEGER REFERENCES districts(id),
    capacity_cubic_meters DECIMAL(15, 2),
    quality_rating VARCHAR(50)
);

-- Insert sample comment data
INSERT INTO dm_schema.comment_on_table (id, table_name, comment, schema_name) VALUES
('1', 'catchments', 'Stores information about water catchment areas including their location, size, and population served', 'public'),
('2', 'districts', 'Contains administrative district information including population and geographical data', 'public'),
('3', 'water_resources', 'Tracks water resources including wells, boreholes, rivers, and reservoirs with their capacity and quality', 'public');

INSERT INTO dm_schema.comment_on_column (id, table_name, column_name, comment, schema_name) VALUES
('1', 'catchments', 'catchment_name', 'Name of the water catchment area', 'public'),
('2', 'catchments', 'country', 'Country where the catchment is located', 'public'),
('3', 'catchments', 'area_km2', 'Total area of the catchment in square kilometers', 'public'),
('4', 'catchments', 'population', 'Number of people served by this catchment', 'public'),
('5', 'catchments', 'water_source', 'Primary source of water (river, lake, groundwater, etc.)', 'public'),
('6', 'districts', 'district_name', 'Official name of the administrative district', 'public'),
('7', 'districts', 'population', 'Total population of the district', 'public'),
('8', 'water_resources', 'resource_type', 'Type of water resource (well, borehole, river, reservoir, etc.)', 'public'),
('9', 'water_resources', 'capacity_cubic_meters', 'Maximum water capacity in cubic meters', 'public'),
('10', 'water_resources', 'quality_rating', 'Water quality assessment rating', 'public');

-- Insert sample data
INSERT INTO catchments (catchment_name, country, area_km2, population, water_source, status) VALUES
('Lake Victoria Basin', 'Uganda', 15000.50, 500000, 'Lake', 'Active'),
('Nile River Catchment', 'Uganda', 8500.25, 350000, 'River', 'Active'),
('Kyoga Basin', 'Uganda', 5200.75, 200000, 'Lake', 'Active'),
('Albert Basin', 'Uganda', 7800.00, 280000, 'Lake', 'Active'),
('Kagera Catchment', 'Uganda', 3500.50, 150000, 'River', 'Active');

INSERT INTO districts (district_name, country, region, population, area_km2) VALUES
('Kampala', 'Uganda', 'Central', 1659600, 189.0),
('Wakiso', 'Uganda', 'Central', 2915200, 1974.0),
('Mukono', 'Uganda', 'Central', 689400, 2968.0),
('Jinja', 'Uganda', 'Eastern', 515800, 767.0),
('Gulu', 'Uganda', 'Northern', 436345, 3059.0);