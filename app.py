from flask import Flask, render_template, request, jsonify, send_file
from flask_cors import CORS
from datetime import datetime
import pdfkit
from scripts.bar_graph import generate_bar_graph
from scripts.heat_map import generate_heat_map
from scripts.chart import generate_chart
from scripts.month_data import generate_month_list
from scripts.barangay_list import generate_barangay_list
from scripts.model import AccidentModel
from scripts.summary_report import generate_summary_report
import logging
import os

app = Flask(__name__)
CORS(app)

EXCEL_FILE_PATH = 'traffic-incident.xlsx'

#Loads model upon starting the webapp
accident_model = AccidentModel()
accident_model.load_model()

@app.route('/')
def home():
    bar_graph_html = generate_bar_graph(EXCEL_FILE_PATH)
    heat_map_html = generate_heat_map(EXCEL_FILE_PATH)
    chart_2022_html = generate_chart(EXCEL_FILE_PATH, 2022)
    chart_2023_html = generate_chart(EXCEL_FILE_PATH, 2023)
    chart_2024_html = generate_chart(EXCEL_FILE_PATH, 2024)

    return render_template('index.html', bar_graph = bar_graph_html, chart_2022 = chart_2022_html, chart_2023 = chart_2023_html, chart_2024 = chart_2024_html, heat_map = heat_map_html)

@app.route('/getMonthData', methods=['POST'])
def get_month_data():
    try:
        data = request.get_json()
        logging.debug(f'Received data:{data}')
        if not data or 'year' not in data or 'month' not in data:
            raise ValueError("Invalid input data. Ensure 'year' and 'month' are provided.")
        
        year = data.get('year')
        month_name = data.get('month')
        month = datetime.strptime(month_name, "%b").month 
        logging.debug(f"Year: {year}, Month: {month_name}")


        response = generate_month_list(EXCEL_FILE_PATH, year, month)
        logging.debug(f"Response from generate_month_list: {response}")

        return jsonify(response)
    
    except Exception as e:
        logging.error(f"Error in get_month_data: {str(e)}")
        return jsonify({'error':str(e)}), 500


@app.route('/predict', methods=['POST'])
def predict_accident():
    try:
        data = request.get_json()
        barangay = data.get('barangay')
        hour = data.get('hour')
        
        # Check if both barangay and hour are provided
        if barangay is None or hour is None:
            return jsonify({'error': 'Please provide barangay and hour.'}), 400
        
        # Extract the hour part from the "hh:mm" format
        try:
            hour = int(hour.split(":")[0])
        except ValueError:
            return jsonify({'error': 'Invalid hour format. Must be in "hh:mm" format.'}), 400
        except IndexError:
            return jsonify({'error': 'Hour format is incorrect. Please provide hour in "hh:mm" format.'}), 400
        
        # Ensure the hour is valid (between 0 and 23)
        if hour < 0 or hour > 23:
            return jsonify({'error': 'Hour must be between 00 and 23.'}), 400
        
        response = accident_model.predict_accident_chance(barangay, hour)
        return jsonify(response)
    
    except Exception as e:
        return jsonify({'error': f'No results found: {str(e)}'}), 500


@app.route('/getBarangayList', methods=['GET'])
def get_barangay_list():
    try:
        return generate_barangay_list(EXCEL_FILE_PATH)
    except Exception as e:
        return jsonify('Unable to generate list', e), 500

@app.route('/getSummaryReport/<string:barangay>', methods=['GET'])
def get_summary_report(barangay):
    try:
        summary_report =  generate_summary_report(barangay)
        rendered_html = render_template('pdf_template.html', barangay_name=barangay,
                                         peak_hour=summary_report["peak_hour"],
                                           lowest_hour=summary_report["lowest_hour"],
                                             peak_quarter = summary_report["peak_quarter"],
                                               lowest_quarter = summary_report["lowest_quarter"],
                                                 predictions=summary_report["predictions"])
        
        path_to_wkhtmltopdf = r'C:\Program Files\wkhtmltopdf\bin\wkhtmltopdf.exe'
        config = pdfkit.configuration(wkhtmltopdf=path_to_wkhtmltopdf)
        pdf = pdfkit.from_string(rendered_html, False, configuration=config)
         # Create a temporary file for the PDF
        pdf_file = os.path.join(os.getcwd(), "summary_report.pdf")
        with open(pdf_file, "wb") as f:
            f.write(pdf)
        return send_file(pdf_file, as_attachment=True, download_name="summary_report.pdf", mimetype="application/pdf")
    except Exception as e:
        return jsonify('Unable to generate summary report', e), 500

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 5000)), debug=True)