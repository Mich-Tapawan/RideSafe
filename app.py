from flask import Flask, render_template, request, jsonify, send_file
from flask_cors import CORS
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from datetime import datetime
import pdfkit
import shutil
import re
import logging
import os
from io import BytesIO

from scripts.month_data import generate_month_list
from scripts.model import AccidentModel
from scripts.summary_report import generate_summary_report
from scripts.db import init_db
from scripts.seed_database import seed_database
from scripts.cache import warm_dashboard_cache, get_dashboard_html, get_barangay_list_cached

_log_level = os.environ.get("LOG_LEVEL", "INFO").upper()
logging.basicConfig(
    level=getattr(logging, _log_level, logging.INFO),
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)

app = Flask(__name__)
CORS(app)

limiter = Limiter(
    get_remote_address,
    app=app,
    default_limits=[],
    storage_uri="memory://",
)

accident_model = AccidentModel()


def _initialize_app():
    init_db()
    seed_database()
    accident_model.load_model()
    accident_model.precompute_city_hour_averages()
    warm_dashboard_cache()
    logging.info("RideSafe startup complete.")


_initialize_app()


@app.route("/health")
def health():
    return jsonify({"status": "ok"})


@app.route("/")
@limiter.limit("30 per minute")
def home():
    cache = get_dashboard_html()
    return render_template(
        "index.html",
        bar_graph=cache["bar_graph"],
        chart_2022=cache["chart_2022"],
        chart_2023=cache["chart_2023"],
        chart_2024=cache["chart_2024"],
        heat_map=cache["heat_map"],
    )


@app.route("/getMonthData", methods=["POST"])
def get_month_data():
    try:
        data = request.get_json()
        logging.debug("Received data: %s", data)
        if not data or "year" not in data or "month" not in data:
            raise ValueError("Invalid input data. Ensure 'year' and 'month' are provided.")

        year = data.get("year")
        month_name = data.get("month")
        month = datetime.strptime(month_name, "%b").month
        logging.debug("Year: %s, Month: %s", year, month_name)

        response = generate_month_list(year, month)
        logging.debug("Response from generate_month_list: %s", response)

        return jsonify(response)

    except Exception as e:
        logging.error("Error in get_month_data: %s", e)
        return jsonify({"error": str(e)}), 500


@app.route("/predict", methods=["POST"])
def predict_accident():
    try:
        data = request.get_json()
        barangay = data.get("barangay")
        hour = data.get("hour")

        if barangay is None or hour is None:
            return jsonify({"error": "Please provide barangay and hour."}), 400

        try:
            hour = int(hour.split(":")[0])
        except ValueError:
            return jsonify({"error": 'Invalid hour format. Must be in "hh:mm" format.'}), 400
        except IndexError:
            return jsonify(
                {"error": 'Hour format is incorrect. Please provide hour in "hh:mm" format.'}
            ), 400

        if hour < 0 or hour > 23:
            return jsonify({"error": "Hour must be between 00 and 23."}), 400

        response = accident_model.predict_accident_chance(barangay, hour)
        return jsonify(response)

    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception:
        logging.exception("Error in predict_accident")
        return jsonify({"error": "Unable to generate prediction."}), 500


@app.route("/getBarangayList", methods=["GET"])
def get_barangay_list():
    try:
        return jsonify(get_barangay_list_cached())
    except Exception:
        logging.exception("Error in get_barangay_list")
        return jsonify({"error": "Unable to generate barangay list."}), 500


def _wkhtmltopdf_config():
    path = os.environ.get("WKHTMLTOPDF_PATH")
    if path and os.path.isfile(path):
        return pdfkit.configuration(wkhtmltopdf=path)
    default_win = r"C:\Program Files\wkhtmltopdf\bin\wkhtmltopdf.exe"
    if os.path.isfile(default_win):
        return pdfkit.configuration(wkhtmltopdf=default_win)
    found = shutil.which("wkhtmltopdf")
    if found:
        return pdfkit.configuration(wkhtmltopdf=found)
    raise FileNotFoundError(
        "wkhtmltopdf not found. Install wkhtmltopdf or set WKHTMLTOPDF_PATH."
    )


@app.route("/getSummaryReport/<string:barangay>", methods=["GET"])
@limiter.limit("10 per minute")
def get_summary_report(barangay):
    try:
        selected_hour = request.args.get("hour")
        if selected_hour is not None:
            try:
                selected_hour = int(str(selected_hour).split(":")[0])
            except (ValueError, IndexError):
                return jsonify({"error": "Invalid hour query parameter."}), 400

        report = generate_summary_report(
            barangay,
            accident_model,
            selected_hour=selected_hour,
        )
        rendered_html = render_template("pdf_template.html", **report)

        pdf_options = {
            "page-size": "A4",
            "margin-top": "12mm",
            "margin-right": "12mm",
            "margin-bottom": "18mm",
            "margin-left": "12mm",
            "encoding": "UTF-8",
            "enable-local-file-access": None,
            "footer-center": "RideSafe · Page [page] of [topage]",
            "footer-font-size": "8",
        }
        config = _wkhtmltopdf_config()
        pdf_bytes = pdfkit.from_string(
            rendered_html,
            False,
            configuration=config,
            options=pdf_options,
        )

        safe_name = re.sub(r"[^\w\-]+", "_", report["barangay_name"])[:40]
        download_name = f"RideSafe_{safe_name}_summary.pdf"

        return send_file(
            BytesIO(pdf_bytes),
            as_attachment=True,
            download_name=download_name,
            mimetype="application/pdf",
        )
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except FileNotFoundError as e:
        return jsonify({"error": str(e)}), 500
    except Exception as e:
        logging.error("Error in get_summary_report: %s", e)
        return jsonify({"error": "Unable to generate summary report."}), 500


if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=int(os.environ.get("PORT", 5000)),
        debug=os.environ.get("FLASK_DEBUG") == "1",
    )
