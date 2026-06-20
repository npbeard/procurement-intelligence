# Procurement Intelligence Dashboard - Quick Start Guide

## What Was Created

A complete 6-page Streamlit dashboard with these business intelligence sections:

### 1. **📈 Executive Overview** - "What is the market?"
- Market size and value metrics
- Procurement type distribution  
- Geographic coverage
- Key statistics and trends

### 2. **🎯 Opportunity Radar** - "Which tenders should we prioritize?"
- Opportunity ranking by priority score
- Value vs. deadline analysis
- CPV code filtering
- Priority matrix visualization

### 3. **👥 Buyer Intelligence** - "Who is buying?"
- Top buyers by spending
- Buyer type and location analysis
- Detailed buyer profiles
- Spending patterns

### 4. **🏆 Supplier & Awards** - "Who is winning?"
- Award criteria breakdown
- Winners identification
- Win rate metrics
- Contract value analysis

### 5. **📊 Trends & Forecasts** - "What is changing?"
- Historical trend analysis
- AI-powered 30/90-day forecasting
- Segment performance tracking
- Growth predictions

### 6. **🤖 Procurement Copilot** - "Can users ask anything naturally?"
- Natural language Q&A interface
- Market intelligence queries
- Intelligent auto-suggestions
- Context-aware responses

## How to Run

### Step 1: Ensure Databricks is Set Up
```powershell
# Load environment variables
.\load-env.ps1

# Verify dbt connection
dbt debug
```

### Step 2: Create Mock Data (Optional - if you haven't run the SQL yet)
In Databricks SQL Editor, run:
```sql
-- Copy contents from: scripts/create_mock_sources.sql
```

### Step 3: Start the Dashboard
```powershell
# Option A: Using Python directly
python -m streamlit run dashboard/app.py

# Option B: Using the helper script
python run_dashboard.py
```

The dashboard will open at: **http://localhost:8501**

## File Structure Created

```
dashboard/
├── app.py                           # Main Streamlit app
├── README.md                        # Dashboard documentation
├── pages/
│   ├── __init__.py
│   ├── executive_overview.py        # Market overview page
│   ├── opportunity_radar.py         # Tender prioritization
│   ├── buyer_intelligence.py        # Buyer analysis
│   ├── supplier_awards.py           # Awards analysis
│   ├── trends_forecasts.py          # Trends & predictions
│   └── copilot.py                   # AI Q&A chatbot
```

## Features Included

✅ Multi-page navigation with sidebar
✅ Responsive metric cards and KPIs
✅ Interactive Plotly charts
✅ Data filtering and sorting
✅ Chat-based Q&A with suggestions
✅ Mock data for immediate testing
✅ Formatted tables and visualizations
✅ Professional UI styling

## Next Steps

### To Connect Real Data:
Each page currently uses mock data. To connect to live Databricks tables:

1. Update the `render()` functions in page files
2. Query from `samples.ted_intelligence.*` tables
3. Use Spark/SQL to fetch real data

Example:
```python
from config import get_spark

spark = get_spark()
notices = spark.sql("SELECT * FROM samples.ted_intelligence.notices")
st.dataframe(notices.toPandas())
```

### To Add More Features:
1. Create new page file in `dashboard/pages/`
2. Add a `render()` function
3. Register in `app.py` pages dictionary

### To Enable AI Chatbot:
Replace mock responses in `copilot.py` with:
- OpenAI GPT API calls
- LLaMA integration
- Custom ML model

## Troubleshooting

**"ModuleNotFoundError: No module named 'streamlit'"**
```powershell
pip install streamlit plotly
```

**"Databricks connection failed"**
```powershell
dbt debug  # Check connection
.\load-env.ps1  # Reload env vars
```

**"No such table" errors**
Run the SQL script to create mock tables:
```sql
-- scripts/create_mock_sources.sql in Databricks
```

## Questions?

Refer to [dashboard/README.md](README.md) for detailed documentation.
