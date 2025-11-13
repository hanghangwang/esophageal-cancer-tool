# esophageal_cancer_tool.py — Fully Regenerated with Early-Stage NCCN Logic

"""
This module implements a full NCCN‑aligned decision engine for esophageal and GEJ
cancer management, including:

✔ Early‑stage logic (T1a EMR/ESD, T1b surgery)  
✔ FLOT vs CROSS tumor‑board rules for adenocarcinoma  
✔ Siewert II/III → FLOT  
✔ Distal adenocarcinoma → FLOT unless mediastinal nodes  
✔ Mid/upper adenocarcinoma → CROSS  
✔ SCC: cervical → definitive CRT; thoracic → CROSS  
✔ Metastatic disease → systemic therapy only  
✔ Unresectable (T4b) or nonsurgical → definitive CRT  
✔ Biomarker‑driven systemic therapy engine

This is a complete replacement file.
"""

from typing import Dict, List


# =============================================================================
# DATA CONTAINER
# =============================================================================
class PatientData:
    def __init__(self, data: Dict):
        self.age = data.get("age")
        self.stage = (data.get("stage", "") or "UNKNOWN").upper()
        self.histology = data.get("histology", "").lower()
        self.tumour_location = data.get("tumour_location", "").lower()
        self.tumour_size_cm = data.get("tumour_size_cm")
        self.grade = data.get("grade", "")
        self.lymphovascular_invasion = data.get("lymphovascular_invasion", False)
        self.biomarkers = data.get("biomarkers", {})
        self.comorbidities = data.get("comorbidities", [])
        self.invasion_features = [x.lower() for x in data.get("invasion_features", [])]
        self.nodal_regions = [x.lower() for x in data.get("nodal_regions", [])]
        self.distant_met_sites = [x.lower() for x in data.get("distant_met_sites", [])]
        self.surgical_candidate = data.get("surgical_candidate", True)


# =============================================================================
# BIOMARKER‑DRIVEN SYSTEMIC THERAPY
# =============================================================================

def systemic_therapy(p: PatientData) -> str:
    bmk = {k.upper(): v for k, v in p.biomarkers.items()}

    # MSI‑H → IO monotherapy
    if bmk.get("MSI_H"):
        return "Pembrolizumab monotherapy (MSI‑H/dMMR)"

    # HER2+ → trastuzumab
    if bmk.get("HER2"):
        return "Fluoropyrimidine + platinum + trastuzumab (HER2+)"

    # CLDN18.2
    if bmk.get("CLDN18_2"):
        return "Chemotherapy + zolbetuximab (CLDN18.2+)"

    # PD‑L1 CPS
    cps = bmk.get("PD_L1_CPS")
    if cps is not None:
        if cps >= 10:
            return "Platinum + fluoropyrimidine + nivolumab/pembrolizumab (PD‑L1 CPS ≥10)"
        else:
            return "Platinum + fluoropyrimidine chemotherapy"

    # Default regimen
    return "Platinum + fluoropyrimidine chemotherapy"


# =============================================================================
# MAIN NCCN DECISION ENGINE
# =============================================================================

