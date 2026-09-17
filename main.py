import os
import time
import uuid
import random
import socket
import json
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from fastapi import FastAPI, Request, HTTPException, UploadFile, File, Form
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

IS_VERCEL = bool(os.environ.get("VERCEL"))
BASE_DIR = Path(__file__).resolve().parent
UPLOAD_DIR = Path("/tmp/uploads") if IS_VERCEL else (BASE_DIR / "uploads")
try:
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
except OSError:
    pass

app = FastAPI(
    title="Pulse Shield — Patient Intelligence & 3D Health ID",
    description="Next-generation patient medical portal with 3D ID credentials, prescription OCR decrypter, and multilingual health engine.",
    version="2.3.0"
)

# Enable CORS for cross-origin and local file:// access
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Static and Templates
REPORTS_DIR = BASE_DIR / "reports"
try:
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
except OSError:
    pass

ASSETS_DIR = BASE_DIR / "assets"
try:
    ASSETS_DIR.mkdir(parents=True, exist_ok=True)
except OSError:
    pass

if UPLOAD_DIR.exists():
    app.mount("/uploads", StaticFiles(directory=str(UPLOAD_DIR)), name="uploads")
if REPORTS_DIR.exists():
    app.mount("/reports", StaticFiles(directory=str(REPORTS_DIR)), name="reports")
if ASSETS_DIR.exists():
    app.mount("/assets", StaticFiles(directory=str(ASSETS_DIR)), name="assets")

@app.api_route("/pulse_shield_logo.png", methods=["GET", "HEAD"])
async def get_pulse_shield_logo():
    return FileResponse(BASE_DIR / "pulse_shield_logo.png", media_type="image/png")

@app.api_route("/favicon.ico", methods=["GET", "HEAD"])
@app.api_route("/favicon.png", methods=["GET", "HEAD"])
async def get_favicon():
    return FileResponse(BASE_DIR / "favicon.png", media_type="image/png")
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))

# --- In-Memory Stores ---
ACTIVE_SESSIONS = {}
PENDING_OTPS = {}

def get_lan_ip() -> str:
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"

def generate_unique_health_id(name: str) -> str:
    seed = abs(hash(name + str(time.time()))) % 9000 + 1000
    return f"AH-2026-{seed}-IN"

DEFAULT_USER = {
    "id": "USR-8849",
    "health_id": "AH-2026-8849-IN",
    "name": "Hemanth Kumar",
    "phone": "+91 98765 43210",
    "email": "hemanth@pulseshield.ai",
    "age": 38,
    "gender": "Male",
    "blood_group": "O+ (Positive)",
    "dob": "1988-06-14",
    "address": "Banjara Hills, Road No. 12, Hyderabad, TS",
    "emergency_contact": "+91 91234 56789 (Family)",
    "primary_physician": "Dr. K. S. Rao, MD, FCCP (Pulmonology)",
    "hospital": "Apollo Health City, Jubilee Hills, Hyderabad",
    "allergies": ["Penicillin (Severe Rash)", "Sulfa Drugs", "Shellfish"],
    "chronic_conditions": ["Reactive Airway Disease", "Mild Hypertension"],
    "organ_donor": "Registered Organ Donor (Yes - All Organs)",
    "insurance_provider": "Star Health & Allied Insurance",
    "policy_no": "SH-MED-2026-99214",
    "avatar": "https://images.unsplash.com/photo-1534528741775-53994a69daeb?auto=format&fit=crop&w=400&q=80",
    "created_at": "2026-01-15"
}

# Current live vitals
CURRENT_VITALS = {
    "blood_pressure": "118/76",
    "blood_sugar": "98 mg/dL",
    "spo2": "99%",
    "pulse": "72 bpm",
    "temperature": "98.6 °F",
    "adherence_rate": "96%",
    "bmi": "22.4",
    "last_scanned_at": "Today, 11:30 AM"
}

DAILY_HEALTH_QUOTES = [
    {
        "quote": "The greatest wealth is health. Take care of your body, it's the only place you have to live.",
        "author": "Jim Rohn"
    },
    {
        "quote": "Let food be thy medicine and medicine be thy food.",
        "author": "Hippocrates"
    },
    {
        "quote": "It is health that is real wealth and not pieces of gold and silver.",
        "author": "Mahatma Gandhi"
    },
    {
        "quote": "A healthy outside starts from the inside.",
        "author": "Robert Urich"
    },
    {
        "quote": "To keep the body in good health is a duty... otherwise we shall not be able to keep our mind strong and clear.",
        "author": "Buddha"
    }
]

# Stored medical documents (vault)
MOCK_RECORDS = [
    {
        "id": "REC-101",
        "title": "Complete Blood Count (CBC) with Differential",
        "file_name": "CBC_Lab_Report_March2026.pdf",
        "file_url": "https://images.unsplash.com/photo-1579154204601-01588f351e67?auto=format&fit=crop&w=800&q=80",
        "file_type": "application/pdf",
        "size_kb": 342,
        "category": "Blood Test",
        "date": "2026-03-12",
        "doctor_status": "Verified",
        "doctor_name": "Dr. K. S. Rao, MD",
        "doctor_notes": "WBC normalized to 9,800/mcL. Neutrophils 62%, Lymphocytes 30%. Acute bacterial infection successfully cleared.",
        "key_metrics": {
            "Hemoglobin": "14.2 g/dL (Normal)",
            "Total WBC": "9,800 /mcL (Normal)",
            "Platelets": "285,000 /mcL (Normal)",
            "RBC Count": "4.9 mil/uL"
        }
    },
    {
        "id": "REC-102",
        "title": "High-Resolution Chest X-Ray (PA View)",
        "file_name": "Chest_XRay_PA_Digital.png",
        "file_url": "https://images.unsplash.com/photo-1516549655169-df83a0774514?auto=format&fit=crop&w=800&q=80",
        "file_type": "image/png",
        "size_kb": 1280,
        "category": "Imaging & Radiology",
        "date": "2026-03-09",
        "doctor_status": "Verified",
        "doctor_name": "Dr. Ramesh Gupta, MD (Radiology)",
        "doctor_notes": "Peribronchial cuffing resolving. Lungs clear, zero alveolar consolidation, cardiothoracic ratio normal.",
        "key_metrics": {
            "Impression": "Resolving Acute Bronchitis",
            "Pleural Effusion": "Nil",
            "Lung Fields": "Clear bilaterally"
        }
    },
    {
        "id": "REC-103",
        "title": "Outpatient Prescription Slip - Dr. K. S. Rao",
        "file_name": "Rx_Apollo_Pulmonology_Mar09.jpg",
        "file_url": "https://images.unsplash.com/photo-1584515979956-d9f6e5d09982?auto=format&fit=crop&w=800&q=80",
        "file_type": "image/jpeg",
        "size_kb": 512,
        "category": "Doctor Prescription",
        "date": "2026-03-09",
        "doctor_status": "Verified",
        "doctor_name": "Dr. K. S. Rao, MD",
        "doctor_notes": "Prescribed 6-day course of Augmentin 625 Duo, Ascoril-LS, Montair-LC, and Pan-D.",
        "key_metrics": {
            "Prescribing Clinic": "Apollo Health City Pulmonology",
            "Follow-up": "In 7 Days"
        }
    }
]

# Stored Past Health Reports & Medical History (Vault)
PAST_HEALTH_REPORTS = [
    {
        "id": "REC-HIST-01",
        "title": "Annual Executive Health Checkup 2025",
        "date": "2025-11-14",
        "category": "Cardiology & General Health",
        "hospital": "Apollo Health City, Hyderabad",
        "doctor_name": "Dr. Ramesh Gupta, MD (Cardiology)",
        "key_metrics": {
            "12-Lead ECG": "Normal Sinus Rhythm",
            "Total Cholesterol": "178 mg/dL (Desirable)",
            "Triglycerides": "135 mg/dL",
            "Liver Enzymes (ALT)": "24 U/L (Normal)"
        },
        "notes": "Cardiovascular risk low. Normal exercise tolerance. Preserved left ventricular systolic function."
    },
    {
        "id": "REC-HIST-02",
        "title": "Pulmonary Function Test (PFT) & Spirometry",
        "date": "2025-08-22",
        "category": "Pulmonology & Respiratory",
        "hospital": "Apollo Health City Pulmonology",
        "doctor_name": "Dr. K. S. Rao, MD, FCCP",
        "key_metrics": {
            "FEV1 / FVC Ratio": "82% (Normal Baseline)",
            "Forced Vital Capacity": "4.12 L (96% of predicted)",
            "Bronchodilator Reversibility": "Mild reactive tendency"
        },
        "notes": "Normal lung volume. Mild reactive airway irritability during seasonal transition; responsive to bronchodilators."
    },
    {
        "id": "REC-HIST-03",
        "title": "HbA1c Glycated Hemoglobin Test",
        "date": "2025-05-10",
        "category": "Endocrinology / Blood Test",
        "hospital": "Vijaya Diagnostics, Hyderabad",
        "doctor_name": "Dr. Sunita Reddy, MD, DM",
        "key_metrics": {
            "HbA1c": "5.6% (Non-Diabetic)",
            "Estimated Avg Glucose": "114 mg/dL",
            "Fasting Blood Sugar": "94 mg/dL"
        },
        "notes": "Excellent glycemic control. Zero microvascular or macrovascular diabetes risk indicators."
    },
    {
        "id": "REC-HIST-04",
        "title": "Comprehensive Thyroid Profile (TSH, T3, Free T4)",
        "date": "2025-01-18",
        "category": "Hormonal Panel / Blood Test",
        "hospital": "Lucid Diagnostics, Jubilee Hills",
        "doctor_name": "Dr. P. Naidu, MD",
        "key_metrics": {
            "TSH": "2.10 uIU/mL (Normal)",
            "Free T4": "1.32 ng/dL (Normal)",
            "Total T3": "118 ng/dL (Normal)"
        },
        "notes": "Thyroid gland functions within optimal physiological homeostasis. No levothyroxine therapy indicated."
    }
]

