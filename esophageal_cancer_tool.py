"""
esophageal_cancer_tool (NCCN 2025-aligned with structured inputs)
=================================================================

Generates evidence-based treatment recommendations for esophageal and
EGJ cancer per NCCN Guidelines v4.2025 and landmark trials.

Structured inputs:
- Comorbidities: coded selections (severe cardiopulmonary disease, frailty, etc.)
- Imaging: tumor location, local invasion, nodal regions, distant mets

Clickable references are returned as HTML-safe strings.

Key trials:
- CROSS: https://pubmed.ncbi.nlm.nih.gov/22646630/
- FLOT4: https://pubmed.ncbi.nlm.nih.gov/30982686/
- ESOPEC: https://pubmed.ncbi.nlm.nih.gov/38764613/
- NEO-AEGIS: https://pubmed.ncbi.nlm.nih.gov/37318943/
- MATTERHORN: https://pubmed.ncbi.nlm.nih.gov/39827347/
- CheckMate-577: https://pubmed.ncbi.nlm.nih.gov/33843945/
- CheckMate-649: https://pubmed.ncbi.nlm.nih.gov/34102137/
- KEYNOTE-811: https://pubmed.ncbi.nlm.nih.gov/34912120/
- NCCN Guidelines (login required): https://www.nccn.org/guidelines/category_1
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple, Any
import re


# -------------------------------------------------------------------
# Data structure
# -------------------------------------------------------------------

@dataclass
class PatientData:
    age: int
    stage: str
    histology: str  # "adenocarcinoma" or "squamous"

    # Pathologic / clinical features
    tumour_size_cm: Optional[float] = None
    grade: Optional[str] = None
    lymphovascular_invasion: Optional[bool] = None

    # Biomarkers
    biomarkers: Dict[str, Optional[float]] = field(default_factory=dict)

    # Comorbidities (coded)
    # e.g. ["severe_pulm", "severe_card", "frailty", "ckd", "liver", "prior_rt", "autoimmune", "diabetes", "malnutrition"]
    comorbidities: List[str] = field(default_factory=list)
    comorbidities_other: str = ""

    # Imaging structure (Option B)
    tumour_location: str = ""  # "cervical", "upper_thoracic", "mid_thoracic", "distal_thoracic", "gej_siewert1/2/3"
    invasion_features: List[str] = field(default_factory=list)
    # e.g. ["none_beyond_wall", "adventitial_involvement", "airway_invasion",
    #       "aortic_encasement", "vertebral_body_involvement",
    #       "diaphragm_involvement", "pericardial_involvement",
    #       "pleural_carcinomatosis"]
    nodal_regions: List[str] = field(default_factory=list)  # ["mediastinal","celiac","supraclavicular","retroperitoneal"]
    distant_met_sites: List[str] = field(default_factory=list)  # ["liver","lung","bone","brain","peritoneal","distant_nodes","other"]
    imaging_findings: str = ""

    surgical_candidate: bool = True


# -------------------------------------------------------------------
# TNM parser
# -------------------------------------------------------------------

def parse_stage(stage: str) -> Tuple[str, str, str]:
    """Parse TNM stage string into (T, N, M)."""
    s = stage.upper() if stage else ""
    T = re.search(r"T\d+[AB]?", s)
    N = re.search(r"N\d+[AB]?", s)
    M = re.search(r"M\d+[AB]?", s)
    return (T.group(0) if T else "", N.group(0) if N else "", M.group(0) if M else "")


# -------------------------------------------------------------------
# Main algorithm
# -------------------------------------------------------------------

def recommend_plan(patient: Dict) -> Dict[str, str]:
    """Generate a treatment plan for esophageal cancer.

    Parameters
    ----------
    patient : dict
        Expected keys (from the web form):
        - age, stage, histology
        - tumour_size_cm, grade, lymphovascular_invasion
        - biomarkers (dict with HER2, PD_L1_CPS, MSI, CLDN18.2)
        - comorbidities (list of coded strings, e.g. 'severe_pulm', 'frailty')
        - comorbidities_other (optional free text)
        - tumour_location (e.g. 'cervical', 'distal_thoracic', 'gej_siewert2')
        - invasion_features (list of coded strings, e.g. 'airway_invasion')
        - nodal_regions (list of coded strings)
        - distant_met_sites (list of coded strings, e.g. 'liver', 'peritoneal')
        - imaging_findings (free text)
        - surgical_candidate (bool)

    Returns
    -------
    dict with keys 'summary' and 'details'
    """

    # Convert dictionary into PatientData for the fields it knows about
    pdata = PatientData(
        age=patient.get("age"),
        stage=patient.get("stage", ""),
        histology=patient.get("histology", ""),
        tumour_size_cm=patient.get("tumour_size_cm"),
        grade=patient.get("grade"),
        lymphovascular_invasion=patient.get("lymphovascular_invasion"),
        biomarkers=patient.get("biomarkers", {}),
        comorbidities=patient.get("comorbidities", []),
        imaging_findings=patient.get("imaging_findings", ""),
    )

    tumour_location = (patient.get("tumour_location") or "").lower()
    invasion_features = [f.lower() for f in patient.get("invasion_features", [])]
    nodal_regions = [n.lower() for n in patient.get("nodal_regions", [])]
    distant_met_sites = [m.lower() for m in patient.get("distant_met_sites", [])]
    surgical_candidate = bool(patient.get("surgical_candidate", True))

    T_category, N_category, M_category = parse_stage(pdata.stage)
    T_upper = T_category.upper()
    N_upper = N_category.upper()
    M_upper = M_category.upper()

    details: List[str] = []
    summary_parts: List[str] = []

    # --- 1. Determine metastatic vs local/regional ---
    # If imaging shows metastatic sites, treat as metastatic regardless of M in TNM.
    # Determine if there are distant metastases either via coded distant_met_sites or
    # through invasion features that represent carcinomatosis/implants.  NCCN defines
    # pleural or peritoneal implants as distant metastases rather than local invasion
    # (eg, pleural carcinomatosis corresponds to M1 disease【944136750254746†L3550-L3577】).
    has_imaging_metastasis = False
    # copy of distant sites for reporting
    distant_sites_report: List[str] = []
    if distant_met_sites:
        has_imaging_metastasis = True
        distant_sites_report.extend(distant_met_sites)
    # treat pleural or peritoneal carcinomatosis as metastatic disease
    for f in invasion_features:
        if f in {"pleural_carcinomatosis", "peritoneal_carcinomatosis"}:
            has_imaging_metastasis = True
            # record as pleural/peritoneal metastasis for details
            if f == "pleural_carcinomatosis" and "pleura" not in distant_sites_report:
                distant_sites_report.append("pleura")
            if f == "peritoneal_carcinomatosis" and "peritoneal" not in distant_sites_report:
                distant_sites_report.append("peritoneal")
    if has_imaging_metastasis and (not M_upper or M_upper == "M0"):
        details.append(
            "Imaging demonstrates distant metastatic disease ({}), "
            "so the disease is functionally metastatic even if TNM lists M0."
            .format(", ".join(distant_sites_report))
        )
        M_upper = "M1"

    # --- 2. Determine unresectability / T4b based on invasion + TNM ---
    unresectable = False

    # T4b by TNM string
    if "4B" in T_upper:
        unresectable = True
        details.append(
            "Tumour is staged as T4b by TNM, generally unresectable and "
            "treated with definitive chemoradiation or systemic therapy."
        )

    # T4b-equivalent invasion patterns (airway, aorta, vertebral body, etc.)
    # Features that correspond to T4b (unresectable) disease.  NCCN defines
    # invasion of the trachea/airway, aorta, or vertebral body as T4b.  
    # Pericardial involvement is classified as T4a and is potentially
    # resectable; pleural or peritoneal carcinomatosis are distant
    # metastases (M1) rather than local invasion【944136750254746†L3550-L3577】.  
    t4b_like_flags = {
        "airway_invasion",
        "aortic_encasement",
        "vertebral_body_involvement",
    }
    if any(f in t4b_like_flags for f in invasion_features):
        if not unresectable:
            details.append(
                "Imaging shows invasion of critical adjacent structures "
                "(e.g., airway, aorta, vertebral body, pericardium, pleura), "
                "which is consistent with T4b and renders the tumour "
                "unresectable; definitive chemoradiation or systemic therapy "
                "is preferred."
            )
        unresectable = True

    # Cervical location: NCCN favors definitive chemoradiation
    cervical_location = tumour_location == "cervical"
    if cervical_location and not unresectable and M_upper in ("", "M0"):
        details.append(
            "Primary tumour is in the cervical esophagus, where NCCN "
            "recommends definitive chemoradiation rather than esophagectomy."
        )
        unresectable = True  # functionally treat as non-surgical

    # Metastatic disease is 'unresectable' from a curative esophagectomy standpoint
    if M_upper and M_upper != "M0":
        unresectable = True
        details.append(
            "Because the disease is metastatic ({}), curative esophagectomy "
            "is not appropriate; management is systemic/palliative."
            .format(M_upper)
        )

    # --- 3. Evaluate surgical fitness ---
    high_risk_surgery = False

    # Structured comorbidities from the web form
    comorbid_codes = set(c.lower() for c in pdata.comorbidities)
    if any(code in comorbid_codes for code in {
        "severe_pulm", "severe_card", "frailty", "ckd", "liver"
    }):
        high_risk_surgery = True
        details.append(
            "Significant comorbidities (e.g., severe cardiopulmonary disease, "
            "frailty, CKD, or liver disease) increase operative risk and may "
            "limit tolerance of esophagectomy."
        )

    # Explicit "not a surgical candidate" flag from the form
    if not surgical_candidate:
        high_risk_surgery = True
        details.append(
            "The patient has been assessed as not a surgical candidate; "
            "definitive chemoradiation or systemic therapy is preferred "
            "over esophagectomy."
        )

    # --- 4. Early disease: Tis/T1a ---
    if not unresectable and not high_risk_surgery:
        if T_upper in {"TIS", "T1A"}:
            details.append(
                f"Stage {T_upper} disease is confined to the mucosa. "
                "Endoscopic therapy (EMR/ESD) is preferred for high-grade "
                "dysplasia and T1a lesions when the lesion is small and "
                "without high-risk features."
            )
            summary_parts.append("Endoscopic resection (EMR/ESD)")
            details.append(
                "If the lesion is extensive or not amenable to endoscopic "
                "removal, esophagectomy is recommended."
            )

    # --- 5. T1b or T2 N0: surgery vs neoadjuvant ---
    if (
        not unresectable
        and not high_risk_surgery
        and T_upper in {"T1B", "T2"}
        and (not N_upper or N_upper == "N0")
    ):
        low_risk = True
        # High-risk features prompting neoadjuvant therapy
        if pdata.tumour_size_cm and pdata.tumour_size_cm >= 3:
            low_risk = False
        if pdata.grade and pdata.grade.lower().startswith("poor"):
            low_risk = False
        if pdata.lymphovascular_invasion:
            low_risk = False

        if low_risk:
            details.append(
                f"For a small (<3 cm), well-differentiated {pdata.histology} "
                "tumour without lymphovascular invasion (pT1b–pT2,N0), "
                "esophagectomy alone is an NCCN-accepted option."
            )
            summary_parts.append("Primary esophagectomy")
        else:
            details.append(
                "Because the tumour has high-risk features (size ≥3 cm, "
                "poor differentiation and/or lymphovascular invasion), "
                "neoadjuvant chemoradiation followed by esophagectomy is "
                "preferred."
            )
            summary_parts.append("Neoadjuvant chemoradiation → esophagectomy")

    # --- 6. Locally advanced resectable disease (T3/T4a or N+) ---
    if (
        not unresectable
        and not high_risk_surgery
        and (
            "T3" in T_upper
            or "T4A" in T_upper
            or (N_upper and N_upper != "N0")
        )
    ):
        # Locally advanced resectable disease
        details.append(
            f"Locally advanced stage {pdata.stage} is typically managed with "
            "neoadjuvant therapy followed by esophagectomy. Approaches "
            "include chemoradiation (CROSS-type) or peri-operative "
            "chemotherapy (e.g., FLOT) depending on histology and location."
        )
        # For GEJ Siewert II/III adenocarcinoma, peri-operative chemotherapy (FLOT) is preferred
        if tumour_location.startswith("gej_siewert") and pdata.histology.lower() == "adenocarcinoma":
            summary_parts.append("Peri-operative chemotherapy (FLOT) → esophagectomy")
        else:
            summary_parts.append("Neoadjuvant chemoradiation → esophagectomy")

    # --- 7. Adjuvant therapy after resection (conceptual guidance text) ---
    if (
        not unresectable
        and not high_risk_surgery
        and any("esophagectomy" in part.lower() for part in summary_parts)
    ):
        details.append(
            "After surgery, pathologic staging determines the need for "
            "adjuvant therapy. Residual disease (ypT+ and/or ypN+) after "
            "neoadjuvant chemoradiation and R0 resection should receive "
            "adjuvant nivolumab for one year (CheckMate 577)."
        )
        details.append(
            "If margins are positive (R1/R2), options include additional "
            "chemoradiation if not previously delivered or palliative "
            "systemic therapy, depending on prior treatment."
        )

    # --- 8. Unresectable or medically inoperable (non-metastatic) ---
    if (unresectable or high_risk_surgery) and M_upper in ("", "M0"):
        if cervical_location:
            summary_parts.append("Definitive chemoradiation (cervical esophagus)")
            details.append(
                "For cervical esophageal tumours, definitive chemoradiation "
                "is preferred over esophagectomy."
            )
        elif any(f in t4b_like_flags for f in invasion_features):
            summary_parts.append("Definitive chemoradiation (T4b/unresectable)")
            details.append(
                "Because the tumour is T4b/unresectable by local invasion, "
                "definitive chemoradiation is recommended."
            )
        elif high_risk_surgery and not unresectable:
            summary_parts.append("Definitive chemoradiation (medically inoperable)")
            details.append(
                "Although anatomically resectable, the patient is not a "
                "suitable surgical candidate; definitive chemoradiation is "
                "recommended."
            )

    # --- 9. Metastatic disease: systemic therapy based on biomarkers ---
    if M_upper and M_upper != "M0":
        """
        Construct systemic therapy recommendations for metastatic disease.  
        Priority is given to MSI-H/dMMR monotherapy, followed by HER2-targeted
        therapy, CLDN18.2-targeted therapy (when HER2 is negative), and
        immunotherapy combinations based on PD-L1 expression and histology.
        """
        systemic_options: List[str] = []
        bmk = {k.upper(): v for k, v in pdata.biomarkers.items()}
        hist = pdata.histology.lower()
        pd_l1 = bmk.get("PD_L1_CPS")

        # MSI-H/dMMR tumours: ICI monotherapy has regulatory approval and
        # supersedes other biomarker-directed therapies in first line
        if bmk.get("MSI"):
            systemic_options.append(
                "immune checkpoint inhibitor monotherapy (e.g., pembrolizumab "
                "or dostarlimab) for MSI-H/dMMR disease"
            )
        else:
            # HER2-positive disease: standard is fluoropyrimidine + platinum + trastuzumab
            if bmk.get("HER2"):
                option = "fluoropyrimidine + platinum chemotherapy + trastuzumab"
                # if PD-L1 CPS ≥5 in adenocarcinoma, immunotherapy may be added
                if pd_l1 is not None and hist == "adenocarcinoma" and pd_l1 >= 5:
                    option += " ± nivolumab or pembrolizumab"
                systemic_options.append(option)
            # CLDN18.2-positive disease only if HER2-negative
            if bmk.get("CLDN18.2") and not bmk.get("HER2"):
                systemic_options.append(
                    "FOLFOX or CAPOX + zolbetuximab for CLDN18.2-positive disease"
                )
            # PD-L1 driven therapy for squamous carcinoma (CheckMate 648)
            if hist == "squamous" and pd_l1 is not None:
                if pd_l1 >= 10:
                    systemic_options.append(
                        "platinum-based chemotherapy + nivolumab, or "
                        "nivolumab/ipilimumab in selected patients"
                    )
                else:
                    systemic_options.append(
                        "platinum-based chemotherapy ± nivolumab, depending on PD-L1 expression and prior therapy"
                    )
            # PD-L1 driven therapy for adenocarcinoma/GEJ (CheckMate 649 / KEYNOTE‑590).
            # Only consider this pathway if the tumour is not HER2-positive or CLDN18.2-positive,
            # because targeted agents take precedence.  When HER2-positive and PD-L1 ≥5, the
            # addition of nivolumab/pembrolizumab is already handled above with trastuzumab.
            if hist == "adenocarcinoma" and pd_l1 is not None and not bmk.get("HER2") and not bmk.get("CLDN18.2"):
                if pd_l1 >= 5:
                    systemic_options.append(
                        "fluoropyrimidine + platinum chemotherapy + nivolumab or pembrolizumab"
                    )
                else:
                    systemic_options.append(
                        "fluoropyrimidine + platinum chemotherapy with optional immunotherapy depending on local practice"
                    )
            # If no biomarker-driven options were generated, use standard chemo ± immunotherapy
            if not systemic_options:
                systemic_options.append(
                    "fluoropyrimidine + platinum chemotherapy (e.g., FOLFOX or CAPOX) with or without immunotherapy based on PD-L1 and histology"
                )

        details.append(
            "For metastatic disease, first-line systemic therapy is chosen "
            "based on histology and biomarkers. Options include: "
            + "; ".join(systemic_options)
            + ". Subsequent lines may incorporate agents such as ramucirumab + paclitaxel, "
              "irinotecan, or additional immunotherapy depending on prior exposure and tolerance."
        )
        summary_parts.append("Systemic therapy")

    # --- 10. Consolidate summary ---
    # Remove duplicates while preserving order
    summary = "; ".join(dict.fromkeys(summary_parts))
    if not summary:
        summary = (
            "No specific recommendation generated; please review clinical "
            "details and consult full NCCN guidelines and MDT discussion."
        )

    return {"summary": summary, "details": "\n".join(details)}

