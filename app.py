"""
Simple web interface for the esophageal cancer treatment planning tool.

This Flask application presents a form for entering patient data and
returns an evidence‑based treatment recommendation using the
`recommend_plan` function from `esophageal_cancer_tool.py`.

To run the app locally:

    pip install flask
    python3 app.py

Navigate to http://127.0.0.1:5000/ in your web browser.  Enter the
relevant patient information and click "Submit" to see the recommended
plan and rationale.
"""

# -*- coding: utf-8 -*-
from flask import Flask, render_template, request
from esophageal_cancer_tool import recommend_plan

app = Flask(__name__)


@app.route("/", methods=["GET", "POST"])
def index():
    result = None

    # Static grouped references shown below results
    references = {
        "Definitive / Neoadjuvant Chemoradiation": [
            ("RTOG 85-01", "https://pubmed.ncbi.nlm.nih.gov/10235156/"),
            ("CROSS", "https://pubmed.ncbi.nlm.nih.gov/22646630/"),
            ("PRODIGE5/ACCORD17", "https://pubmed.ncbi.nlm.nih.gov/24556041/"),
        ],
        "Peri-operative Chemotherapy (Resectable Adenocarcinoma)": [
            ("MAGIC", "https://pubmed.ncbi.nlm.nih.gov/16822992/"),
            ("FNCLCC ACCORD 07", "https://pubmed.ncbi.nlm.nih.gov/21444866/"),
            ("FLOT4", "https://pubmed.ncbi.nlm.nih.gov/30982686/"),
            ("NEO-AEGIS", "https://pubmed.ncbi.nlm.nih.gov/37318943/"),
            ("ESOPEC", "https://pubmed.ncbi.nlm.nih.gov/38764613/"),
            ("MATTERHORN", "https://pubmed.ncbi.nlm.nih.gov/39827347/"),
        ],
        "Adjuvant / Immunotherapy": [
            ("CheckMate-577 (adjuvant nivolumab)", "https://pubmed.ncbi.nlm.nih.gov/33843945/"),
            ("CheckMate-649", "https://pubmed.ncbi.nlm.nih.gov/34102137/"),
            ("KEYNOTE-811", "https://pubmed.ncbi.nlm.nih.gov/34912120/"),
        ],
        "Guidelines": [
            ("NCCN Guidelines v4.2025 (login required)", "https://www.nccn.org/guidelines/category_1"),
        ],
    }

    if request.method == "POST":
        # Basic clinical fields
        age_raw = request.form.get("age", "").strip()
        stage = request.form.get("stage", "").strip()
        histology = request.form.get("histology", "adenocarcinoma").strip()

        size_raw = request.form.get("tumour_size_cm", "").strip()
        grade = request.form.get("grade", "").strip()
        lvi = request.form.get("lvi", "no")

        # Biomarkers
        her2 = request.form.get("her2", "negative")
        pdl1_raw = request.form.get("pdl1", "").strip()
        msi = request.form.get("msi", "negative")
        cldn = request.form.get("cldn", "negative")

        # Comorbidities (checkboxes)
        comorbidities = []
        if request.form.get("comorb_severe_pulm"):  # COPD / significant lung disease
            comorbidities.append("severe_pulm")
        if request.form.get("comorb_severe_card"):  # CAD / HF
            comorbidities.append("severe_card")
        if request.form.get("comorb_frailty"):
            comorbidities.append("frailty")
        if request.form.get("comorb_ckd"):
            comorbidities.append("ckd")
        if request.form.get("comorb_liver"):
            comorbidities.append("liver")
        if request.form.get("comorb_prior_rt"):
            comorbidities.append("prior_rt")
        if request.form.get("comorb_autoimmune"):
            comorbidities.append("autoimmune")
        if request.form.get("comorb_diabetes"):
            comorbidities.append("diabetes")
        if request.form.get("comorb_malnutrition"):
            comorbidities.append("malnutrition")

        comorbidities_other = request.form.get("comorbidities_other", "").strip()

        # Imaging — Option B structure
        tumour_location = request.form.get("tumour_location", "").strip()

        invasion_features = []
        if request.form.get("inv_none"):
            invasion_features.append("none_beyond_wall")
        if request.form.get("inv_adventitial"):
            invasion_features.append("adventitial_involvement")
        if request.form.get("inv_airway"):
            invasion_features.append("airway_invasion")
        if request.form.get("inv_aorta"):
            invasion_features.append("aortic_encasement")
        if request.form.get("inv_vertebral"):
            invasion_features.append("vertebral_body_involvement")
        if request.form.get("inv_diaphragm"):
            invasion_features.append("diaphragm_involvement")
        if request.form.get("inv_pericardium"):
            invasion_features.append("pericardial_involvement")
        if request.form.get("inv_pleural"):
            invasion_features.append("pleural_carcinomatosis")

        nodal_regions = []
        if request.form.get("node_mediastinal"):
            nodal_regions.append("mediastinal")
        if request.form.get("node_celiac"):
            nodal_regions.append("celiac")
        if request.form.get("node_supraclavicular"):
            nodal_regions.append("supraclavicular")
        if request.form.get("node_retroperitoneal"):
            nodal_regions.append("retroperitoneal")

        distant_met_sites = []
        if request.form.get("met_liver"):
            distant_met_sites.append("liver")
        if request.form.get("met_lung"):
            distant_met_sites.append("lung")
        if request.form.get("met_bone"):
            distant_met_sites.append("bone")
        if request.form.get("met_brain"):
            distant_met_sites.append("brain")
        if request.form.get("met_peritoneal"):
            distant_met_sites.append("peritoneal")
        if request.form.get("met_distant_nodes"):
            distant_met_sites.append("distant_nodes")
        met_other = request.form.get("met_other", "").strip()
        if met_other:
            distant_met_sites.append("other")

        imaging_other = request.form.get("imaging_findings", "").strip()

        surgical_candidate = request.form.get("surgical_candidate", "yes") == "yes"

        # Convert numeric fields safely
        age = int(age_raw) if age_raw.isdigit() else None
        tumour_size_cm = float(size_raw) if size_raw else None

        pdl1_cps = None
        if pdl1_raw:
            try:
                pdl1_cps = float(pdl1_raw)
            except ValueError:
                pdl1_cps = None

        biomarkers = {
            "HER2": (her2 == "positive"),
            "PD_L1_CPS": pdl1_cps,
            "MSI": (msi == "positive"),
            "CLDN18.2": (cldn == "positive"),
        }

        patient = {
            "age": age or 0,
            "stage": stage,
            "histology": histology,
            "tumour_size_cm": tumour_size_cm,
            "grade": grade or None,
            "lymphovascular_invasion": (lvi == "yes"),
            "biomarkers": biomarkers,
            "comorbidities": comorbidities,
            "comorbidities_other": comorbidities_other,
            "tumour_location": tumour_location,
            "invasion_features": invasion_features,
            "nodal_regions": nodal_regions,
            "distant_met_sites": distant_met_sites,
            "imaging_findings": imaging_other,
            "surgical_candidate": surgical_candidate,
        }

        rp = recommend_plan(patient)
        result = {
            "summary": rp.get("summary", ""),
            "details": rp.get("details", ""),
        }

    return render_template("index.html", result=result, references=references)


if __name__ == "__main__":
    # If 5000 is occupied (macOS AirPlay), change port to e.g. 5050
    app.run(host="0.0.0.0", port=5000, debug=False)