# Health Condition & Recovery Estimator
HEALTH_ISSUE_DATA = {
    "condition_name": "Acute Bacterial Bronchitis & Reactive Airway",
    "icd_10_code": "J20.8",
    "severity": "Moderate (Improving Rapidly)",
    "diagnosed_date": "2026-03-08",
    "total_estimated_days": 14,
    "days_elapsed": 4,
    "days_remaining": 10,
    "recovery_percentage": 58,
    "recommended_doctor": {
        "specialty": "Pulmonologist / Chest Physician",
        "recommended_doctor_name": "Dr. K. S. Rao, MD, FCCP",
        "experience": "18 Years Experience",
        "department": "Department of Pulmonology & Critical Care",
        "why_recommended": "Specializes in lower respiratory tract infections, bronchial spasm, and reactive airway management."
    },
    "milestones": [
        {
            "phase": "Phase 1: Acute Infection & Fever Control",
            "day_range": "Day 1 - 3",
            "status": "Completed",
            "description": "Fever subsided, body aches neutralized by antipyretics and initial antibiotic doses."
        },
        {
            "phase": "Phase 2: Bronchial Decongestion & Cough Softening",
            "day_range": "Day 4 - 7",
            "status": "Current",
            "description": "Sputum thinning with expectorant, airway irritation decreasing. Keep hydrated."
        },
        {
            "phase": "Phase 3: Airway Reactivity & Wheezing Resolution",
            "day_range": "Day 8 - 11",
            "status": "Upcoming",
            "description": "Peak expiratory flow rate returning to >85% baseline. Night wheeze ceases."
        },
        {
            "phase": "Phase 4: Complete Mucosal Healing & Full Remission",
            "day_range": "Day 12 - 14",
            "status": "Upcoming",
            "description": "Zero residual cough, full exercise tolerance restored, complete clinical discharge."
        }
    ],
    "recommended_blood_tests": [
        {
            "name": "Complete Blood Count (CBC) with Diff",
            "clinical_reason": "Monitors absolute neutrophil and lymphocyte counts to confirm bacterial clearance.",
            "sample_type": "Venous Blood (EDTA tube)",
            "fasting_required": "No fasting required",
            "target_range": "WBC 4,500 - 11,000 /mcL",
            "urgency": "High",
            "status": "Done (Normalizing)"
        },
        {
            "name": "High-Sensitivity C-Reactive Protein (hs-CRP)",
            "clinical_reason": "Quantifies systemic inflammation markers in bronchial microvascular beds.",
            "sample_type": "Serum Blood",
            "fasting_required": "No fasting required",
            "target_range": "< 3.0 mg/L",
            "urgency": "High",
            "status": "Scheduled for Day 8"
        },
        {
            "name": "Sputum Culture & Antimicrobial Sensitivity",
            "clinical_reason": "Validates targeted antibiotic efficacy against secondary pathogens.",
            "sample_type": "Early Morning Sputum",
            "fasting_required": "Rinse mouth with water only",
            "target_range": "Normal respiratory flora (no growth of H. influenzae / S. pneumoniae)",
            "urgency": "Medium",
            "status": "Sample in Lab"
        },
        {
            "name": "Serum Total IgE & Absolute Eosinophil Count",
            "clinical_reason": "Assesses allergic hyper-reactivity component causing bronchospasm.",
            "sample_type": "Venous Blood",
            "fasting_required": "8 hours fasting suggested",
            "target_range": "IgE < 100 IU/mL, AEC < 350 /mcL",
            "urgency": "Routine",
            "status": "Recommended"
        }
    ]
}

