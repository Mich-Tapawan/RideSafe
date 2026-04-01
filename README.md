# RideSafe - Traffic Accident Analysis & Prediction System

<div align="center">

**An RAG-powered web application for analyzing traffic accidents and predicting accident risk in Imus, Philippines**

[Features](#features) • [Setup](#setup) • [Architecture](#architecture) • [Usage](#usage)

</div>

---

## Overview

RideSafe is a comprehensive traffic safety platform that leverages Retrieval-Augmented Generation (RAG) and machine learning to provide data-driven insights for Imus City. By integrating historical incident data (2022–2024) with a vector database, RideSafe allows users to query complex accident patterns using natural language, visualize hotspots via interactive heatmaps, and predict localized risks using a Random Forest model.

## Screenshots

<div align="center">
  <img src="static/screenshots/dashboard.jpg" alt="Dashboard" width="400">
  <img src="static/screenshots/heat-map.jpg" alt="Heatmap" width="400">
  <img src="static/screenshots/prediction.jpg" alt="Prediction" width="400">
  <img src="static/screenshots/chatbot.jpg" alt="Chatbot" width="400">
</div>

## Features

✨ **Key Capabilities:**

- **RAG-Powered Chatbot**: Uses Gemini (`gemini-pro`) and Supabase pgvector to provide grounded, factual answers based on real 2022–2024 accident records
- **Semantic Search**: Replaced legacy spaCy keyword matching with vector embeddings (`text-embedding-004`) for natural language understanding — no exact phrasing required
- **Accident Prediction**: ML-powered risk assessment by barangay and hour of day using a Random Forest Classifier
- **Interactive Dashboards**: Dynamic bar graphs, heatmaps, and time-series charts built with Plotly and Folium
- **PDF Reports**: Generate professional stakeholder reports with peak-hour analysis and barangay-level trends
- **Geospatial Analysis**: Real-world mapping of accident density using GeoJSON data of Imus barangays

## Tech Stack

- **LLM & Embeddings**: Google Gemini (`gemini-pro`, `text-embedding-004`)
- **Vector Database**: Supabase (PostgreSQL + pgvector extension)
- **Backend**: Flask (Python 3.8+)
- **Machine Learning**: Scikit-learn (Random Forest + SMOTE)
- **Frontend**: HTML5, CSS3, JavaScript, Plotly.js
- **Mapping**: Folium, GeoPandas
- **Report Generation**: pdfkit (wkhtmltopdf), Jinja2

## Setup Instructions

### Prerequisites

- **Python 3.8+**
- **Supabase account** with pgvector enabled
- **Google AI Studio API key** — get one at [Google AI Studio](https://makersuite.google.com/app/apikey)
- **wkhtmltopdf** (required for PDF generation)
  - Windows: Download from [wkhtmltopdf.org](https://wkhtmltopdf.org/downloads.html)
  - macOS: `brew install wkhtmltopdf`
  - Linux: `apt-get install wkhtmltopdf`

### Installation

1. **Clone the repository**

   ```bash
   git clone https://github.com/Mich-Tapawan/RideSafe.git
   cd ridesafe
   ```

2. **Create a virtual environment** (recommended)

   ```bash
   # Windows
   python -m venv venv
   venv\Scripts\activate

   # macOS/Linux
   python3 -m venv venv
   source venv/bin/activate
   ```

3. **Install dependencies**

   ```bash
   pip install -r requirements.txt
   ```

4. **Set up environment variables**

   Create a `.env` file in the project root:

   ```
   GOOGLE_API_KEY=your_google_generative_ai_api_key
   SUPABASE_URL=your_supabase_project_url
   SUPABASE_ANON_KEY=your_supabase_anon_key
   SUPABASE_SERVICE_KEY=your_supabase_service_role_key
   FLASK_ENV=development
   ```

   > `SUPABASE_SERVICE_KEY` is only required for the one-time ingestion script. The app itself uses `SUPABASE_ANON_KEY` (anon key) for read queries.

5. **Initialize the vector database**

   Run the SQL setup script once in your Supabase SQL editor to create the tables, vector columns, and search functions:

   ```
   supabase_setup.sql
   ```

   Then run the ingestion script to embed and upload your Excel records to Supabase:

   ```bash
   python scripts/ingest_to_supabase.py
   ```

   This only needs to be run once (or again if your data changes).

### Running the Application

1. **Start the Flask development server**

   ```bash
   python app.py
   ```

2. **Access the application** at `http://localhost:5000`

## Architecture

The chatbot operates on a dual-logic flow:

**Semantic flow** — for general and narrative questions:
User question → embed with `text-embedding-004` → cosine similarity search against Supabase pgvector → retrieved accident records passed as context to Gemini → grounded answer

**Predictive flow** — for explicit risk/probability questions:
Regex detects prediction intent → extracts barangay + hour → `AccidentModel` returns probability score → result included in Gemini context

The two flows are not mutually exclusive — a prediction query also retrieves semantic context, giving Gemini both the ML score and relevant historical records to reference.

### Project Structure

```
ridesafe/
├── app.py                        # Main Flask application & routes
├── supabase_setup.sql            # Run once in Supabase SQL editor
├── traffic-incident.xlsx         # Source traffic data (2022–2024)
├── requirements.txt
├── Procfile                      # Heroku deployment config
│
├── scripts/
│   ├── rag_chatbot.py            # RAG pipeline (replaces nlp.py)
│   ├── chatbot.py                # Gemini embed + chat helpers
│   ├── ingest_to_supabase.py     # One-time Excel → pgvector ingestion
│   ├── model.py                  # Random Forest prediction model
│   ├── bar_graph.py              # Plotly trend charts
│   ├── heat_map.py               # Folium geographic visualization
│   ├── chart.py                  # Time-series charts
│   ├── barangay_list.py          # Barangay data processing
│   ├── month_data.py             # Monthly statistics
│   └── summary_report.py        # PDF report generation
│
├── templates/
│   ├── index.html                # Main dashboard
│   ├── nlp.html                  # Chatbot interface
│   └── pdf_template.html        # PDF report template
│
└── static/
    ├── assets/                   # GeoJSON and data files
    ├── js/                       # JavaScript files
    └── style/                    # CSS stylesheets
```

## API Endpoints

| Endpoint           | Method | Description                              |
| ------------------ | ------ | ---------------------------------------- |
| `/`                | GET    | Main dashboard with visualizations       |
| `/chatbot`         | GET    | Chatbot interface                        |
| `/handlePrompt`    | POST   | Chatbot endpoint (RAG + semantic search) |
| `/getMonthData`    | POST   | Retrieve monthly accident statistics     |
| `/predict`         | POST   | Returns ML-based accident probability    |
| `/generate_report` | POST   | Downloads a localized PDF summary report |

## Machine Learning Model

The prediction model uses:

- **Algorithm**: Random Forest Classifier
- **Features**: Barangay, hour of day, peak hour indicator
- **Data balance**: SMOTE (Synthetic Minority Over-sampling Technique)
- **Training data**: Traffic incidents from 2022–2024

## Deployment

### Deploy to Heroku

```bash
heroku login
heroku create your-app-name
git push heroku main
heroku logs --tail
```

The `Procfile` is configured for Heroku deployment.

## License

This project is licensed under the MIT License — see the LICENSE file for details.

## Acknowledgments

- Traffic accident data from Imus City
- Built with Flask, Scikit-learn, and Google Generative AI
- Interactive visualizations powered by Plotly and Folium
- Vector search powered by Supabase pgvector