def recommend_plan(data: Dict) -> Dict[str, str]:
    p = PatientData(data)
    details = []

    # ---------------------------------------------------------------------
    # 0. EARLY‑STAGE LOGIC (critical NCCN fix)
    # ---------------------------------------------------------------------
    # Extract T and N
    T = "UNKNOWN"
    N = "UNKNOWN"

    for part in p.stage.split("N"):
        if part.startswith("T"):
            T = part.split("T")[1].split("M")[0].upper()
    if "N" in p.stage:
        N = p.stage.split("N")[1].split("M")[0].upper()

    # T1a adenocarcinoma → EMR/ESD
    if p.histology == "adenocarcinoma" and "T1A" in p.stage:
        return {
            "summary": "T1a adenocarcinoma → Endoscopic resection (EMR/ESD)",
            "details": "NCCN: T1a mucosal adenocarcinoma should undergo EMR/ESD if feasible."
        }

    # T1b adenocarcinoma → esophagectomy (if surgical candidate)
    if p.histology == "adenocarcinoma" and "T1B" in p.stage and p.surgical_candidate:
        return {
            "summary": "T1b adenocarcinoma → Esophagectomy",
            "details": "NCCN: T1b (submucosal) adenocarcinoma → surgical resection if fit."
        }

    # T1a/T1b SCC → esophagectomy unless cervical
    if p.histology == "squamous" and ("T1A" in p.stage or "T1B" in p.stage):
        if "cervical" in p.tumour_location:
            return {
                "summary": "Cervical T1 SCC → Definitive CRT",
                "details": "NCCN: Cervical esophagus SCC → definitive chemoradiation."
            }
        return {
            "summary": "Early‑stage SCC → Esophagectomy",
            "details": "NCCN: T1a/b SCC of mid/distal esophagus → esophagectomy if feasible."
        }

    # ---------------------------------------------------------------------
    # 1. METASTATIC DISEASE
    # ---------------------------------------------------------------------
    metastatic = False

    if "M1" in p.stage:
        metastatic = True

    if any("carcinomatosis" in f for f in p.invasion_features):
        metastatic = True

    if any(site in ["liver", "lung", "bone", "brain", "peritoneum"] for site in p.distant_met_sites):
        metastatic = True

    if metastatic:
        return {
            "summary": "Metastatic disease — systemic therapy",
            "details": f"NCCN: Metastatic → systemic therapy only. Recommended: {systemic_therapy(p)}"
        }

    # ---------------------------------------------------------------------
    # 2. UNRESECTABLE T4b OR NON‑SURGICAL
    # ---------------------------------------------------------------------
    t4b = {"airway_invasion", "aortic_encasement", "vertebral_body_involvement"}

    if any(f in t4b for f in p.invasion_features) or not p.surgical_candidate:
        return {
            "summary": "Definitive CRT",
            "details": "NCCN: Unresectable T4b disease or non‑surgical candidate → definitive chemoradiation."
        }

    # ---------------------------------------------------------------------
    # 3. HISTOLOGY‑SPECIFIC LOGIC
    # ---------------------------------------------------------------------
    # ====================
    # NEUROENDOCRINE CARCINOMA (new override)
    # ====================
    if p.histology == "neuroendocrine":
        # Determine metastatic status
        metastatic_nec = (
            "M1" in p.stage
            or any(site in ["liver", "lung", "bone", "brain", "peritoneum"] for site in p.distant_met_sites)
            or any("carcinomatosis" in f for f in p.invasion_features)
        )

        if metastatic_nec:
            # First-line metastatic NEC
            regimen = "Platinum–etoposide chemotherapy (first-line for metastatic NEC)"

            # Brain metastasis nuance
            if "brain" in p.distant_met_sites:
                regimen += "; add SRS/WBRT per NCCN for brain metastases"

            # MSI-H rare exception
            if p.biomarkers.get("MSI_H"):
                regimen = "Pembrolizumab monotherapy (MSI-H NEC)"

            return {
                "summary": "Metastatic NEC → systemic therapy",
                "details": f"NCCN: Poorly differentiated NEC is treated with systemic therapy. Recommended: {regimen}. Consider FOLFIRI/FOLFOX/lurbinectedin upon progression; clinical trial preferred."
            }

        # Localized or locoregional NEC
        return {
            "summary": "High-grade neuroendocrine carcinoma → Platinum–etoposide chemotherapy",
            "details": "NCCN: Poorly differentiated NEC (localized) → platinum–etoposide ± radiation depending on resectability; surgery not first-line."
        }

    # ====================
    # SQUAMOUS
    # ====================
    if p.histology == "squamous":
        if "cervical" in p.tumour_location:
            return {
                "summary": "Cervical SCC → Definitive CRT",
                "details": "NCCN: Cervical SCC → definitive chemoradiation (no surgery)."
            }
        return {
            "summary": "CROSS for thoracic SCC",
            "details": "NCCN: Thoracic SCC → neoadjuvant chemoradiation (CROSS)."
        }

    # ====================
    # ADENOCARCINOMA
    # ====================
    loc = p.tumour_location

    # GEJ Siewert II/III → FLOT
    if "gej_siewert2" in loc or "gej_siewert3" in loc:
        return {
            "summary": "FLOT for GEJ Siewert II/III",
            "details": "NCCN: FLOT is preferred regimen for GEJ II/III based on FLOT4."
        }

    # Distal adenocarcinoma
    if "distal" in loc:
        if p.nodal_regions and any("mediastinal" in n for n in p.nodal_regions):
            return {
                "summary": "CROSS for distal adenocarcinoma with mediastinal nodes",
                "details": "NCCN: CROSS acceptable when mediastinal nodal downstaging is needed."
            }
        return {
            "summary": "FLOT for distal adenocarcinoma",
            "details": "NCCN: Distal esophageal adenocarcinoma behaves gastric‑like → FLOT preferred."
        }

    # Mid/upper adenocarcinoma → CROSS
    if "mid" in loc or "upper" in loc:
        return {
            "summary": "CROSS for mid/upper adenocarcinoma",
            "details": "NCCN: CROSS preferred for mediastinal clearance in mid/upper adenocarcinoma."
        }

    # Default adenocarcinoma pathway
    return {
        "summary": "Default CROSS (ambiguous adenocarcinoma)",
        "details": "Location unclear → default to CROSS per NCCN patterns."
    }