# Nearby Hospitals Directory
NEARBY_HOSPITALS_DATABASE = [
    {
        "id": "HYD-1",
        "name": "Apollo Health City, Jubilee Hills",
        "city": "Hyderabad",
        "location": "Road No. 72, Film Nagar, Jubilee Hills, Hyderabad",
        "lat": 17.4325,
        "lon": 78.4071,
        "rating": "4.9 \u2b50 (14,200+ Reviews)",
        "specialties": [
            "Pulmonology",
            "Cardiology",
            "Emergency ICU",
            "Oncology"
        ],
        "emergency_phone": "+91 40 2360 7777",
        "icu_beds_available": "14 Beds Available",
        "distance": "1.2 km away"
    },
    {
        "id": "HYD-2",
        "name": "Care Hospitals, Banjara Hills",
        "city": "Hyderabad",
        "location": "Road No. 1, Banjara Hills, Hyderabad",
        "lat": 17.4156,
        "lon": 78.4487,
        "rating": "4.8 \u2b50 (9,800+ Reviews)",
        "specialties": [
            "Internal Medicine",
            "Pulmonology",
            "Critical Care",
            "Neurology"
        ],
        "emergency_phone": "+91 40 6165 6565",
        "icu_beds_available": "9 Beds Available",
        "distance": "2.4 km away"
    },
    {
        "id": "HYD-3",
        "name": "Yashoda Hospitals, Somajiguda",
        "city": "Hyderabad",
        "location": "Raj Bhavan Road, Somajiguda, Hyderabad",
        "lat": 17.4262,
        "lon": 78.4578,
        "rating": "4.8 \u2b50 (11,400+ Reviews)",
        "specialties": [
            "Pulmonary Medicine",
            "Cardio-Thoracic",
            "Nephrology"
        ],
        "emergency_phone": "+91 40 4567 4567",
        "icu_beds_available": "18 Beds Available",
        "distance": "3.1 km away"
    },
    {
        "id": "HYD-4",
        "name": "AIG Hospitals, Gachibowli",
        "city": "Hyderabad",
        "location": "Mindspace Road, Gachibowli, Hyderabad",
        "lat": 17.4419,
        "lon": 78.3619,
        "rating": "4.9 \u2b50 (16,500+ Reviews)",
        "specialties": [
            "Gastroenterology",
            "Pulmonology",
            "Advanced Diagnostics"
        ],
        "emergency_phone": "+91 40 4244 4222",
        "icu_beds_available": "22 Beds Available",
        "distance": "6.2 km away"
    },
    {
        "id": "HYD-5",
        "name": "KIMS Hospitals, Secunderabad",
        "city": "Hyderabad",
        "location": "Minister Road, Secunderabad, Hyderabad",
        "lat": 17.4399,
        "lon": 78.4983,
        "rating": "4.7 \u2b50 (8,900+ Reviews)",
        "specialties": [
            "Chest Medicine",
            "Organ Transplant",
            "Trauma Care"
        ],
        "emergency_phone": "+91 40 4488 5000",
        "icu_beds_available": "12 Beds Available",
        "distance": "7.5 km away"
    },
    {
        "id": "HYD-6",
        "name": "Continental Hospitals, Financial District",
        "city": "Hyderabad",
        "location": "Nanakramguda, Financial District, Gachibowli, Hyderabad",
        "lat": 17.4183,
        "lon": 78.3444,
        "rating": "4.8 \u2b50 (7,200+ Reviews)",
        "specialties": [
            "Emergency & Trauma",
            "Cardiology",
            "Pulmonology"
        ],
        "emergency_phone": "+91 40 6700 0000",
        "icu_beds_available": "15 Beds Available",
        "distance": "8.8 km away"
    },
    {
        "id": "BLR-1",
        "name": "Manipal Hospital, HAL Old Airport Road",
        "city": "Bengaluru",
        "location": "98, HAL Old Airport Road, Kodihalli, Bengaluru",
        "lat": 12.9592,
        "lon": 77.6534,
        "rating": "4.9 \u2b50 (18,400+ Reviews)",
        "specialties": [
            "Cardiology",
            "Pulmonology",
            "Emergency ICU",
            "Neurology"
        ],
        "emergency_phone": "+91 80 2502 4444",
        "icu_beds_available": "19 Beds Available",
        "distance": "1.8 km away"
    },
    {
        "id": "BLR-2",
        "name": "Apollo Hospitals, Bannerghatta Road",
        "city": "Bengaluru",
        "location": "154/11, Opp IIMB, Bannerghatta Road, Bengaluru",
        "lat": 12.8943,
        "lon": 77.5982,
        "rating": "4.8 \u2b50 (15,600+ Reviews)",
        "specialties": [
            "Oncology",
            "Cardiothoracic",
            "Pulmonology"
        ],
        "emergency_phone": "+91 80 2630 4050",
        "icu_beds_available": "16 Beds Available",
        "distance": "3.4 km away"
    },
    {
        "id": "BLR-3",
        "name": "Fortis Hospital, Bannerghatta Road",
        "city": "Bengaluru",
        "location": "154/9, Bannerghatta Road, Opp IIMB, Bengaluru",
        "lat": 12.8956,
        "lon": 77.5991,
        "rating": "4.8 \u2b50 (12,100+ Reviews)",
        "specialties": [
            "Emergency Trauma",
            "Pulmonology",
            "Cardiac Care"
        ],
        "emergency_phone": "+91 80 6621 4444",
        "icu_beds_available": "11 Beds Available",
        "distance": "3.6 km away"
    },
    {
        "id": "BLR-4",
        "name": "Narayana Institute of Cardiac Sciences",
        "city": "Bengaluru",
        "location": "258/A, Bommasandra Industrial Area, Anekal Taluk, Bengaluru",
        "lat": 12.8021,
        "lon": 77.6974,
        "rating": "4.9 \u2b50 (21,000+ Reviews)",
        "specialties": [
            "Cardiology",
            "Heart Transplant",
            "Critical ICU"
        ],
        "emergency_phone": "+91 80 7122 2222",
        "icu_beds_available": "28 Beds Available",
        "distance": "7.2 km away"
    },
    {
        "id": "BLR-5",
        "name": "Aster CMI Hospital, Hebbal",
        "city": "Bengaluru",
        "location": "No. 43/42, NH 44, Sahakar Nagar, Hebbal, Bengaluru",
        "lat": 13.0561,
        "lon": 77.5925,
        "rating": "4.8 \u2b50 (13,400+ Reviews)",
        "specialties": [
            "Multi-Organ Transplant",
            "Pulmonology",
            "Trauma"
        ],
        "emergency_phone": "+91 80 4342 0100",
        "icu_beds_available": "14 Beds Available",
        "distance": "5.5 km away"
    },
    {
        "id": "BOM-1",
        "name": "Lilavati Hospital & Research Centre, Bandra",
        "city": "Mumbai",
        "location": "A-791, Bandra Reclamation, Bandra West, Mumbai",
        "lat": 19.0519,
        "lon": 72.8291,
        "rating": "4.9 \u2b50 (17,800+ Reviews)",
        "specialties": [
            "Critical Care ICU",
            "Cardiology",
            "Pulmonology"
        ],
        "emergency_phone": "+91 22 2675 1000",
        "icu_beds_available": "17 Beds Available",
        "distance": "2.1 km away"
    },
    {
        "id": "BOM-2",
        "name": "Kokilaben Dhirubhai Ambani Hospital, Andheri",
        "city": "Mumbai",
        "location": "Rao Saheb Achutrao Patwardhan Marg, Four Bungalows, Andheri West, Mumbai",
        "lat": 19.1314,
        "lon": 72.8252,
        "rating": "4.9 \u2b50 (22,500+ Reviews)",
        "specialties": [
            "Emergency Medicine",
            "Robotic Surgery",
            "Cardio-Pulmonary"
        ],
        "emergency_phone": "+91 22 4269 6969",
        "icu_beds_available": "24 Beds Available",
        "distance": "3.8 km away"
    },
    {
        "id": "BOM-3",
        "name": "P. D. Hinduja Hospital, Mahim",
        "city": "Mumbai",
        "location": "Veer Savarkar Marg, Mahim West, Mumbai",
        "lat": 19.033,
        "lon": 72.8402,
        "rating": "4.8 \u2b50 (14,900+ Reviews)",
        "specialties": [
            "Pulmonology",
            "Infectious Diseases",
            "Cardiology"
        ],
        "emergency_phone": "+91 22 2445 1515",
        "icu_beds_available": "13 Beds Available",
        "distance": "4.2 km away"
    },
    {
        "id": "BOM-4",
        "name": "Nanavati Max Super Speciality Hospital, Vile Parle",
        "city": "Mumbai",
        "location": "SV Road, LIC Colony, Suresh Colony, Vile Parle West, Mumbai",
        "lat": 19.0964,
        "lon": 72.8415,
        "rating": "4.8 \u2b50 (11,300+ Reviews)",
        "specialties": [
            "Heart & Lung Institute",
            "Neurosciences",
            "ICU"
        ],
        "emergency_phone": "+91 22 6836 0000",
        "icu_beds_available": "15 Beds Available",
        "distance": "4.9 km away"
    },
    {
        "id": "DEL-1",
        "name": "AIIMS (All India Institute of Medical Sciences)",
        "city": "Delhi",
        "location": "Sri Aurobindo Marg, Ansari Nagar, New Delhi",
        "lat": 28.5672,
        "lon": 77.21,
        "rating": "4.9 \u2b50 (35,000+ Reviews)",
        "specialties": [
            "National Apex Trauma",
            "Pulmonology",
            "Critical ICU"
        ],
        "emergency_phone": "+91 11 2658 8500",
        "icu_beds_available": "35 Beds Available",
        "distance": "2.5 km away"
    },
    {
        "id": "DEL-2",
        "name": "Medanta - The Medicity, Gurugram",
        "city": "Delhi",
        "location": "CH Bakhtawar Singh Road, Sector 38, Gurugram, Delhi NCR",
        "lat": 28.4395,
        "lon": 77.0422,
        "rating": "4.9 \u2b50 (28,000+ Reviews)",
        "specialties": [
            "Chest Surgery",
            "Cardiology",
            "Emergency ICU"
        ],
        "emergency_phone": "+91 124 414 1414",
        "icu_beds_available": "31 Beds Available",
        "distance": "4.8 km away"
    },
    {
        "id": "DEL-3",
        "name": "Max Super Speciality Hospital, Saket",
        "city": "Delhi",
        "location": "1, 2, Press Enclave Marg, Saket Institutional Area, New Delhi",
        "lat": 28.5282,
        "lon": 77.2117,
        "rating": "4.8 \u2b50 (19,200+ Reviews)",
        "specialties": [
            "Pulmonology",
            "Cardiac Care",
            "Critical Care"
        ],
        "emergency_phone": "+91 11 2651 5050",
        "icu_beds_available": "18 Beds Available",
        "distance": "3.9 km away"
    },
    {
        "id": "DEL-4",
        "name": "Indraprastha Apollo Hospitals, Sarita Vihar",
        "city": "Delhi",
        "location": "Delhi Mathura Road, Sarita Vihar, New Delhi",
        "lat": 28.5398,
        "lon": 77.2831,
        "rating": "4.8 \u2b50 (16,700+ Reviews)",
        "specialties": [
            "Emergency Trauma",
            "Cardiology",
            "Organ Transplant"
        ],
        "emergency_phone": "+91 11 2692 5858",
        "icu_beds_available": "20 Beds Available",
        "distance": "5.1 km away"
    },
    {
        "id": "MAA-1",
        "name": "Apollo Main Hospital, Greams Road",
        "city": "Chennai",
        "location": "21 Greams Lane, Thousand Lights, Greams Road, Chennai",
        "lat": 13.0577,
        "lon": 80.2514,
        "rating": "4.9 \u2b50 (24,000+ Reviews)",
        "specialties": [
            "Cardiology",
            "Pulmonology",
            "Emergency Trauma"
        ],
        "emergency_phone": "+91 44 2829 0200",
        "icu_beds_available": "26 Beds Available",
        "distance": "1.9 km away"
    },
    {
        "id": "MAA-2",
        "name": "MIOT International, Manapakkam",
        "city": "Chennai",
        "location": "4/112, Mount Poonamallee High Rd, Manapakkam, Chennai",
        "lat": 13.0232,
        "lon": 80.1772,
        "rating": "4.8 \u2b50 (13,800+ Reviews)",
        "specialties": [
            "Orthopedics",
            "Pulmonary Critical Care",
            "ICU"
        ],
        "emergency_phone": "+91 44 4200 2288",
        "icu_beds_available": "16 Beds Available",
        "distance": "4.2 km away"
    },
    {
        "id": "MAA-3",
        "name": "Fortis Malar Hospital, Adyar",
        "city": "Chennai",
        "location": "52, 1st Main Rd, Gandhi Nagar, Adyar, Chennai",
        "lat": 13.0067,
        "lon": 80.2573,
        "rating": "4.7 \u2b50 (11,000+ Reviews)",
        "specialties": [
            "Cardio-Thoracic",
            "Vascular Surgery",
            "Emergency"
        ],
        "emergency_phone": "+91 44 4289 2222",
        "icu_beds_available": "10 Beds Available",
        "distance": "3.1 km away"
    },
    {
        "id": "PNQ-1",
        "name": "Ruby Hall Clinic, Sassoon Road",
        "city": "Pune",
        "location": "40, Sassoon Road, Sangamvadi, Pune",
        "lat": 18.5312,
        "lon": 73.877,
        "rating": "4.8 \u2b50 (15,200+ Reviews)",
        "specialties": [
            "Cardiology",
            "Pulmonology",
            "Emergency Trauma"
        ],
        "emergency_phone": "+91 20 6645 5100",
        "icu_beds_available": "19 Beds Available",
        "distance": "2.2 km away"
    },
    {
        "id": "PNQ-2",
        "name": "Jupiter Hospital, Baner",
        "city": "Pune",
        "location": "Near Prathamesh Park, Aundh-Baner Link Road, Baner, Pune",
        "lat": 18.5583,
        "lon": 73.7885,
        "rating": "4.9 \u2b50 (10,400+ Reviews)",
        "specialties": [
            "Critical Care",
            "Neurology",
            "Pulmonary Rehab"
        ],
        "emergency_phone": "+91 20 2799 2222",
        "icu_beds_available": "14 Beds Available",
        "distance": "3.8 km away"
    },
    {
        "id": "CCU-1",
        "name": "Apollo Multispeciality Hospitals, Canal Circular",
        "city": "Kolkata",
        "location": "58, Canal Circular Road, Kadapara, Kankurgachi, Kolkata",
        "lat": 22.5768,
        "lon": 88.4014,
        "rating": "4.8 \u2b50 (18,900+ Reviews)",
        "specialties": [
            "Cardiac Sciences",
            "Pulmonology",
            "Emergency ICU"
        ],
        "emergency_phone": "+91 33 2320 3040",
        "icu_beds_available": "21 Beds Available",
        "distance": "2.7 km away"
    },
    {
        "id": "CCU-2",
        "name": "Fortis Hospital, Anandapur, EM Bypass",
        "city": "Kolkata",
        "location": "730, Anandapur, EM Bypass Road, Kolkata",
        "lat": 22.5186,
        "lon": 88.4035,
        "rating": "4.8 \u2b50 (14,500+ Reviews)",
        "specialties": [
            "Emergency Care",
            "Pulmonology",
            "Cardiology"
        ],
        "emergency_phone": "+91 33 6628 4444",
        "icu_beds_available": "16 Beds Available",
        "distance": "3.9 km away"
    },
    {
        "id": "AP-1",
        "name": "Apollo Hospitals, Ramnagar, Visakhapatnam",
        "city": "Visakhapatnam",
        "location": "Waltair Main Road, Ramnagar, Visakhapatnam, AP",
        "lat": 17.7214,
        "lon": 83.3106,
        "rating": "4.9 \u2b50 (9,400+ Reviews)",
        "specialties": [
            "Cardiology",
            "Pulmonology",
            "Trauma ICU"
        ],
        "emergency_phone": "+91 891 272 7272",
        "icu_beds_available": "15 Beds Available",
        "distance": "1.9 km away"
    },
    {
        "id": "AP-2",
        "name": "Care Hospitals, Maharani Peta, Vizag",
        "city": "Visakhapatnam",
        "location": "AS Raja Complex, Waltair Main Rd, Maharani Peta, Visakhapatnam",
        "lat": 17.7088,
        "lon": 83.3031,
        "rating": "4.8 \u2b50 (7,800+ Reviews)",
        "specialties": [
            "Critical Care",
            "Cardiology",
            "Chest Medicine"
        ],
        "emergency_phone": "+91 891 304 1444",
        "icu_beds_available": "11 Beds Available",
        "distance": "2.8 km away"
    },
    {
        "id": "AP-3",
        "name": "Manipal Hospital, Tadepalli, Vijayawada",
        "city": "Vijayawada",
        "location": "Near Kanaka Durga Varadhi, Tadepalli, Vijayawada, AP",
        "lat": 16.4883,
        "lon": 80.6072,
        "rating": "4.8 \u2b50 (8,900+ Reviews)",
        "specialties": [
            "Emergency Trauma",
            "Pulmonology",
            "Cardiology"
        ],
        "emergency_phone": "+91 866 676 7777",
        "icu_beds_available": "14 Beds Available",
        "distance": "2.5 km away"
    },
    {
        "id": "AP-4",
        "name": "Ramesh Hospitals, Collectorate Road, Guntur/Vijayawada",
        "city": "Vijayawada",
        "location": "Beside Hindu College Grounds, Collectorate Road, Guntur/Vijayawada",
        "lat": 16.5185,
        "lon": 80.6433,
        "rating": "4.9 \u2b50 (12,300+ Reviews)",
        "specialties": [
            "Cardiac ICU",
            "Pulmonology",
            "Critical Care"
        ],
        "emergency_phone": "+91 863 237 7777",
        "icu_beds_available": "18 Beds Available",
        "distance": "3.7 km away"
    },
    {
        "id": "AMD-1",
        "name": "Apollo Hospitals, Gandhinagar / Ahmedabad",
        "city": "Ahmedabad",
        "location": "Plot No. 1A, Bhat GIDC Estate, Gandhinagar/Ahmedabad",
        "lat": 23.1118,
        "lon": 72.6321,
        "rating": "4.9 \u2b50 (16,200+ Reviews)",
        "specialties": [
            "Cardiology",
            "Pulmonology",
            "Emergency ICU"
        ],
        "emergency_phone": "+91 79 6670 1800",
        "icu_beds_available": "20 Beds Available",
        "distance": "3.1 km away"
    },
    {
        "id": "AMD-2",
        "name": "Zydus Hospital, Thaltej, SG Highway",
        "city": "Ahmedabad",
        "location": "Zydus Hospitals Road, SG Highway, Thaltej, Ahmedabad",
        "lat": 23.0583,
        "lon": 72.5074,
        "rating": "4.8 \u2b50 (14,100+ Reviews)",
        "specialties": [
            "Critical Care",
            "Pulmonology",
            "Heart Transplant"
        ],
        "emergency_phone": "+91 79 6619 0201",
        "icu_beds_available": "17 Beds Available",
        "distance": "3.9 km away"
    }
]

