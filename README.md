# RideSafe - Traffic Accident Analysis & Prediction System

<div align="center">

**An intelligent web application for analyzing traffic accidents and predicting accident risk in Imus, Philippines**

[Features](#features) • [Setup](#setup) • [Usage](#usage) • [Architecture](#architecture)

</div>

---

## Overview

RideSafe is a comprehensive traffic accident analysis and prediction platform that leverages machine learning and natural language processing to help understand and mitigate traffic accidents in Imus. The application provides interactive visualizations, predictive analytics, and an intelligent chatbot for accident data insights.

## Screenshots

<div align="center">
  <img src="static/screenshots/dashboard.jpg" alt="Dashboard" width="400">
  <img src="static/screenshots/heat-map.jpg" alt="Heatmap" width="400">
   <img src="static/screenshots/prediction.jpg" alt="Prediction" width="400">
   <img src="static/screenshots/chatbot.jpg" alt="Chatbot" width="400">
</div>

## Features

✨ **Key Capabilities:**

- **Interactive Dashboards**: Visualize accident trends with bar graphs, heat maps, and time-series charts
- **Accident Prediction**: ML-powered risk assessment by barangay and time of day
- **Intelligent Chatbot**: NLP-based chatbot powered by Google Generative AI for natural language queries about accident data
- **Data Analysis**: Comprehensive statistics and trend analysis from 2022-2024 traffic incident data
- **PDF Reports**: Generate professional summary reports of accident statistics
- **Geographic Visualization**: Interactive map views of accident hotspots using GeoJSON data
- **Geospatial Analysis**: Heat map generation showing accident density by location

## Tech Stack

- **Backend**: Flask (Python)
- **Frontend**: HTML5, CSS3, JavaScript
- **Data Processing**: Pandas, NumPy, Scikit-learn
- **Visualization**: Plotly, Folium, Matplotlib
- **Machine Learning**: Random Forest Classifier with SMOTE for class balancing
- **NLP**: Spacy, Google Generative AI
- **Geospatial**: GeoPandas, GeoJSON
- **Report Generation**: pdfkit, Jinja2

## Setup Instructions

### Prerequisites

- **Python 3.8 or higher**
- **pip** (Python package manager)
- **wkhtmltopdf** (required for PDF generation)
  - Windows: Download from [wkhtmltopdf](https://wkhtmltopdf.org/downloads.html)
  - macOS: `brew install wkhtmltopdf`
  - Linux: `apt-get install wkhtmltopdf`

### Installation

1. **Clone the repository**

   ```bash
   git clone https://github.com/yourusername/ridesafe.git
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
   python.exe -m pip install --upgrade pip
   pip install -r requirements.txt
   ```

4. **Download Spacy language model** (required for NLP features)

   ```bash
   python -m spacy download en_core_web_sm
   ```

5. **Set up environment variables**
   Create a `.env` file in the project root:

   ```
   GOOGLE_API_KEY=your_google_generative_ai_api_key
   FLASK_ENV=development
   ```

   Get your Google Generative AI API key from [Google AI Studio](https://makersuite.google.com/app/apikey)

6. **Prepare data**
   - Ensure `traffic-incident.xlsx` is in the project root directory
   - The file should contain sheets with accident data for 2022, 2023, and 2024

### Running the Application

1. **Start the Flask development server**

   ```bash
   python app.py
   ```

2. **Access the application**
   Open your browser and navigate to:
   ```
   http://localhost:5000
   ```

### Project Structure

```
ridesafe/
├── app.py                    # Main Flask application
├── requirements.txt          # Python dependencies
├── Procfile                  # Deployment configuration
├── traffic-incident.xlsx     # Traffic data (2022-2024)
│
├── scripts/                  # Data processing modules
│   ├── model.py             # ML prediction model
│   ├── nlp.py               # NLP chatbot functionality
│   ├── bar_graph.py         # Bar chart generation
│   ├── heat_map.py          # Heat map visualization
│   ├── chart.py             # Time-series charts
│   ├── barangay_list.py     # Barangay data processing
│   ├── month_data.py        # Monthly statistics
│   └── summary_report.py    # PDF report generation
│
├── templates/               # HTML templates
│   ├── index.html           # Main dashboard
│   ├── nlp.html             # Chatbot interface
│   └── pdf_template.html    # PDF report template
│
├── static/                  # Static assets
│   ├── assets/              # GeoJSON and data files
│   ├── js/                  # JavaScript files
│   └── style/               # CSS stylesheets
```

## Usage

### Dashboard

Visit the home page (`/`) to view:

- Monthly accident bar graph
- Accident trends by year (2022, 2023, 2024)
- Heat map of accident hotspots
- Interactive visualizations

### Prediction

The system predicts accident risk based on:

- **Barangay** (location)
- **Hour of day** (24-hour format)
- **Peak hours** (7-9 AM, 5-7 PM)

### Chatbot

Access the intelligent chatbot at `/chatbot` to:

- Ask natural language questions about accident data
- Get insights powered by Google Generative AI
- Retrieve statistics and trends

### API Endpoints

| Endpoint           | Method | Description                        |
| ------------------ | ------ | ---------------------------------- |
| `/`                | GET    | Main dashboard with visualizations |
| `/chatbot`         | GET    | Chatbot interface                  |
| `/handlePrompt`    | POST   | Send queries to chatbot            |
| `/getMonthData`    | POST   | Retrieve monthly accident data     |
| `/predict`         | POST   | Predict accident risk              |
| `/generate_report` | POST   | Generate PDF summary report        |

## Machine Learning Model

The prediction model uses:

- **Algorithm**: Random Forest Classifier
- **Features**: Barangay, hour of day, peak hour indicator
- **Data Balance**: SMOTE (Synthetic Minority Over-sampling Technique)
- **Training Data**: Traffic incidents from 2022-2024

## Deployment

### Deploy to Heroku

```bash
# Install Heroku CLI and login
heroku login

# Create a new Heroku app
heroku create your-app-name

# Deploy
git push heroku main

# View logs
heroku logs --tail
```

The `Procfile` is configured for Heroku deployment.

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Acknowledgments

- Traffic accident data from Imus City
- Built with Flask, Scikit-learn, and Google Generative AI
- Interactive visualizations powered by Plotly and Folium

---
