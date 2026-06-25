-- Create mock source tables for testing dbt
-- Run this in Databricks SQL Editor

-- Create schema if it doesn't exist
CREATE SCHEMA IF NOT EXISTS samples.ted_intelligence;

-- Create notices table
CREATE TABLE IF NOT EXISTS samples.ted_intelligence.notices (
    notice_publication_id STRING NOT NULL,
    notice_uuid STRING,
    notice_type STRING,
    subtype_code STRING,
    issue_date STRING,
    publication_date STRING,
    gazette_id STRING,
    language STRING,
    regulatory_domain STRING,
    buyer_org_ref STRING,
    source_file STRING
);

-- Create lots table
CREATE TABLE IF NOT EXISTS samples.ted_intelligence.lots (
    notice_publication_id STRING NOT NULL,
    lot_id STRING,
    name STRING,
    description STRING,
    procurement_type STRING,
    cpv_code STRING
);

-- Create award_criteria table
CREATE TABLE IF NOT EXISTS samples.ted_intelligence.award_criteria (
    notice_publication_id STRING NOT NULL,
    lot_id STRING,
    criteria_type STRING,
    criteria_description STRING,
    weight DOUBLE
);

-- Create organizations table
CREATE TABLE IF NOT EXISTS samples.ted_intelligence.organizations (
    org_ref STRING NOT NULL,
    org_name STRING,
    org_type STRING,
    country STRING,
    city STRING
);

-- Insert sample data
INSERT INTO samples.ted_intelligence.notices VALUES
    ('TED-2026-001', 'uuid-001', 'ContractNotice', 'CN-SER', '2026-01-15', '2026-01-20', 'OJ-2026-001', 'EN', 'GENERAL', 'org-buyer-1', 'sample-001.xml'),
    ('TED-2026-002', 'uuid-002', 'ContractNotice', 'CN-SUP', '2026-01-16', '2026-01-21', 'OJ-2026-002', 'EN', 'GENERAL', 'org-buyer-2', 'sample-002.xml');

INSERT INTO samples.ted_intelligence.lots VALUES
    ('TED-2026-001', 'LOT-001', 'IT Services', 'Description of IT services', 'SERVICES', '72000000'),
    ('TED-2026-002', 'LOT-001', 'Office Supplies', 'Description of office supplies', 'SUPPLIES', '30125000');

INSERT INTO samples.ted_intelligence.award_criteria VALUES
    ('TED-2026-001', 'LOT-001', 'price', 'Lowest price', NULL),
    ('TED-2026-001', 'LOT-001', 'quality', 'Technical quality', 50.0);

INSERT INTO samples.ted_intelligence.organizations VALUES
    ('org-buyer-1', 'City of Example', 'PUBLIC_BODY', 'EX', 'Example City'),
    ('org-buyer-2', 'State Agency', 'PUBLIC_BODY', 'EX', 'State Capital');