# Prescription OCR & Decrypted Medication Knowledge Base
SAMPLE_PRESCRIPTION_DATA = {
    "doctor_name": "Dr. K. S. Rao, MD, FCCP",
    "doctor_reg": "Reg No. APMC/48921/2008",
    "clinic_name": "Apollo Health City — Dept of Pulmonology & Critical Care",
    "date": "2026-03-09",
    "patient_name": "Hemanth Kumar",
    "rx_code": "RX-2026-9041A",
    "diagnosis": "Acute Bacterial Bronchitis with Reactive Airway Spasm",
    "medications": [
        {
            "drug_name": "Augmentin 625 Duo Tablet",
            "composition": "Amoxicillin 500mg + Potassium Clavulanate 125mg",
            "class": "Broad-Spectrum Penicillin Antibiotic",
            "dosage": "1 Tablet Twice Daily",
            "schedule": {
                "morning": "1 Tab (8:00 AM)",
                "afternoon": "—",
                "night": "1 Tab (8:00 PM)",
                "meal_relation": "Immediately After Meals"
            },
            "duration": "6 Days remaining (Total 7 days)",
            "purpose": "Eliminates bacterial pathogens in bronchial airways and stops secondary infection.",
            "precaution": "Must complete full 7-day course even if feeling 100% cured. Take with food to protect stomach.",
            "generic_alternative": "Moxikind-CV 625 (Mankind) or Clavam 625 (Alkem) — Saves ~40% cost."
        },
        {
            "drug_name": "Ascoril-LS Syrup",
            "composition": "Levosalbutamol 1mg + Ambroxol 30mg + Guaiphenesin 50mg (per 5ml)",
            "class": "Bronchodilator & Mucolytic Expectorant",
            "dosage": "10 ml Three Times Daily",
            "schedule": {
                "morning": "10 ml (8:30 AM)",
                "afternoon": "10 ml (2:00 PM)",
                "night": "10 ml (8:30 PM)",
                "meal_relation": "After Food with warm water"
            },
            "duration": "5 Days",
            "purpose": "Thins thick bronchial mucus and dilates airways for effortless breathing.",
            "precaution": "May cause mild temporary hand shakiness or mild heart rate bump. Avoid cold drinks.",
            "generic_alternative": "Kofrest-LS Syrup (Centaur) or Bro-Zedex LS — Saves ~35% cost."
        },
        {
            "drug_name": "Montair-LC Tablet",
            "composition": "Montelukast 10mg + Levocetirizine Dihydrochloride 5mg",
            "class": "Leukotriene Receptor Antagonist & Antihistaminic",
            "dosage": "1 Tablet Once Daily",
            "schedule": {
                "morning": "—",
                "afternoon": "—",
                "night": "1 Tab (9:30 PM at bedtime)",
                "meal_relation": "After Dinner before sleeping"
            },
            "duration": "10 Days",
            "purpose": "Blocks nocturnal allergic cough triggers, wheezing, and throat tickle while resting.",
            "precaution": "Causes mild drowsiness. Avoid driving or heavy machinery right after taking.",
            "generic_alternative": "Telekast-L (Lupin) or Romilast-L (Sun Pharma) — Saves ~30% cost."
        },
        {
            "drug_name": "Pan-D Capsule",
            "composition": "Pantoprazole 40mg + Domperidone 30mg (Sustained Release)",
            "class": "Proton Pump Inhibitor (PPI) & Prokinetic",
            "dosage": "1 Capsule Once Daily",
            "schedule": {
                "morning": "1 Cap (7:00 AM)",
                "afternoon": "—",
                "night": "—",
                "meal_relation": "30 to 45 mins BEFORE Breakfast (Empty Stomach)"
            },
            "duration": "7 Days",
            "purpose": "Shields stomach lining from antibiotic-induced gastritis, nausea, and acid reflux.",
            "precaution": "Must take with a full glass of plain water at least 30 minutes before first meal.",
            "generic_alternative": "Pantocid-DSR (Sun Pharma) or Pantosec-DSR — Saves ~25% cost."
        }
    ]
}

# Pulse Shield Medical Knowledge Base (for deep, accurate chatbot answers)
DRUG_PHARMACOLOGY_KB = {
    "augmentin": {
        "name": "Augmentin 625 Duo (Amoxicillin + Potassium Clavulanate)",
        "why_used": "It is a potent broad-spectrum antibiotic used to destroy bacterial infections in your respiratory tract (lungs, bronchitis, sinusitis). Amoxicillin attacks and ruptures bacterial cell walls, while Clavulanic Acid inhibits bacterial enzymes that resist penicillin, ensuring 100% bacterial kill.",
        "dosage": "1 Tablet twice daily (Morning & Night) immediately AFTER food.",
        "precaution": "Complete the full prescribed 7-day course even if fever or cough disappears. Stopping early causes bacterial resistance! Take with meals to prevent stomach upset.",
        "te": "Augmentin 625 అనేది శక్తివంతమైన యాంటీబయాటిక్. ఇది మీ ఊపిరితిత్తులు మరియు శ్వాసనాళాల్లోని హానికర బ్యాక్టీరియాను పూర్తిగా నిర్మూలిస్తుంది. దీనిని ఉదయం మరియు రాత్రి భోజనం తిన్న వెంటనే వేసుకోవాలి. కోర్సు మధ్యలో ఆపకూడదు.",
        "hi": "Augmentin 625 एक असरदार एंटीबायोटिक है जिसका उपयोग फेफड़ों और ब्रोन्काइटिस के बैक्टीरिया को मारने के लिए किया जाता है। इसे सुबह और रात खाना खाने के तुरंत बाद लें और 7 दिन का पूरा कोर्स अवश्य खत्म करें।",
        "ta": "Augmentin 625 என்பது சக்திவாய்ந்த பாக்டீரியா எதிர்ப்பு மருந்து (Antibiotic). இது உங்கள் நுரையீரலில் உள்ள பாக்டீரியா தொற்றை அழிக்கிறது. இதை காலை மற்றும் இரவு உணவுக்குப் பிறகு உட்கொள்ளவும்."
    },
    "pan-d": {
        "name": "Pan-D Capsule (Pantoprazole 40mg + Domperidone 30mg)",
        "why_used": "It is prescribed as a gastric protective shield. Heavy antibiotics like Augmentin can cause intense stomach acid, nausea, reflux, and gastritis. Pantoprazole stops excess gastric acid production, while Domperidone prevents vomiting and speeds up stomach emptying.",
        "dosage": "1 Capsule once daily in the MORNING, exactly 30 to 45 minutes BEFORE breakfast on an empty stomach with a full glass of water.",
        "precaution": "Do not chew or crush the capsule; swallow it whole.",
        "te": "Pan-D క్యాప్సూల్ కడుపులో గ్యాస్ మరియు ఎసిడిటీ రాకుండా కాపాడుతుంది. యాంటీబయాటిక్స్ వేసుకున్నప్పుడు కడుపులో మంట, వికారం రాకుండా ఇది అడ్డుకుంటుంది. దీనిని ఉదయం పూట బ్రేక్‌ఫాస్ట్‌కి 30 నిమిషాల ముందు ఖాళీ కడుపుతో మాత్రమే వేసుకోవాలి.",
        "hi": "Pan-D पेट में गैस, जलन और एसिडिटी को रोकता है। एंटीबायोटिक दवाओं से पेट खराब न हो, इसलिए इसे सुबह नाश्ते से 30-45 मिनट पहले खाली पेट एक गिलास पानी के साथ लेना अनिवार्य है।",
        "ta": "Pan-D என்பது நெஞ்செரிச்சல் மற்றும் வாயுத் தொல்லையைத் தடுக்கும் மருந்து. ஆன்டிபயாடிக் மருந்துகள் வயிற்றைப் புண்ணாக்காமல் இருக்க இதை காலை உணவுக்கு 30 நிமிடங்களுக்கு முன் வெறும் வயிற்றில் உட்கொள்ள வேண்டும்."
    },
    "ascoril": {
        "name": "Ascoril-LS Syrup (Levosalbutamol + Ambroxol + Guaiphenesin)",
        "why_used": "It is a triple-action cough expectorant and bronchodilator. Ambroxol thins and liquefies sticky phlegm; Guaiphenesin increases airway secretions to help cough out mucus easily; Levosalbutamol opens constricted airways so you can breathe freely without wheezing.",
        "dosage": "10 ml three times daily (Morning, Afternoon, Night) with warm water after food.",
        "precaution": "Do not drink refrigerated cold water. May cause mild temporary hand tremors in sensitive patients.",
        "te": "Ascoril-LS సిరప్ ఛాతీలోని దట్టమైన కఫాన్ని (తెమడను) పల్చబరిచి సులభంగా బయటకు వచ్చేలా చేస్తుంది మరియు శ్వాసనాళాలను వెడల్పు చేసి శ్వాస తేలికగా అందేలా చేస్తుంది. రోజుకు 3 సార్లు 10ml గోరువెచ్చని నీటితో తాగాలి.",
        "hi": "Ascoril-LS सिरप छाती में जमे गाढ़े बलगम को पतला करके बाहर निकालता है और सांस की नलियों को खोलता है ताकि सांस लेने में तकलीफ न हो। इसे दिन में 3 बार 10ml गुनगुने पानी के साथ लें।",
        "ta": "Ascoril-LS சிரப் நெஞ்சில் கட்டியுள்ள சளியை இளக்கி வெளியேற்றுகிறது மற்றும் மூச்சுக்குழாய்களை விரிவடையச் செய்து எளிதாக சுவாசிக்க உதவுகிறது. தினமும் 3 வேளை 10 மி.லி உட்கொள்ளவும்."
    },
    "montair": {
        "name": "Montair-LC (Montelukast 10mg + Levocetirizine 5mg)",
        "why_used": "It is an anti-allergic airway relaxant. It stops histamine and leukotrienes—inflammatory chemicals that cause throat tickling, nighttime coughing fits, sneezing, and bronchial allergy spasms while lying down.",
        "dosage": "1 Tablet once daily at NIGHT right before going to bed.",
        "precaution": "Causes mild drowsiness. Do not drive or operate machinery immediately after taking.",
        "te": "Montair-LC అనేది రాత్రిపూట వచ్చే దగ్గు మరియు శ్వాస ఆయాసాన్ని ఆపడానికి వేసుకునే అలర్జీ నివారణ మాత్ర. దీనిని రాత్రి పడుకునే ముందు మాత్రమే వేసుకోవాలి (కొద్దిగా నిద్రమత్తు రావచ్చు).",
        "hi": "Montair-LC रात में होने वाली एलर्जी, खांसी और घरघराहट को रोकता है। इसे केवल रात को सोने से पहले 1 गोली लें क्योंकि इससे हल्की नींद आ सकती है।",
        "ta": "Montair-LC மாத்திரை இரவில் ஏற்படும் ஒவ்வாமை மற்றும் இருமல் தொல்லையைத் தடுக்கிறது. இதை இரவு தூங்குவதற்கு முன் ஒரு மாத்திரை உட்கொள்ள வேண்டும்."
    },
    "dolo": {
        "name": "Dolo 650mg (Paracetamol / Acetaminophen)",
        "why_used": "It is an antipyretic and analgesic medicine used to reduce body fever and relieve headaches, muscle pain, and joint aches associated with viral or bacterial infections.",
        "dosage": "1 Tablet thrice daily after meals when fever or pain is present.",
        "precaution": "Do not exceed 3-4 tablets in 24 hours. Safe on stomach when taken with food.",
        "te": "Dolo 650 అనేది జ్వరం తగ్గించడానికి మరియు ఒంటి నొప్పులు, తలనొప్పి తగ్గించడానికి వేసుకునే సురక్షితమైన మాత్ర. భోజనం తర్వాత వేసుకోవాలి.",
        "hi": "Dolo 650 बुखार कम करने और सिरदर्द व बदन दर्द से राहत पाने के लिए उपयोग की जाती है। खाना खाने के बाद इसे लें।",
        "ta": "Dolo 650 என்பது காய்ச்சல் மற்றும் உடல் வலியை குறைக்கும் மாத்திரை. உணவுக்குப் பின் உட்கொள்ளவும்."
    }
}

