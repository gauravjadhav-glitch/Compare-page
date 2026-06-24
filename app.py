#!/usr/bin/env python3
import json
import os
import subprocess
import threading
import uuid
from pathlib import Path

from flask import Flask, render_template, request, jsonify, send_file, send_from_directory

app = Flask(__name__)
BASE_DIR = Path(__file__).parent
REPORT_DIR = BASE_DIR / "report"

jobs = {}


def load_env_pairs():
    env_path = BASE_DIR / ".env"
    if not env_path.exists():
        return []
    pairs = {}
    with open(env_path) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" not in line:
                continue
            key, val = line.split("=", 1)
            key = key.strip()
            val = val.strip()
            parts = key.rsplit("_", 1)
            if len(parts) == 2 and parts[1] in ("LIVE", "UAT"):
                name = parts[0].replace("_", " ").title()
                pairs.setdefault(name, {})[parts[1].lower()] = val
    result = []
    for name, urls in pairs.items():
        if "live" in urls and "uat" in urls:
            result.append({"name": name, "live": urls["live"], "uat": urls["uat"]})
    return result


def run_comparison(job_id, live_url, uat_url, page_name, viewports):
    slug = page_name.lower().replace(" ", "-")
    output_dir = str(REPORT_DIR / slug)
    cmd = [
        "python3", "compare.py",
        live_url, uat_url,
        "--viewports", ",".join(viewports),
        "--output", output_dir,
        "--wait", "8",
        "--top-issues", "30",
    ]
    jobs[job_id]["status"] = "running"
    jobs[job_id]["log"] = ""
    try:
        proc = subprocess.Popen(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, cwd=str(BASE_DIR),
        )
        for line in proc.stdout:
            jobs[job_id]["log"] += line
        proc.wait()
        if proc.returncode == 0:
            html_path = os.path.join(output_dir, "comparison_report.html")
            pdf_name = f"{slug}-ATD-Report.pdf"
            pdf_path = str(BASE_DIR / pdf_name)
            try:
                from playwright.sync_api import sync_playwright
                with sync_playwright() as p:
                    browser = p.chromium.launch(headless=True)
                    page = browser.new_page()
                    page.goto(f"file://{os.path.abspath(html_path)}", wait_until="networkidle")
                    page.wait_for_timeout(2000)
                    page.pdf(
                        path=pdf_path, format="A4", print_background=True,
                        margin={"top": "10mm", "bottom": "10mm", "left": "10mm", "right": "10mm"},
                    )
                    page.close()
                    browser.close()
                jobs[job_id]["pdf"] = pdf_name
                jobs[job_id]["log"] += f"\nPDF generated: {pdf_name}\n"
            except Exception as e:
                jobs[job_id]["log"] += f"\nPDF generation failed: {e}\n"

            jobs[job_id]["status"] = "completed"
            jobs[job_id]["report_path"] = slug
        else:
            jobs[job_id]["status"] = "failed"
            jobs[job_id]["log"] += "\nComparison failed.\n"
    except Exception as e:
        jobs[job_id]["status"] = "failed"
        jobs[job_id]["log"] += f"\nError: {e}\n"


@app.route("/")
def index():
    env_pairs = load_env_pairs()
    existing = []
    if REPORT_DIR.exists():
        for d in sorted(REPORT_DIR.iterdir()):
            if d.is_dir() and (d / "comparison_report.html").exists():
                name = d.name.replace("-", " ").title()
                pdf_name = f"{d.name}-ATD-Report.pdf"
                has_pdf = (BASE_DIR / pdf_name).exists()
                existing.append({"slug": d.name, "name": name, "has_pdf": has_pdf, "pdf_name": pdf_name})
    return render_template("index.html", env_pairs=env_pairs, existing=existing)


@app.route("/compare", methods=["POST"])
def compare():
    data = request.json
    live_url = data.get("live_url", "").strip()
    uat_url = data.get("uat_url", "").strip()
    page_name = data.get("page_name", "").strip()
    viewports = data.get("viewports", ["desktop"])

    if not live_url or not uat_url or not page_name:
        return jsonify({"error": "All fields are required"}), 400
    if not viewports:
        return jsonify({"error": "Select at least one viewport"}), 400
    for url in [live_url, uat_url]:
        if not url.startswith(("http://", "https://")):
            return jsonify({"error": f"Invalid URL: {url}"}), 400

    job_id = str(uuid.uuid4())[:8]
    jobs[job_id] = {"status": "queued", "page_name": page_name, "log": ""}
    t = threading.Thread(target=run_comparison, args=(job_id, live_url, uat_url, page_name, viewports))
    t.daemon = True
    t.start()
    return jsonify({"job_id": job_id})


@app.route("/status/<job_id>")
def status(job_id):
    job = jobs.get(job_id)
    if not job:
        return jsonify({"error": "Job not found"}), 404
    return jsonify({
        "status": job["status"],
        "log": job["log"],
        "report_path": job.get("report_path"),
        "pdf": job.get("pdf"),
    })


@app.route("/report/<slug>")
def view_report(slug):
    report_path = REPORT_DIR / slug / "comparison_report.html"
    if not report_path.exists():
        return "Report not found", 404
    return send_file(report_path)


@app.route("/download/<filename>")
def download_pdf(filename):
    pdf_path = BASE_DIR / filename
    if not pdf_path.exists():
        return "PDF not found", 404
    return send_file(pdf_path, as_attachment=True)


@app.route("/env-pairs")
def env_pairs():
    return jsonify(load_env_pairs())


if __name__ == "__main__":
    REPORT_DIR.mkdir(exist_ok=True)
    print("ATD Comparison Tool running at http://localhost:5000")
    app.run(debug=True, port=5000)
