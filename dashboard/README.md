# Procurement Intelligence Streamlit Dashboard

A comprehensive multi-page Streamlit dashboard for procurement market intelligence and tender analysis.

## Features

### 📈 Executive Overview
Real-time market metrics including:
- Total tenders and market value
- Procurement type distribution
- Geographic coverage analysis
- Summary statistics and trends

### 🎯 Opportunity Radar
Intelligent tender prioritization:
- Opportunity ranking by priority score
- Value vs. deadline analysis
- CPV code filtering
- Match scoring for opportunities

### 👥 Buyer Intelligence
Detailed buyer profile analysis:
- Top buyers by spend
- Buyer type classification
- Geographic distribution
- Spending patterns and behavior

### 🏆 Supplier & Awards
Contract award analytics:
- Award criteria analysis
- Winner identification
- Award value distribution
- Win rate metrics

### 📊 Trends & Forecasts
Market trends and predictions:
- Historical trend analysis
- AI-powered forecasting
- Segment performance tracking
- 30 & 90-day outlook

### 🤖 Procurement Copilot
Natural language Q&A interface:
- Ask questions in plain English
- Automatic data summarization
- Query suggestions
- Context-aware responses

## Quick Start

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Set Up Databricks Connection
Create a `.env` file:
```env
DATABRICKS_HOST=https://your-workspace.cloud.databricks.com
DATABRICKS_HTTP_PATH=/sql/1.0/warehouses/your-warehouse-id
DATABRICKS_TOKEN=your-token
```

Load environment variables:
```powershell
.\load-env.ps1
```

### 3. Set Up dbt
Verify connection:
```bash
dbt debug
```

### 4. Create Mock Data (if needed)
Run the SQL script in Databricks:
```sql
-- Copy contents of scripts/create_mock_sources.sql
-- Run in Databricks SQL Editor
```

### 5. Run the Dashboard
```bash
streamlit run dashboard/app.py
```

The dashboard will open at `http://localhost:8501`

## Architecture

```
dashboard/
├── app.py                 # Main Streamlit app
├── pages/
│   ├── __init__.py
│   ├── executive_overview.py
│   ├── opportunity_radar.py
│   ├── buyer_intelligence.py
│   ├── supplier_awards.py
│   ├── trends_forecasts.py
│   └── copilot.py
└── README.md
```

## Data Source

The dashboard connects to Databricks Unity Catalog tables:
- `samples.ted_intelligence.notices` - Procurement notices
- `samples.ted_intelligence.lots` - Procurement lots
- `samples.ted_intelligence.award_criteria` - Award decision criteria
- `samples.ted_intelligence.organizations` - Buyer and supplier organizations

## Key Metrics

- **Total Tenders**: Count of procurement notices
- **Market Value**: Aggregate procurement spending
- **Priority Score**: ML-based opportunity ranking (0-10)
- **Match Score**: Supplier alignment metric (0-100)
- **Win Rate**: Percentage of successful awards

## Customization

To connect to live dbt models instead of mock data:
1. Update page files to query from Databricks directly
2. Use dbt source tables for queries
3. Add SQL queries to fetch real data

Example:
```python
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config import get_spark

spark = get_spark()
notices_df = spark.sql("SELECT * FROM samples.ted_intelligence.notices")
```

## Support

For issues or questions:
1. Check Streamlit documentation: https://docs.streamlit.io
2. Verify Databricks connection: `dbt debug`
3. Review mock data: `scripts/create_mock_sources.sql`