# Multilingual AI Knowledge Base
MULTILINGUAL_TRANSLATIONS = {
    "te": {
        "lang_name": "Telugu (తెలుగు)",
        "welcome": "నమస్కారం! నేను మీ Pulse Shield AI వైద్య సహాయకుడిని.\nమీరు మీ మందుల వివరాలు, రికవరీ సమయం లేదా రక్త పరీక్షల గురించి నన్ను అడగవచ్చు.",
        "rx_summary": "డాక్టర్ కె. ఎస్. రావు గారు మీకు 4 రకాల మందులు సూచించారు: యాంటీబయాటిక్ (Augmentin 625), దగ్గు సిరప్ (Ascoril-LS), అలర్జీ నివారణ మాత్ర (Montair-LC), మరియు గ్యాస్ట్రిక్ మాత్ర (Pan-D).",
        "instructions": [
            "1. Pan-D: ఉదయం పూట బ్రేక్‌ఫాస్ట్‌కి 30 నిమిషాల ముందు ఖాళీ కడుపుతో ఒక టాబ్లెట్ వేసుకోవాలి.",
            "2. Augmentin 625: ఉదయం మరియు రాత్రి భోజనం తిన్న వెంటనే వేసుకోవాలి. కోర్సు పూర్తి అయ్యేవరకు ఆపకూడదు.",
            "3. Ascoril-LS Syrup: రోజుకు 3 సార్లు (ఉదయం, మధ్యాహ్నం, రాత్రి) 10ml గోరువెచ్చని నీటితో తీసుకోవాలి.",
            "4. Montair-LC: రాత్రి పడుకునే ముందు మాత్రమే ఒక మాత్ర వేసుకోవాలి (కొద్దిగా నిద్రమత్తు రావచ్చు)."
        ],
        "recovery_advice": "మీ ఊపిరితిత్తుల ఇన్ఫెక్షన్ 10 రోజుల్లో పూర్తిగా నయమవుతుంది. గోరువెచ్చని నీరు మాత్రమే త్రాగండి, ఆవిరి పట్టండి, చల్లని పదార్ధాలు తినవద్దు."
    },
    "hi": {
        "lang_name": "Hindi (हिन्दी)",
        "welcome": "नमस्ते! Pulse Shield AI मेडिकल असिस्टेंट में आपका स्वागत है।",
        "rx_summary": "डॉ. के. एस. राव ने आपके ब्रोन्काइटिस के इलाज के लिए 4 दवाइयां दी हैं: एंटीबायोटिक (Augmentin), कफ सिरप (Ascoril-LS), एलर्जी निवारक (Montair-LC), और गैस की गोली (Pan-D)।",
        "instructions": [
            "1. Pan-D: सुबह नाश्ते से 30 मिनट पहले खाली पेट एक कैप्सूल पानी के साथ लें।",
            "2. Augmentin 625: सुबह और रात खाना खाने के तुरंत बाद लें। 7 दिन का पूरा कोर्स अवश्य पूरा करें।",
            "3. Ascoril-LS Syrup: दिन में 3 बार 10ml गुनगुने पानी के साथ पिएं, इससे बलगम आसानी से निकलेगा।",
            "4. Montair-LC: रात को सोने से पहले 1 गोली लें (इससे हल्की नींद आ सकती है)।"
        ],
        "recovery_advice": "आपकी बीमारी 10 दिनों में पूरी तरह ठीक होने का अनुमान है। ठंडी चीजों से परहेज करें और नियमित भाप लें।"
    },
    "ta": {
        "lang_name": "Tamil (தமிழ்)",
        "welcome": "வணக்கம்! Pulse Shield AI மருத்துவ உதவி மையத்திற்கு வரவேற்கிறோம்.",
        "rx_summary": "மருத்துவர் கே. எஸ். ராவ் உங்கள் மூச்சுக்குழாய் அழற்சிக்கு 4 மருந்துகளை பரிந்துரைத்துள்ளார்: ஆன்டிபயாடிக், இருமல் சிரப், ஒவ்வாமை எதிர்ப்பு மாத்திரை மற்றும் வாயு நிவாரணி.",
        "instructions": [
            "1. Pan-D: காலை உணவுக்கு 30 நிமிடங்களுக்கு முன் வெறும் வயிற்றில் உட்கொள்ளவும்.",
            "2. Augmentin 625: காலை மற்றும் இரவு உணவுக்குப் பிறகு உடனடியாக ஒரு மாத்திரை எடுக்கவும்.",
            "3. Ascoril-LS Syrup: தினமும் 3 வேளை 10 மி.லி வெதுவெதுப்பான நீரில் அருந்தவும்.",
            "4. Montair-LC: இரவு படுக்கைக்கு செல்லும் முன் ஒரு மாத்திரை உட்கொள்ளவும்."
        ],
        "recovery_advice": "இன்னும் 10 நாட்களில் நீங்கள் பூரண குணம் அடைவீர்கள். சுடுநீர் அருந்தவும் மற்றும் நீராவி பிடிக்கவும்."
    },
    "en": {
        "lang_name": "English",
        "welcome": "Hello! Welcome to Pulse Shield Multilingual Clinical AI.",
        "rx_summary": "Dr. K. S. Rao prescribed 4 core medications for Acute Bronchitis: Antibiotic (Augmentin 625), Expectorant (Ascoril-LS), Anti-allergic (Montair-LC), and Gastro-protective (Pan-D).",
        "instructions": [
            "1. Pan-D: Take 1 capsule 30-45 mins before breakfast on an empty stomach with water.",
            "2. Augmentin 625: Take 1 tablet twice daily immediately after morning & night meals.",
            "3. Ascoril-LS: Take 10ml thrice daily after meals with warm water to clear airway mucus.",
            "4. Montair-LC: Take 1 tablet at night before sleeping to eliminate nighttime coughing."
        ],
        "recovery_advice": "Estimated full recovery in 10 remaining days. Maintain warm fluid hydration, perform steam inhalation twice daily, and avoid refrigerated beverages."
    }
}

# --- Pydantic Models ---
class SendOTPRequest(BaseModel):
    phone: Optional[str] = None
    email: Optional[str] = None
    channel: str = "sms"

class VerifyOTPRequest(BaseModel):
    phone: Optional[str] = None
    email: Optional[str] = None
    channel: str = "sms"
    otp: str
    name: Optional[str] = None


class RegisterRequest(BaseModel):
    name: str
    email: Optional[str] = None
    phone: Optional[str] = None
    dob: Optional[str] = None
    gender: Optional[str] = None
    blood_group: Optional[str] = None
    emergency_contact: Optional[str] = None
    hospital: Optional[str] = None
    allergies: Optional[List[str]] = None
    chronic_conditions: Optional[List[str]] = None
    address: Optional[str] = None
    password: Optional[str] = None

class GoogleLoginRequest(BaseModel):
    email: str
    name: str
    avatar: Optional[str] = None

class ChatRequest(BaseModel):
    message: str
    language: str = "en"
    context: Optional[str] = None

class VitalsScanRecordRequest(BaseModel):
    temperature: Optional[str] = "98.6 °F"
    blood_pressure: Optional[str] = "118/76"
    pulse: Optional[str] = "72 bpm"
    spo2: Optional[str] = "99%"
    scan_target: str = "forehead"

class ManualVitalsRequest(BaseModel):
    temperature: str
    blood_pressure: str
    pulse: str
    spo2: str
    blood_sugar: Optional[str] = "98 mg/dL"

class ManualReportRequest(BaseModel):
    title: str
    category: str
    date: Optional[str] = None
    notes: Optional[str] = ""

class ManualPrescriptionRequest(BaseModel):
    drug_name: str
    composition: str
    dosage: str
    morning: bool = False
    afternoon: bool = False
    night: bool = False
    meal_relation: str = "After Food"
    purpose: str = ""
    generic_alternative: str = ""

class ManualDiseaseRequest(BaseModel):
    disease_name: str
    symptoms: str
    severity: str = "Moderate"
    duration_days: Optional[int] = 14

class SelectHospitalRequest(BaseModel):
    hospital_name: str
    hospital_id: Optional[str] = None


# ==========================================
# API Endpoints
# ==========================================

@app.get("/", response_class=HTMLResponse)
async def serve_portal(request: Request):
    return templates.TemplateResponse("index.html", {
        "request": request,
        "app_name": "Pulse Shield",
        "user": DEFAULT_USER,
        "past_records": PAST_HEALTH_REPORTS,
        "lan_ip": get_lan_ip()
    })


# --- Dedicated Standalone Public Emergency Page (For Phone QR Scanners) ---
@app.get("/emergency/{health_id}", response_class=HTMLResponse)
async def serve_emergency_page(request: Request, health_id: str):
    """
    When an EMT, doctor, or paramedic points their camera at the QR code,
    this standalone responsive medical page opens immediately with zero auth required.
    """
    return templates.TemplateResponse("emergency.html", {
        "request": request,
        "app_name": "Pulse Shield — Emergency Responder View",
        "user": DEFAULT_USER,
        "vitals": CURRENT_VITALS,
        "current_records": MOCK_RECORDS,
        "past_records": PAST_HEALTH_REPORTS,
        "medications": SAMPLE_PRESCRIPTION_DATA.get("medications", []),
        "condition": HEALTH_ISSUE_DATA,
        "lan_ip": get_lan_ip()
    })


@app.get("/api/tunnel-status")
async def get_tunnel_status():
    state_file = os.path.join(os.path.dirname(__file__), "tunnel_state.json")
    if os.path.exists(state_file):
        try:
            with open(state_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    lan_ip = get_lan_ip()
    return {
        "active": False,
        "url": None,
        "lan_ip": lan_ip,
        "local_url": f"http://{lan_ip}:8000"
    }


# --- Authentication Endpoints ---
@app.post("/api/auth/send-otp")
async def send_otp(payload: SendOTPRequest):
    channel = payload.channel.lower()
    
    if channel == "gmail":
        identifier = (payload.email or "").strip()
        if not identifier or "@" not in identifier:
            raise HTTPException(status_code=400, detail="Please enter a valid Gmail address.")
        channel_label = f"Gmail inbox ({identifier})"
    elif channel == "whatsapp":
        identifier = (payload.phone or "").strip()
        if not identifier or len(identifier) < 8:
            raise HTTPException(status_code=400, detail="Please enter a valid WhatsApp mobile number.")
        channel_label = f"WhatsApp (+91 {identifier})"
    else:
        identifier = (payload.phone or "").strip()
        if not identifier or len(identifier) < 8:
            raise HTTPException(status_code=400, detail="Please enter a valid mobile number.")
        channel_label = f"SMS (+91 {identifier})"

    generated_otp = f"{hash(identifier + channel) % 900000 + 100000:06d}"
    PENDING_OTPS[identifier] = {
        "otp": generated_otp,
        "channel": channel,
        "timestamp": time.time()
    }
    
    return {
        "status": "success",
        "channel": channel,
        "message": f"Verification code dispatched via {channel_label}",
        "demo_otp": generated_otp,
        "backup_otp": "123456"
    }


@app.post("/api/auth/verify-otp")
async def verify_otp(payload: VerifyOTPRequest):
    identifier = (payload.email if payload.channel == "gmail" else payload.phone or "").strip()
    entered_otp = payload.otp.strip()
    
    record = PENDING_OTPS.get(identifier)
    valid_otps = {"123456", "849201"}
    if record:
        valid_otps.add(record["otp"])
    
    if entered_otp not in valid_otps:
        raise HTTPException(status_code=400, detail="Invalid OTP code. Please try again or use the demo code shown.")
    
    session_user = dict(DEFAULT_USER)
    if payload.phone:
        session_user["phone"] = f"+91 {payload.phone}"
    if payload.email:
        session_user["email"] = payload.email
    if payload.name and payload.name.strip():
        session_user["name"] = payload.name.strip()
        session_user["health_id"] = generate_unique_health_id(session_user["name"])
        DEFAULT_USER["name"] = session_user["name"]
        DEFAULT_USER["health_id"] = session_user["health_id"]
    
    token = str(uuid.uuid4())
    ACTIVE_SESSIONS[token] = session_user
    
    return {
        "status": "success",
        "message": f"Welcome, {session_user['name']}! Accessing your Health Command Center.",
        "token": token,
        "user": session_user
    }



@app.post("/api/auth/register")
async def register_user(payload: RegisterRequest):
    safe_name = payload.name.strip()
    if not safe_name:
        raise HTTPException(status_code=400, detail="Full Name is required for registration.")
    
    session_user = dict(DEFAULT_USER)
    session_user["name"] = safe_name
    session_user["health_id"] = generate_unique_health_id(safe_name)
    if payload.email:
        session_user["email"] = payload.email.strip()
    if payload.phone:
        session_user["phone"] = payload.phone.strip()
    if payload.dob:
        session_user["dob"] = payload.dob
    if payload.gender:
        session_user["gender"] = payload.gender
    if payload.blood_group:
        session_user["blood_group"] = payload.blood_group
    if payload.emergency_contact:
        session_user["emergency_contact"] = payload.emergency_contact
    if payload.hospital:
        session_user["hospital"] = payload.hospital
    if payload.allergies:
        session_user["allergies"] = payload.allergies
    if payload.chronic_conditions:
        session_user["chronic_conditions"] = payload.chronic_conditions
    if payload.address:
        session_user["address"] = payload.address

    DEFAULT_USER.update(session_user)
    token = str(uuid.uuid4())
    ACTIVE_SESSIONS[token] = session_user

    return {
        "status": "success",
        "message": f"Profile registered successfully for {safe_name}! Generated Health ID: {session_user['health_id']}",
        "token": token,
        "user": session_user
    }

@app.post("/api/auth/google")
async def google_login_alias(payload: GoogleLoginRequest):
    return await google_login(payload)

@app.post("/api/auth/google-login")
async def google_login(payload: GoogleLoginRequest):
    email = payload.email.strip()
    if not email or "@" not in email:
        raise HTTPException(status_code=400, detail="Invalid Google account email.")
    
    session_user = dict(DEFAULT_USER)
    session_user["email"] = email
    session_user["name"] = payload.name or email.split("@")[0].replace(".", " ").title()
    session_user["health_id"] = generate_unique_health_id(session_user["name"])
    DEFAULT_USER["name"] = session_user["name"]
    DEFAULT_USER["health_id"] = session_user["health_id"]
    if payload.avatar:
        session_user["avatar"] = payload.avatar
    
    token = str(uuid.uuid4())
    ACTIVE_SESSIONS[token] = session_user
    
    return {
        "status": "success",
        "message": f"Authenticated with Google as {session_user['name']}",
        "token": token,
        "user": session_user
    }


# --- User Profile & Emergency QR Scan Endpoints ---
@app.get("/api/user/profile")
async def get_user_profile():
    return {"user": DEFAULT_USER}


@app.post("/api/user/profile")
async def update_user_profile(payload: dict):
    if "name" in payload and payload["name"].strip():
        DEFAULT_USER["name"] = payload["name"].strip()
        DEFAULT_USER["health_id"] = generate_unique_health_id(DEFAULT_USER["name"])
    return {"status": "success", "user": DEFAULT_USER}


@app.get("/api/daily-quote")
async def get_daily_quote():
    idx = int(time.time() / 86400) % len(DAILY_HEALTH_QUOTES)
    return {"quote": DAILY_HEALTH_QUOTES[idx], "all_quotes": DAILY_HEALTH_QUOTES}


@app.get("/api/public/emergency-report/{health_id}")
async def get_emergency_report(health_id: str):
    return {
        "status": "active",
        "verified_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S IST"),
        "patient": {
            "health_id": DEFAULT_USER["health_id"],
            "name": DEFAULT_USER["name"],
            "age": DEFAULT_USER["age"],
            "gender": DEFAULT_USER["gender"],
            "phone": DEFAULT_USER["phone"],
            "address": DEFAULT_USER["address"],
            "blood_group": DEFAULT_USER["blood_group"],
            "organ_donor": DEFAULT_USER["organ_donor"],
            "emergency_contact": DEFAULT_USER["emergency_contact"],
            "primary_physician": DEFAULT_USER["primary_physician"],
            "hospital": DEFAULT_USER["hospital"],
            "allergies": DEFAULT_USER["allergies"],
            "chronic_conditions": DEFAULT_USER["chronic_conditions"],
            "active_medications": [m["drug_name"] + " (" + m["dosage"] + ")" for m in SAMPLE_PRESCRIPTION_DATA["medications"]],
            "stored_reports": [{"title": r["title"], "category": r["category"], "date": r["date"], "status": r["doctor_status"]} for r in MOCK_RECORDS],
            "current_health_reports": MOCK_RECORDS,
            "past_health_reports": PAST_HEALTH_REPORTS,
            "insurance": {
                "provider": DEFAULT_USER["insurance_provider"],
                "policy_no": DEFAULT_USER["policy_no"],
                "tpa_claim_tollfree": "1800-425-2255"
            },
            "latest_vitals": CURRENT_VITALS
        }
    }


@app.get("/api/records/past")
async def get_past_health_records():
    return {"status": "success", "past_records": PAST_HEALTH_REPORTS}


# --- Dashboard Monthly Vitals & Chart Data ---
@app.get("/api/dashboard/vitals")
async def get_dashboard_vitals():
    return {
        "health_score": 94,
        "health_status": "Optimal Recovery Track",
        "current_vitals": CURRENT_VITALS,
        "monthly_trend": {
            "months": ["Oct 2025", "Nov 2025", "Dec 2025", "Jan 2026", "Feb 2026", "Mar 2026"],
            "systolic_bp": [132, 128, 124, 122, 120, 118],
            "diastolic_bp": [86, 84, 82, 80, 78, 76],
            "fasting_glucose": [128, 122, 115, 108, 102, 98],
            "spo2_levels": [96, 97, 97, 98, 98, 99],
            "adherence_percentage": [82, 85, 90, 94, 95, 96]
        },
        "health_distribution": {
            "labels": [
                "Vitals Stability",
                "Medication Adherence",
                "Cardiopulmonary Fitness",
                "Nutrition & Diet Index",
                "Rest & Sleep Quality"
            ],
            "values": [30, 25, 20, 15, 10],
            "colors": ["#6366f1", "#10b981", "#06b6d4", "#f59e0b", "#ec4899"]
        }
    }


# --- Dynamic Camera Bio-Scan Vitals Record ---
@app.post("/api/vitals/scan-record")
async def record_scanned_vitals(payload: VitalsScanRecordRequest):
    if payload.temperature:
        CURRENT_VITALS["temperature"] = payload.temperature
    if payload.blood_pressure:
        CURRENT_VITALS["blood_pressure"] = payload.blood_pressure
    if payload.pulse:
        CURRENT_VITALS["pulse"] = payload.pulse
    if payload.spo2:
        CURRENT_VITALS["spo2"] = payload.spo2
    CURRENT_VITALS["last_scanned_at"] = f"Just now ({payload.scan_target.title()} Optical Scan)"

    return {
        "status": "success",
        "message": f"Biometric vitals successfully captured via camera {payload.scan_target} scan.",
        "vitals": CURRENT_VITALS,
        "health_score": 94
    }


# --- Manual Vitals Entry Endpoint ---
@app.post("/api/vitals/manual")
async def save_manual_vitals(payload: ManualVitalsRequest):
    CURRENT_VITALS["temperature"] = payload.temperature
    CURRENT_VITALS["blood_pressure"] = payload.blood_pressure
    CURRENT_VITALS["pulse"] = payload.pulse
    CURRENT_VITALS["spo2"] = payload.spo2
    if payload.blood_sugar:
        CURRENT_VITALS["blood_sugar"] = payload.blood_sugar
    CURRENT_VITALS["last_scanned_at"] = f"Manual Entry ({datetime.now().strftime('%I:%M %p')})"

    return {
        "status": "success",
        "message": "Vitals successfully updated manually.",
        "vitals": CURRENT_VITALS,
        "health_score": 95
    }


# --- Medical Records Vault, Upload & Manual Entry ---
@app.get("/api/records")
async def list_records():
    return {"records": MOCK_RECORDS}


@app.post("/api/records/upload")
async def upload_record(
    file: UploadFile = File(...),
    title: str = Form(""),
    category: str = Form("General Medical Report"),
    notes: Optional[str] = Form("")
):
    file_id = f"REC-{len(MOCK_RECORDS) + 101}"
    safe_filename = f"{uuid.uuid4().hex[:8]}_{file.filename}"
    file_path = UPLOAD_DIR / safe_filename
    
    contents = await file.read()
    with open(file_path, "wb") as f:
        f.write(contents)
    
    file_size_kb = max(1, len(contents) // 1024)
    file_url = f"/uploads/{safe_filename}"
    
    new_record = {
        "id": file_id,
        "title": title.strip() or file.filename,
        "file_name": file.filename,
        "file_url": file_url,
        "file_type": file.content_type or "application/pdf",
        "size_kb": file_size_kb,
        "category": category,
        "date": datetime.now().strftime("%Y-%m-%d"),
        "doctor_status": "Pending Review",
        "doctor_name": "Attending Physician Desk",
        "doctor_notes": notes or "Uploaded by patient. Awaiting clinical audit.",
        "key_metrics": {
            "Document Format": file.content_type or "Clinical Scan",
            "Upload Timestamp": datetime.now().strftime("%I:%M %p, %d %b %Y")
        }
    }
    
    MOCK_RECORDS.insert(0, new_record)
    return {"status": "success", "message": "Document uploaded to secure medical vault.", "record": new_record}


@app.post("/api/records/manual")
async def add_manual_record(payload: ManualReportRequest):
    file_id = f"REC-{len(MOCK_RECORDS) + 101}"
    new_record = {
        "id": file_id,
        "title": payload.title.strip(),
        "file_name": f"{payload.title.replace(' ', '_')}.pdf",
        "file_url": "https://images.unsplash.com/photo-1579154204601-01588f351e67?auto=format&fit=crop&w=800&q=80",
        "file_type": "application/pdf",
        "size_kb": 128,
        "category": payload.category,
        "date": payload.date or datetime.now().strftime("%Y-%m-%d"),
        "doctor_status": "Pending Review",
        "doctor_name": "Attending Physician Desk",
        "doctor_notes": payload.notes or "Manually entered report data by patient.",
        "key_metrics": {
            "Entry Type": "Patient Self-Reported",
            "Clinical Notes": payload.notes
        }
    }
    MOCK_RECORDS.insert(0, new_record)
    return {"status": "success", "message": "Report entry added successfully.", "record": new_record}


@app.get("/api/records/{record_id}")
async def get_single_record(record_id: str):
    record = next((r for r in MOCK_RECORDS if r["id"] == record_id), None)
    if not record:
        raise HTTPException(status_code=404, detail="Medical document not found.")
    return {"record": record}


@app.get("/api/doctor/records")
async def get_doctor_records():
    return {
        "physician": {
            "name": "Dr. K. S. Rao, MD, FCCP",
            "department": "Pulmonology & Critical Care Medicine",
            "hospital": DEFAULT_USER["hospital"],
            "license": "APMC-48921"
        },
        "records": MOCK_RECORDS
    }


@app.post("/api/doctor/verify-record/{record_id}")
async def verify_record(record_id: str):
    record = next((r for r in MOCK_RECORDS if r["id"] == record_id), None)
    if not record:
        raise HTTPException(status_code=404, detail="Medical document not found.")
    
    record["doctor_status"] = "Verified"
    record["doctor_name"] = "Dr. K. S. Rao, MD (Signed Off)"
    record["doctor_notes"] = f"Clinically audited and confirmed valid by Dr. K. S. Rao on {datetime.now().strftime('%b %d, %Y')}."
    return {"status": "success", "record": record}


# --- Disease Diagnosis, Manual Addition & Doctor Recommendation ---
@app.get("/api/health-condition")
async def get_health_condition():
    return HEALTH_ISSUE_DATA


@app.post("/api/health-condition/manual")
async def add_manual_disease(payload: ManualDiseaseRequest):
    d_name = payload.disease_name.strip()
    severity = payload.severity
    symptoms = payload.symptoms
    
    # Intelligent Specialty & Doctor Recommendation Mapping
    d_lower = d_name.lower() + " " + symptoms.lower()
    
    if any(k in d_lower for k in ["heart", "cardio", "chest pain", "angina", "bp", "hypertension", "palpitation"]):
        specialty = "Interventional Cardiologist"
        doc_name = "Dr. Ramesh Gupta, MD, DM (Cardio)"
        exp = "22 Years Experience"
        why = "Super-specialist in blood pressure regulation, cardiac rhythm, and coronary diagnostics."
        days = 21
        tests = [
            {"name": "ECG (12-Lead)", "clinical_reason": "Evaluate electrical cardiac conduction", "sample_type": "Electrophysiology", "fasting_required": "No", "target_range": "Normal Sinus", "urgency": "High", "status": "Recommended"},
            {"name": "Lipid Profile & hs-CRP", "clinical_reason": "Check cholesterol & vascular inflammation", "sample_type": "Venous Blood", "fasting_required": "12 Hours Fasting", "target_range": "Cholesterol < 200 mg/dL", "urgency": "High", "status": "Recommended"}
        ]
    elif any(k in d_lower for k in ["lung", "cough", "bronchitis", "asthma", "breath", "wheez", "pneumonia", "respiratory", "phlegm"]):
        specialty = "Pulmonologist / Chest Physician"
        doc_name = "Dr. K. S. Rao, MD, FCCP"
        exp = "18 Years Experience"
        why = "Specializes in airway obstruction, pulmonary infection, and respiratory disease recovery."
        days = payload.duration_days or 14
        tests = [
            {"name": "Complete Blood Count (CBC)", "clinical_reason": "Verify infection markers", "sample_type": "Blood", "fasting_required": "No", "target_range": "WBC 4,500 - 11,000", "urgency": "High", "status": "Recommended"},
            {"name": "Chest X-Ray / Spirometry", "clinical_reason": "Assess lung expansion", "sample_type": "Imaging", "fasting_required": "No", "target_range": "Normal", "urgency": "High", "status": "Recommended"}
        ]
    elif any(k in d_lower for k in ["diabetes", "sugar", "thyroid", "endocrine", "hormone", "weight"]):
        specialty = "Endocrinologist & Diabetologist"
        doc_name = "Dr. Sunita Reddy, MD, DM (Endo)"
        exp = "15 Years Experience"
        why = "Specialist in metabolic stabilization, glycemic control, and hormonal balance."
        days = 30
        tests = [
            {"name": "HbA1c & Fasting Glucose", "clinical_reason": "Measure 3-month average blood glucose", "sample_type": "Venous Blood", "fasting_required": "10 Hours Fasting", "target_range": "HbA1c < 6.5%", "urgency": "High", "status": "Recommended"},
            {"name": "Thyroid Profile (TSH, Free T4)", "clinical_reason": "Quantify metabolic hormonal activity", "sample_type": "Serum", "fasting_required": "Morning sample", "target_range": "TSH 0.4 - 4.0 mIU/L", "urgency": "Medium", "status": "Recommended"}
        ]
    elif any(k in d_lower for k in ["bone", "joint", "knee", "back pain", "arthritis", "fracture"]):
        specialty = "Orthopedic Surgeon & Rheumatologist"
        doc_name = "Dr. Vikram Prasad, MS (Ortho), MCh"
        exp = "19 Years Experience"
        why = "Expert in musculoskeletal repair, joint inflammation reduction, and rehabilitation therapy."
        days = 28
        tests = [
            {"name": "Serum Uric Acid & ESR", "clinical_reason": "Rule out gout and joint inflammation", "sample_type": "Blood", "fasting_required": "No", "target_range": "Uric Acid < 6.0 mg/dL", "urgency": "High", "status": "Recommended"},
            {"name": "Vitamin D3 & Calcium", "clinical_reason": "Assess bone mineral density support", "sample_type": "Venous Blood", "fasting_required": "No", "target_range": "> 30 ng/mL", "urgency": "Medium", "status": "Recommended"}
        ]
    elif any(k in d_lower for k in ["skin", "rash", "itching", "allergy", "dermatitis"]):
        specialty = "Dermatologist & Allergy Specialist"
        doc_name = "Dr. Priya Rao, MD (Dermatology)"
        exp = "12 Years Experience"
        why = "Specializes in cutaneous allergic reactions, eczema, and dermato-pharmacology."
        days = 10
        tests = [
            {"name": "Absolute Eosinophil Count (AEC)", "clinical_reason": "Determine allergic systemic response", "sample_type": "Blood", "fasting_required": "No", "target_range": "< 350 /mcL", "urgency": "High", "status": "Recommended"}
        ]
    else:
        specialty = "Consultant Physician & Internal Medicine"
        doc_name = "Dr. P. Naidu, MD (Internal Medicine)"
        exp = "16 Years Experience"
        why = "Specializes in multi-system diagnosis, infectious fever control, and holistic recovery."
        days = 14
        tests = [
            {"name": "Complete Blood Count & ESR", "clinical_reason": "General infectious profile", "sample_type": "Blood", "fasting_required": "No", "target_range": "Normal", "urgency": "High", "status": "Recommended"}
        ]

    # Update state
    HEALTH_ISSUE_DATA["condition_name"] = d_name
    HEALTH_ISSUE_DATA["severity"] = severity
    HEALTH_ISSUE_DATA["total_estimated_days"] = days
    HEALTH_ISSUE_DATA["days_elapsed"] = 1
    HEALTH_ISSUE_DATA["days_remaining"] = days - 1
    HEALTH_ISSUE_DATA["recovery_percentage"] = 15
    HEALTH_ISSUE_DATA["recommended_doctor"] = {
        "specialty": specialty,
        "recommended_doctor_name": doc_name,
        "experience": exp,
        "department": f"Department of {specialty.split('/')[0].strip()}",
        "why_recommended": why
    }
    HEALTH_ISSUE_DATA["recommended_blood_tests"] = tests
    HEALTH_ISSUE_DATA["milestones"] = [
        {"phase": "Phase 1: Initial Diagnosis & Symptom Stabilization", "day_range": f"Day 1 - {max(2, days//4)}", "status": "Current", "description": f"Targeting {symptoms}. Primary medical therapy initiated."},
        {"phase": "Phase 2: Therapeutic Response & Tissue Recovery", "day_range": f"Day {days//4 + 1} - {days//2}", "status": "Upcoming", "description": "Inflammation subsiding, vital biomarkers stabilizing."},
        {"phase": "Phase 3: Clinical Normalization & Functional Recovery", "day_range": f"Day {days//2 + 1} - {days - 2}", "status": "Upcoming", "description": "Zero active acute symptoms. Energy and tolerance restored."},
        {"phase": "Phase 4: Full Medical Remission & Discharge", "day_range": f"Day {days - 1} - {days}", "status": "Upcoming", "description": "Full physiological recovery confirmed by physician."}
    ]

    return {"status": "success", "message": "Disease entered and clinical care plan customized.", "data": HEALTH_ISSUE_DATA}


# --- Hospitals Directory & Selection Endpoints ---
@app.get("/api/hospitals")
async def get_nearby_hospitals(location: Optional[str] = "Banjara Hills, Hyderabad"):
    return {
        "current_location": location,
        "hospitals": NEARBY_HOSPITALS_DATABASE
    }


@app.post("/api/user/select-hospital")
async def select_hospital(payload: SelectHospitalRequest):
    h_name = payload.hospital_name.strip()
    target = next((h for h in NEARBY_HOSPITALS_DATABASE if h["name"] == h_name or h["id"] == payload.hospital_id), None)
    
    for h in NEARBY_HOSPITALS_DATABASE:
        h["is_selected"] = (h["name"] == h_name)
    
    DEFAULT_USER["hospital"] = h_name
    return {
        "status": "success",
        "message": f"Primary Care Hospital set to {h_name}.",
        "hospital": target,
        "user": DEFAULT_USER
    }


# --- Doctor Prescription Scanner & Manual Entry ---
@app.get("/api/prescription/sample")
async def get_sample_prescription():
    return SAMPLE_PRESCRIPTION_DATA


@app.post("/api/prescription/scan")
async def scan_prescription(file: Optional[UploadFile] = File(None)):
    time.sleep(0.6)
    return {
        "status": "success",
        "extracted_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "prescription": SAMPLE_PRESCRIPTION_DATA
    }


@app.post("/api/prescription/manual")
async def add_manual_prescription(payload: ManualPrescriptionRequest):
    morning_str = "1 Tab" if payload.morning else "—"
    afternoon_str = "1 Tab" if payload.afternoon else "—"
    night_str = "1 Tab" if payload.night else "—"
    
    new_med = {
        "drug_name": payload.drug_name.strip(),
        "composition": payload.composition.strip() or payload.drug_name,
        "class": "Prescribed Medication",
        "dosage": payload.dosage.strip(),
        "schedule": {
            "morning": morning_str,
            "afternoon": afternoon_str,
            "night": night_str,
            "meal_relation": payload.meal_relation
        },
        "duration": "7 Days",
        "purpose": payload.purpose or "Symptomatic relief and therapeutic cure.",
        "precaution": "Take as directed by doctor. Keep hydrated.",
        "generic_alternative": payload.generic_alternative or f"Generic equivalent for {payload.drug_name}"
    }
    
    SAMPLE_PRESCRIPTION_DATA["medications"].insert(0, new_med)
    return {"status": "success", "message": "Medication added manually.", "medication": new_med, "all": SAMPLE_PRESCRIPTION_DATA}


# --- Multilingual AI Chatbot & Medical Guidance Engine ---
@app.post("/api/chat")
async def medical_chat(payload: ChatRequest):
    lang = payload.language.lower() if payload.language in MULTILINGUAL_TRANSLATIONS else "en"
    trans = MULTILINGUAL_TRANSLATIONS[lang]
    msg = payload.message.lower()
    
    # 1. SPECIFIC DRUG & TABLET PHARMACOLOGY LOOKUP (Addresses user complaint)
    matched_drug = None
    for drug_key, drug_info in DRUG_PHARMACOLOGY_KB.items():
        if drug_key in msg or any(part.lower() in msg for part in drug_info["name"].lower().split()):
            matched_drug = drug_info
            break
            
    if matched_drug:
        if lang in matched_drug:
            return {
                "status": "success",
                "language": lang,
                "language_display": trans["lang_name"],
                "reply": f"💊 **{matched_drug['name']}**\n\n{matched_drug[lang]}\n\n• **Dosage:** {matched_drug['dosage']}\n• **Precaution:** {matched_drug['precaution']}"
            }
        else:
            return {
                "status": "success",
                "language": lang,
                "language_display": trans["lang_name"],
                "reply": f"💊 **Clinical Purpose of {matched_drug['name']}:**\n\n**Why it is used:**\n{matched_drug['why_used']}\n\n• **Recommended Timing:** {matched_drug['dosage']}\n• **Crucial Safety Precaution:** {matched_drug['precaution']}"
            }
    
    # 2. GENERAL "WHY IS THIS TABLET USED?" QUERY
    if any(k in msg for k in ["why this tablet", "why tablet", "why medicine", "tablet used for", "medicine used for", "ఈ మందు ఎందుకు", "దవా ఎందుకు", "दवाई क्यों", "மருந்து எதற்கு"]):
        if lang == "te":
            reply = (
                "💊 **మీ ప్రిస్క్రిప్షన్‌లోని మందులు ఎందుకు వాడాలి (వివరణ):**\n\n"
                "1. **Augmentin 625 Duo:** ఇది శక్తివంతమైన యాంటీబయాటిక్. మీ ఊపిరితిత్తులలోని బ్యాక్టీరియల్ ఇన్ఫెక్షన్‌ను పూర్తిగా అంతం చేయడానికి వాడతారు. భోజనం తిన్న వెంటనే వేసుకోవాలి.\n\n"
                "2. **Pan-D:** యాంటీబయాటిక్స్ వల్ల కడుపులో ఎసిడిటీ, గ్యాస్, లేదా వికారం రాకుండా ఉండటానికి ఉదయం బ్రేక్‌ఫాస్ట్‌కి 30 నిమిషాల ముందు ఖాళీ కడుపుతో వేసుకోవాలి.\n\n"
                "3. **Ascoril-LS Syrup:** ఛాతీలోని దట్టమైన కఫాన్ని కరిగించి, శ్వాసనాళాలు తెరుచుకునేలా చేసి సులభంగా శ్వాస ఆడేలా చేస్తుంది.\n\n"
                "4. **Montair-LC:** రాత్రిపూట వచ్చే దగ్గు మరియు అలర్జీని ఆపి ప్రశాంతంగా నిద్ర పట్టేలా చేస్తుంది."
            )
        elif lang == "hi":
            reply = (
                "💊 **आपकी दवाईयां किस काम आती हैं (पूरी जानकारी):**\n\n"
                "1. **Augmentin 625 Duo:** यह फेफड़ों के बैक्टीरियल इन्फेक्शन को जड़ से खत्म करने वाली एंटीबायोटिक है। इसे खाने के तुरंत बाद लें।\n\n"
                "2. **Pan-D:** एंटीबायोटिक से पेट में गैस या जलन न हो, इसलिए इसे सुबह नाश्ते से 30 मिनट पहले खाली पेट लिया जाता है।\n\n"
                "3. **Ascoril-LS Syrup:** यह बलगम को पतला कर बाहर निकालता है और सांस की नली खोलता है।\n\n"
                "4. **Montair-LC:** रात में खांसी और एलर्जी को रोकने के लिए सोते समय ली जाती है।"
            )
        elif lang == "ta":
            reply = (
                "💊 **உங்கள் மருந்துகள் எதற்காகப் பயன்படுத்தப்படுகின்றன:**\n\n"
                "1. **Augmentin 625 Duo:** நுரையீரலில் உள்ள பாக்டீரியா தொற்றை முழுமையாக அழிக்க உதவும் ஆன்டிபயாடிக்.\n\n"
                "2. **Pan-D:** மருந்துகளால் நெஞ்செரிச்சல் மற்றும் வாயு ஏற்படாமல் தடுக்க வெறும் வயிற்றில் எடுக்க வேண்டும்.\n\n"
                "3. **Ascoril-LS சிரப்:** சளியை இளக்கி எளிதாக வெளியேற்றி மூச்சுவிட உதவுகிறது.\n\n"
                "4. **Montair-LC:** இரவு நேர இருமல் மற்றும் ஒவ்வாமையை கட்டுப்படுத்துகிறது."
            )
        else:
            reply = (
                "💊 **Clinical Purpose of Your Prescribed Medications:**\n\n"
                "1. **Augmentin 625 Duo:** Targeted broad-spectrum antibiotic that eradicates bacterial pathogens causing acute bronchitis. Take twice daily immediately after meals.\n\n"
                "2. **Pan-D Capsule:** Gastro-protective proton-pump inhibitor that shields your stomach lining from antibiotic-induced hyperacidity. Take 30 mins before breakfast on an empty stomach.\n\n"
                "3. **Ascoril-LS Syrup:** Mucolytic bronchodilator that thins thick mucus secretions and opens airway passages for effortless breathing.\n\n"
                "4. **Montair-LC Tablet:** Leukotriene receptor blocker that prevents nocturnal cough spasms and airway hyper-reactivity at night."
            )
        return {"status": "success", "language": lang, "language_display": trans["lang_name"], "reply": reply}

    # 3. OTHER INTENTS
    if any(k in msg for k in ["recovery", "days", "disease", "when", "ఎన్ని రోజులు", "రోజు", "कितने दिन", "दिन", "எத்தனை நாள்"]):
        answer = f"**{trans['lang_name']} Recovery Forecast:**\n\n{trans['recovery_advice']}\n\n• Estimated Remaining Time: **10 Days** (Day 4 of 14).\n• Current Status: Phase 2 (Bronchial Decongestion)."
    elif any(k in msg for k in ["test", "blood test", "రక్త పరీక్ష", "खून जांच", "பரிசோதனை", "blood"]):
        if lang == "te":
            answer = "**సిఫార్సు చేయబడిన రక్త పరీక్షలు:**\n1. **Complete Blood Count (CBC):** తెల్ల రక్త కణాలు సాధారణ స్థాయికి వస్తున్నాయో లేదో చూస్తుంది.\n2. **hs-CRP:** ఊపిరితిత్తుల్లో ఇన్ఫెక్షన్ తీవ్రతను కొలుస్తుంది.\n3. **Sputum Culture:** యాంటీబయాటిక్ పనిచేస్తోందో లేదో నిర్ధారిస్తుంది."
        elif lang == "hi":
            answer = "**सुझाई गई जरूरी खून जांच:**\n1. **CBC:** संक्रमण नियंत्रण देखने के लिए।\n2. **hs-CRP:** सूजन के स्तर को मापने के लिए।\n3. **Sputum Culture:** एंटीबायोटिक असर की पुष्टि के लिए।"
        elif lang == "ta":
            answer = "**பரிந்துரைக்கப்பட்ட இரத்த பரிசோதனைகள்:**\n1. **CBC பரிசோதனை:** இரத்த வெள்ளை அணுக்களின் அளவை அறிய.\n2. **hs-CRP பரிசோதனை:** அழற்சி அளவை கணக்கிட.\n3. **சளி பரிசோதனை:** மருந்து சரியாக வேலை செய்கிறதா என சோதிக்க."
        else:
            answer = "**Recommended Blood & Diagnostic Panels:**\n1. **Complete Blood Count (CBC):** Tracks normalization of white blood cells.\n2. **hs-CRP:** Quantifies pulmonary inflammation markers.\n3. **Sputum Culture:** Verifies bacterial eradication."
    else:
        answer = f"{trans['welcome']}\n\n{trans['rx_summary']}\n\n" + "\n".join(trans["instructions"][:2]) + f"\n\n💡 *Health Note:* {trans['recovery_advice']}"

    return {
        "status": "success",
        "language": lang,
        "language_display": trans["lang_name"],
        "reply": answer
    }
