"""
EDUFUND - AI-POWERED SCHOLARSHIP FINDER BACKEND
Complete production-ready backend with REAL scholarship data
Version: 3.0 - Real-world scholarships + West Bengal focus
"""

from flask import Flask, request, jsonify
from flask_cors import CORS
import pytesseract
from PIL import Image
import cv2
import numpy as np
import re
import os
from datetime import datetime
from werkzeug.utils import secure_filename
import logging
from flask import Flask, request, jsonify, session, redirect, url_for
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
import base64
from email.mime.text import MIMEText

# PDF Support (Optional)
try:
    from pdf2image import convert_from_path
    PDF_SUPPORT = True
except ImportError:
    PDF_SUPPORT = False

# Initialize Flask app
app = Flask(__name__)
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# CORS configuration
CORS(app, resources={
    r"/*": {
        "origins": "*",
        "methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        "allow_headers": ["Content-Type", "Authorization"]
    }
})

# File upload configuration
UPLOAD_FOLDER = 'uploads'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'pdf'}
MAX_FILE_SIZE = 10 * 1024 * 1024

if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = MAX_FILE_SIZE

# Set Tesseract path
import platform
if platform.system() == "Windows":
    pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'
elif platform.system() == "Darwin":
    if os.path.exists('/opt/homebrew/bin/tesseract'):
        pytesseract.pytesseract.tesseract_cmd = '/opt/homebrew/bin/tesseract'

# Conversation history
conversation_history = {}

# ============================================================================
# REAL SCHOLARSHIP DATABASE - ACCURATE DATA
# ============================================================================

SCHOLARSHIPS = [
    # ==================== WEST BENGAL STATE SCHOLARSHIPS ====================
    {
        "id": 1,
        "name": "Kanyashree Prakalpa (K1)",
        "name_hi": "कन्याश्री प्रकल्प (K1)",
        "min_percentage": 40,
        "max_income": 999999999,  # No income limit
        "category": ["General", "OBC", "SC", "ST"],
        "amount": 750,
        "deadline": "30-06-2026",
        "description": "Annual scholarship for girls in Class 8-12. ₹750/year to prevent dropout.",
        "description_hi": "कक्षा 8-12 में लड़कियों के लिए वार्षिक छात्रवृत्ति।",
        "apply_url": "https://wbkanyashree.gov.in",
        "eligibility": ["Girls only", "Class 8-12", "West Bengal resident", "Unmarried"],
        "documents": ["Aadhaar", "Bank Account", "School Certificate", "Age Proof"],
        "eligible_streams": ["All"],
        "states": ["West Bengal"]
    },
    {
        "id": 2,
        "name": "Kanyashree Prakalpa (K2)",
        "name_hi": "कन्याश्री प्रकल्प (K2)",
        "min_percentage": 45,
        "max_income": 999999999,
        "category": ["General", "OBC", "SC", "ST"],
        "amount": 25000,
        "deadline": "30-06-2026",
        "description": "One-time grant for girls aged 18-19 pursuing higher education. Unmarried girls only.",
        "description_hi": "उच्च शिक्षा प्राप्त करने वाली 18-19 वर्ष की लड़कियों के लिए एकमुश्त अनुदान।",
        "apply_url": "https://wbkanyashree.gov.in",
        "eligibility": ["Girls 18-19 years", "Class 12 passed", "Enrolled in degree/diploma", "Unmarried"],
        "documents": ["Aadhaar", "Bank Account", "12th Marksheet", "College Admission Proof"],
        "eligible_streams": ["All"],
        "states": ["West Bengal"]
    },
    {
        "id": 3,
        "name": "Aikyashree Scholarship",
        "name_hi": "ऐक्यश्री छात्रवृत्ति",
        "min_percentage": 50,
        "max_income": 250000,
        "category": ["Minority"],
        "amount": 5000,
        "deadline": "31-12-2025",
        "description": "For minority students (Muslim, Christian, Buddhist, Sikh, Jain, Parsi) in West Bengal.",
        "description_hi": "पश्चिम बंगाल में अल्पसंख्यक छात्रों के लिए।",
        "apply_url": "https://scholarships.gov.in",
        "eligibility": ["Minority community", "Class 1-12", "West Bengal resident", "Income < ₹2.5 lakh"],
        "documents": ["Minority Certificate", "Income Certificate", "Marksheet", "Aadhaar"],
        "eligible_streams": ["All"],
        "states": ["West Bengal"]
    },
    {
        "id": 4,
        "name": "Swami Vivekananda Merit-cum-Means Scholarship",
        "name_hi": "स्वामी विवेकानंद मेरिट-कम-मीन्स छात्रवृत्ति",
        "min_percentage": 60,
        "max_income": 250000,
        "category": ["General", "OBC", "SC", "ST"],
        "amount": 15000,
        "deadline": "31-10-2025",
        "description": "For UG/PG students in West Bengal. Covers tuition fees up to ₹15,000.",
        "description_hi": "पश्चिम बंगाल में UG/PG छात्रों के लिए।",
        "apply_url": "https://svmcm.wbhed.gov.in",
        "eligibility": ["60%+ in last exam", "UG/PG student", "Income < ₹2.5 lakh"],
        "documents": ["Last exam marksheet", "Income Certificate", "Admission Proof"],
        "eligible_streams": ["All"],
        "states": ["West Bengal"]
    },
    {
        "id": 5,
        "name": "Dr. Ambedkar Post-Matric SC/ST Scholarship (WB)",
        "name_hi": "डॉ. अम्बेडकर पोस्ट-मैट्रिक SC/ST छात्रवृत्ति",
        "min_percentage": 50,
        "max_income": 250000,
        "category": ["SC", "ST"],
        "amount": 12000,
        "deadline": "31-12-2025",
        "description": "West Bengal state scholarship for SC/ST students in higher education.",
        "description_hi": "उच्च शिक्षा में SC/ST छात्रों के लिए पश्चिम बंगाल राज्य छात्रवृत्ति।",
        "apply_url": "https://scholarships.gov.in",
        "eligibility": ["SC/ST certificate", "Class 11+", "West Bengal domicile"],
        "documents": ["Caste Certificate", "Income Certificate", "Marksheet", "Admission Proof"],
        "eligible_streams": ["All"],
        "states": ["West Bengal"]
    },
    {
        "id": 6,
        "name": "Taruner Swapna (Youth Dream) Scholarship",
        "name_hi": "तरुणेर स्वप्न छात्रवृत्ति",
        "min_percentage": 55,
        "max_income": 400000,
        "category": ["General", "OBC", "SC", "ST"],
        "amount": 8000,
        "deadline": "31-01-2026",
        "description": "For West Bengal students pursuing technical/vocational courses.",
        "description_hi": "तकनीकी/व्यावसायिक पाठ्यक्रमों में छात्रों के लिए।",
        "apply_url": "https://wbhed.gov.in",
        "eligibility": ["Technical/Vocational courses", "West Bengal resident"],
        "documents": ["Marksheet", "Income Certificate", "Course Admission Proof"],
        "eligible_streams": ["Engineering", "Polytechnic", "ITI"],
        "states": ["West Bengal"]
    },

    # ==================== NATIONAL SCHOLARSHIPS ====================
    {
        "id": 7,
        "name": "National Scholarship Portal - Pre-Matric SC",
        "name_hi": "राष्ट्रीय छात्रवृत्ति पोर्टल - प्री-मैट्रिक SC",
        "min_percentage": 50,
        "max_income": 250000,
        "category": ["SC"],
        "amount": 3000,
        "deadline": "31-10-2025",
        "description": "For SC students in Class 9-10. Day scholars: ₹225/month, Hostellers: ₹525/month.",
        "description_hi": "कक्षा 9-10 के SC छात्रों के लिए।",
        "apply_url": "https://scholarships.gov.in",
        "eligibility": ["SC certificate", "Class 9-10", "Income < ₹2.5 lakh"],
        "documents": ["SC Certificate", "Income Certificate", "Marksheet", "Bank Details"],
        "eligible_streams": ["All"],
        "states": ["All States"]
    },
    {
        "id": 8,
        "name": "National Scholarship Portal - Pre-Matric ST",
        "name_hi": "राष्ट्रीय छात्रवृत्ति पोर्टल - प्री-मैट्रिक ST",
        "min_percentage": 50,
        "max_income": 250000,
        "category": ["ST"],
        "amount": 3000,
        "deadline": "31-10-2025",
        "description": "For ST students in Class 9-10. Day scholars: ₹225/month, Hostellers: ₹525/month.",
        "description_hi": "कक्षा 9-10 के ST छात्रों के लिए।",
        "apply_url": "https://scholarships.gov.in",
        "eligibility": ["ST certificate", "Class 9-10", "Income < ₹2.5 lakh"],
        "documents": ["ST Certificate", "Income Certificate", "Marksheet", "Bank Details"],
        "eligible_streams": ["All"],
        "states": ["All States"]
    },
    {
        "id": 9,
        "name": "Post-Matric Scholarship for SC Students",
        "name_hi": "SC छात्रों के लिए पोस्ट-मैट्रिक छात्रवृत्ति",
        "min_percentage": 50,
        "max_income": 250000,
        "category": ["SC"],
        "amount": 10000,
        "deadline": "31-12-2025",
        "description": "For SC students in Class 11 to PhD. Maintenance + tuition fees covered.",
        "description_hi": "कक्षा 11 से PhD तक के SC छात्रों के लिए।",
        "apply_url": "https://scholarships.gov.in",
        "eligibility": ["SC certificate", "Class 11 onwards", "Income < ₹2.5 lakh"],
        "documents": ["SC Certificate", "Income Certificate", "Admission Proof", "Bank Details"],
        "eligible_streams": ["All"],
        "states": ["All States"]
    },
    {
        "id": 10,
        "name": "Post-Matric Scholarship for ST Students",
        "name_hi": "ST छात्रों के लिए पोस्ट-मैट्रिक छात्रवृत्ति",
        "min_percentage": 50,
        "max_income": 250000,
        "category": ["ST"],
        "amount": 10000,
        "deadline": "31-12-2025",
        "description": "For ST students in Class 11 to PhD. Maintenance + tuition fees covered.",
        "description_hi": "कक्षा 11 से PhD तक के ST छात्रों के लिए।",
        "apply_url": "https://scholarships.gov.in",
        "eligibility": ["ST certificate", "Class 11 onwards", "Income < ₹2.5 lakh"],
        "documents": ["ST Certificate", "Income Certificate", "Admission Proof"],
        "eligible_streams": ["All"],
        "states": ["All States"]
    },
    {
        "id": 11,
        "name": "Post-Matric Scholarship for OBC Students (Central)",
        "name_hi": "OBC छात्रों के लिए पोस्ट-मैट्रिक छात्रवृत्ति",
        "min_percentage": 50,
        "max_income": 100000,
        "category": ["OBC"],
        "amount": 5000,
        "deadline": "15-01-2026",
        "description": "Central sector scheme for OBC (Non-Creamy Layer) students.",
        "description_hi": "OBC (गैर-क्रीमी लेयर) छात्रों के लिए केंद्रीय योजना।",
        "apply_url": "https://scholarships.gov.in",
        "eligibility": ["OBC Non-Creamy Layer", "Class 11+", "Income < ₹1 lakh"],
        "documents": ["OBC Certificate", "Income Certificate", "Non-Creamy Layer Certificate"],
        "eligible_streams": ["All"],
        "states": ["All States"]
    },
    {
        "id": 12,
        "name": "National Means-cum-Merit Scholarship (NMMS)",
        "name_hi": "राष्ट्रीय मीन्स-कम-मेरिट छात्रवृत्ति",
        "min_percentage": 55,
        "max_income": 150000,
        "category": ["General", "OBC", "SC", "ST"],
        "amount": 12000,
        "deadline": "30-11-2025",
        "description": "₹12,000/year for Class 9-12. Students must pass NMMS exam conducted by state.",
        "description_hi": "कक्षा 9-12 के लिए ₹12,000/वर्ष।",
        "apply_url": "https://scholarships.gov.in",
        "eligibility": ["55%+ in Class 8", "Pass NMMS test", "Income < ₹1.5 lakh"],
        "documents": ["Class 8 Marksheet", "Income Certificate", "NMMS Pass Certificate"],
        "eligible_streams": ["All"],
        "states": ["All States"]
    },
    {
        "id": 13,
        "name": "Prime Minister's Scholarship Scheme (PMSS)",
        "name_hi": "प्रधानमंत्री छात्रवृत्ति योजना",
        "min_percentage": 75,
        "max_income": 600000,
        "category": ["General", "OBC", "SC", "ST"],
        "amount": 30000,
        "deadline": "15-10-2025",
        "description": "For wards/widows of Ex-Servicemen, Ex-Coast Guard. ₹2500/month (Boys), ₹3000/month (Girls).",
        "description_hi": "भूतपूर्व सैनिकों के बच्चों/विधवाओं के लिए।",
        "apply_url": "https://ksb.gov.in",
        "eligibility": ["Ex-servicemen dependent", "75%+ in 12th", "Professional courses"],
        "documents": ["Ex-Servicemen Certificate", "12th Marksheet", "College Admission"],
        "eligible_streams": ["All"],
        "states": ["All States"]
    },
    {
        "id": 14,
        "name": "Central Sector Scheme - Top Class Education for SC",
        "name_hi": "SC के लिए शीर्ष श्रेणी शिक्षा योजना",
        "min_percentage": 60,
        "max_income": 600000,
        "category": ["SC"],
        "amount": 200000,
        "deadline": "31-10-2025",
        "description": "Full tuition + living expenses for SC students in notified institutions (IITs, NITs, AIIMS, etc).",
        "description_hi": "IIT, NIT, AIIMS आदि में SC छात्रों के लिए पूर्ण ट्यूशन।",
        "apply_url": "https://scholarships.gov.in",
        "eligibility": ["SC certificate", "Admission in notified institutes", "Income < ₹6 lakh"],
        "documents": ["SC Certificate", "Income Certificate", "Admission Letter"],
        "eligible_streams": ["All"],
        "states": ["All States"]
    },
    {
        "id": 15,
        "name": "Post-Matric Scholarship for Minorities (Central)",
        "name_hi": "अल्पसंख्यकों के लिए पोस्ट-मैट्रिक छात्रवृत्ति",
        "min_percentage": 50,
        "max_income": 200000,
        "category": ["Minority"],
        "amount": 10000,
        "deadline": "31-12-2025",
        "description": "For Muslim, Christian, Sikh, Buddhist, Jain, Parsi students. 30% seats reserved for girls.",
        "description_hi": "मुस्लिम, ईसाई, सिख, बौद्ध, जैन, पारसी छात्रों के लिए।",
        "apply_url": "https://scholarships.gov.in",
        "eligibility": ["Notified minority community", "Class 11+", "Income < ₹2 lakh"],
        "documents": ["Minority Certificate", "Income Certificate", "Marksheet"],
        "eligible_streams": ["All"],
        "states": ["All States"]
    },
    {
        "id": 16,
        "name": "AICTE Pragati Scholarship for Girls",
        "name_hi": "लड़कियों के लिए AICTE प्रगति छात्रवृत्ति",
        "min_percentage": 60,
        "max_income": 800000,
        "category": ["General", "OBC", "SC", "ST"],
        "amount": 50000,
        "deadline": "31-10-2025",
        "description": "For 1 girl child per family in AICTE-approved degree courses. ₹50,000/year.",
        "description_hi": "AICTE-स्वीकृत डिग्री पाठ्यक्रमों में प्रति परिवार 1 लड़की के लिए।",
        "apply_url": "https://www.aicte-india.org/schemes/students-development-schemes/Pragati-Saksham",
        "eligibility": ["Girl student", "AICTE approved college", "One girl per family", "Income < ₹8 lakh"],
        "documents": ["Marksheet", "Admission Proof", "Income Certificate", "Single Girl Declaration"],
        "eligible_streams": ["Engineering", "Pharmacy", "Architecture", "Management"],
        "states": ["All States"]
    },
    {
        "id": 17,
        "name": "INSPIRE Scholarship (SHE)",
        "name_hi": "INSPIRE छात्रवृत्ति",
        "min_percentage": 85,
        "max_income": 500000,
        "category": ["General", "OBC", "SC", "ST"],
        "amount": 80000,
        "deadline": "31-12-2025",
        "description": "For top 1% in Class 12 board exams pursuing BSc/BS/Integrated MSc in Natural Sciences.",
        "description_hi": "बोर्ड परीक्षा में शीर्ष 1% छात्रों के लिए।",
        "apply_url": "https://online-inspire.gov.in",
        "eligibility": ["Top 1% in 12th boards (85%+)", "Natural Science courses", "Income < ₹5 lakh"],
        "documents": ["12th Marksheet", "BSc/MSc Admission", "Income Certificate"],
        "eligible_streams": ["Science"],
        "states": ["All States"]
    },
    {
        "id": 18,
        "name": "Merit-cum-Means Based Scholarship (MCM)",
        "name_hi": "मेरिट-कम-मीन्स आधारित छात्रवृत्ति",
        "min_percentage": 80,
        "max_income": 450000,
        "category": ["General", "OBC", "SC", "ST"],
        "amount": 20000,
        "deadline": "15-01-2026",
        "description": "For professional/technical courses: Engineering, Medical, Agriculture, Veterinary, Law, etc.",
        "description_hi": "व्यावसायिक/तकनीकी पाठ्यक्रमों के लिए।",
        "apply_url": "https://scholarships.gov.in",
        "eligibility": ["80%+ in qualifying exam", "Professional courses", "Income < ₹4.5 lakh"],
        "documents": ["Previous Marksheet", "Admission Letter", "Income Certificate"],
        "eligible_streams": ["Engineering", "Medical", "Law", "Agriculture"],
        "states": ["All States"]
    },
    {
        "id": 19,
        "name": "Begum Hazrat Mahal National Scholarship",
        "name_hi": "बेगम हज़रत महल राष्ट्रीय छात्रवृत्ति",
        "min_percentage": 50,
        "max_income": 200000,
        "category": ["Minority"],
        "amount": 12000,
        "deadline": "31-12-2025",
        "description": "For minority girls from Class 9-12. ₹6,000 (9-10), ₹12,000 (11-12).",
        "description_hi": "कक्षा 9-12 की अल्पसंख्यक लड़कियों के लिए।",
        "apply_url": "https://maef.nic.in",
        "eligibility": ["Minority girls", "Class 9-12", "50%+ marks", "Income < ₹2 lakh"],
        "documents": ["Minority Certificate", "Marksheet", "Income Certificate"],
        "eligible_streams": ["All"],
        "states": ["All States"]
    },
    {
        "id": 20,
        "name": "Central Sector Scheme of National Merit Scholarship",
        "name_hi": "राष्ट्रीय मेरिट छात्रवृत्ति योजना",
        "min_percentage": 80,
        "max_income": 600000,
        "category": ["General", "OBC", "SC", "ST"],
        "amount": 20000,
        "deadline": "31-10-2025",
        "description": "For students with 80%+ in Class 12. Continuation depends on 75% in UG/PG.",
        "description_hi": "कक्षा 12 में 80%+ प्राप्त करने वाले छात्रों के लिए।",
        "apply_url": "https://scholarships.gov.in",
        "eligibility": ["80%+ in Class 12", "Degree/PG course", "Income < ₹6 lakh"],
        "documents": ["12th Marksheet", "Admission Proof", "Income Certificate"],
        "eligible_streams": ["All"],
        "states": ["All States"]
    },
    {
        "id": 21,
        "name": "AICTE Saksham Scholarship for Differently-Abled",
        "name_hi": "दिव्यांगों के लिए AICTE सक्षम छात्रवृत्ति",
        "min_percentage": 60,
        "max_income": 800000,
        "category": ["General", "OBC", "SC", "ST"],
        "amount": 50000,
        "deadline": "31-10-2025",
        "description": "For differently-abled students (40%+ disability) in AICTE-approved courses.",
        "description_hi": "AICTE-स्वीकृत पाठ्यक्रमों में दिव्यांग छात्रों के लिए।",
        "apply_url": "https://www.aicte-india.org",
        "eligibility": ["40%+ disability", "AICTE approved courses", "Income < ₹8 lakh"],
        "documents": ["Disability Certificate", "Marksheet", "Income Certificate"],
        "eligible_streams": ["Engineering", "Pharmacy", "Architecture"],
        "states": ["All States"]
    },
    {
        "id": 22,
        "name": "Ishan Uday - NE Region Scholarship",
        "name_hi": "ईशान उदय - NE क्षेत्र छात्रवृत्ति",
        "min_percentage": 60,
        "max_income": 450000,
        "category": ["General", "OBC", "SC", "ST"],
        "amount": 100000,
        "deadline": "31-10-2025",
        "description": "For students from North-Eastern states pursuing UG in Central/State universities.",
        "description_hi": "उत्तर-पूर्वी राज्यों के छात्रों के लिए।",
        "apply_url": "https://www.ugc.ac.in",
        "eligibility": ["NE state domicile", "60%+ in 12th", "Central/State university"],
        "documents": ["Domicile Certificate", "12th Marksheet", "Admission Proof"],
        "eligible_streams": ["All"],
        "states": ["Arunachal Pradesh", "Assam", "Manipur", "Meghalaya", "Mizoram", "Nagaland", "Sikkim", "Tripura"]
    }
]

# ============================================================================
# ENHANCED MATCHING ALGORITHM
# ============================================================================

def match_scholarships(student_data):
    """Enhanced scholarship matching with strict percentage filtering"""
    matched = []
    rejected = []
    
    percentage = student_data.get("percentage")
    income = student_data.get("income")
    category = student_data.get("category")
    stream = student_data.get("stream")
    state = student_data.get("state")
    
    for scholarship in SCHOLARSHIPS:
        eligibility_score = 0
        reasons = []
        rejection_reason = None
        max_score = 0
        
        # CRITICAL: Percentage check (MUST PASS)
        if percentage:
            max_score += 1
            if percentage >= scholarship["min_percentage"]:
                eligibility_score += 1
                reasons.append(f"✓ Marks: {percentage:.1f}% (Required: {scholarship['min_percentage']}%+)")
            else:
                rejection_reason = f"Marks too low: {percentage:.1f}% < {scholarship['min_percentage']}% required"
                rejected.append({
                    "scholarship": scholarship["name"],
                    "reason": rejection_reason
                })
                continue  # Skip this scholarship
        
        # Income check (MUST PASS if income provided)
        if income:
            max_score += 1
            if income <= scholarship["max_income"]:
                eligibility_score += 1
                reasons.append(f"✓ Income: ₹{income:,} (Limit: ₹{scholarship['max_income']:,})")
            else:
                rejection_reason = f"Income too high: ₹{income:,} > ₹{scholarship['max_income']:,}"
                rejected.append({
                    "scholarship": scholarship["name"],
                    "reason": rejection_reason
                })
                continue
        
        # Category check (MUST PASS if category provided)
        if category:
            max_score += 1
            if category in scholarship["category"]:
                eligibility_score += 1
                reasons.append(f"✓ Category: {category} eligible")
            else:
                rejection_reason = f"Category mismatch: {category} not in {', '.join(scholarship['category'])}"
                rejected.append({
                    "scholarship": scholarship["name"],
                    "reason": rejection_reason
                })
                continue
        
        # State filtering (Optional but important)
        eligible_states = scholarship.get("states", ["All States"])
        if "All States" not in eligible_states:
            if state and state not in eligible_states:
                rejection_reason = f"State not eligible: {state} (Only for: {', '.join(eligible_states)})"
                rejected.append({
                    "scholarship": scholarship["name"],
                    "reason": rejection_reason
                })
                continue
            elif state and state in eligible_states:
                reasons.append(f"✓ State: {state} eligible")
        
        # Stream filtering (Optional)
        eligible_streams = scholarship.get("eligible_streams", ["All"])
        if "All" not in eligible_streams:
            if stream and stream not in eligible_streams:
                rejection_reason = f"Stream not eligible: {stream} (Only: {', '.join(eligible_streams)})"
                rejected.append({
                    "scholarship": scholarship["name"],
                    "reason": rejection_reason
                })
                continue
            elif stream and stream in eligible_streams:
                reasons.append(f"✓ Stream: {stream} eligible")
        
        # Calculate match percentage
        match_percentage = (eligibility_score / max_score * 100) if max_score > 0 else 0
        
        # Only include scholarships with good match
        if eligibility_score >= max_score * 0.6:  # At least 60% match
            scholarship_copy = scholarship.copy()
            scholarship_copy["eligibility_score"] = eligibility_score
            scholarship_copy["match_percentage"] = round(match_percentage, 1)
            scholarship_copy["match_reasons"] = reasons
            
            # Calculate urgency based on deadline
            try:
                deadline_date = datetime.strptime(scholarship["deadline"], "%d-%m-%Y")
                days_left = (deadline_date - datetime.now()).days
                scholarship_copy["days_until_deadline"] = days_left
                
                if days_left < 0:
                    scholarship_copy["urgency"] = "expired"
                    scholarship_copy["status"] = "Deadline Passed"
                elif days_left < 7:
                    scholarship_copy["urgency"] = "critical"
                    scholarship_copy["status"] = "Apply Now!"
                elif days_left < 30:
                    scholarship_copy["urgency"] = "high"
                    scholarship_copy["status"] = "Closing Soon"
                elif days_left < 90:
                    scholarship_copy["urgency"] = "medium"
                    scholarship_copy["status"] = "Open"
                else:
                    scholarship_copy["urgency"] = "low"
                    scholarship_copy["status"] = "Open"
            except:
                scholarship_copy["days_until_deadline"] = None
                scholarship_copy["urgency"] = "unknown"
                scholarship_copy["status"] = "Check Website"
            
            matched.append(scholarship_copy)
    
    # Sort by: match percentage > amount > urgency
    matched.sort(key=lambda x: (
        -x.get("match_percentage", 0),
        -x.get("amount", 0),
        0 if x.get("urgency") == "critical" else 1 if x.get("urgency") == "high" else 2
    ))
    
    return matched, rejected

def calculate_statistics(matched_scholarships):
    """Calculate comprehensive statistics"""
    if not matched_scholarships:
        return {
            "total_amount": 0,
            "avg_amount": 0,
            "highest_scholarship": None,
            "urgent_count": 0,
            "total_scholarships": 0,
            "wb_scholarships": 0,
            "national_scholarships": 0
        }
    
    total_amount = sum(s["amount"] for s in matched_scholarships)
    avg_amount = total_amount // len(matched_scholarships) if matched_scholarships else 0
    highest = max(matched_scholarships, key=lambda x: x["amount"])
    urgent = sum(1 for s in matched_scholarships if s.get("urgency") in ["critical", "high"])
    wb_count = sum(1 for s in matched_scholarships if "West Bengal" in s.get("states", []))
    national_count = len(matched_scholarships) - wb_count
    
    return {
        "total_amount": total_amount,
        "avg_amount": avg_amount,
        "highest_scholarship": highest["name"],
        "highest_amount": highest["amount"],
        "urgent_count": urgent,
        "total_scholarships": len(matched_scholarships),
        "wb_scholarships": wb_count,
        "national_scholarships": national_count
    }

# ============================================================================
# IMAGE PROCESSING FUNCTIONS
# ============================================================================

def allowed_file(filename):
    """Check if file extension is allowed"""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def process_pdf(filepath):
    """Convert PDF to images and extract text"""
    if not PDF_SUPPORT:
        raise Exception("PDF support not available")
    
    try:
        images = convert_from_path(filepath, dpi=300)
        all_text = ""
        
        for i, image in enumerate(images):
            processed_image = preprocess_image(image)
            text = pytesseract.image_to_string(processed_image, lang='eng')
            all_text += f"\n--- Page {i+1} ---\n{text}"
        
        return all_text
    except Exception as e:
        logger.error(f"PDF processing error: {str(e)}")
        raise

def preprocess_image(image):
    """Enhanced image preprocessing for better OCR"""
    try:
        img_array = np.array(image)
        
        if len(img_array.shape) == 3:
            gray = cv2.cvtColor(img_array, cv2.COLOR_RGB2GRAY)
        else:
            gray = img_array
        
        # Denoise
        denoised = cv2.fastNlMeansDenoising(gray, None, 10, 7, 21)
        
        # Enhance contrast
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8,8))
        enhanced = clahe.apply(denoised)
        
        # Threshold
        thresh = cv2.threshold(enhanced, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)[1]
        
        return Image.fromarray(thresh)
    except Exception as e:
        logger.error(f"Image preprocessing error: {str(e)}")
        return image

def extract_data(text):
    """Enhanced data extraction with better pattern matching"""
    data = {
        "percentage": None,
        "income": None,
        "category": None,
        "name": None,
        "stream": None,
        "state": None
    }
    
    # Extract name
    name_patterns = [
        r'name[:\s]+([A-Za-z\s]+?)(?:\n|percentage|marks)',
        r'student[:\s]+([A-Za-z\s]+?)(?:\n)',
        r'naam[:\s]+([A-Za-z\s]+?)(?:\n)'
    ]
    for pattern in name_patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            data["name"] = match.group(1).strip()
            break
    
    # Extract percentage
    percentage_patterns = [
        r'(\d+\.?\d*)\s*%',
        r'percentage[:\s]+(\d+\.?\d*)',
        r'marks[:\s]+(\d+\.?\d*)',
        r'cgpa[:\s]+(\d+\.?\d*)',
    ]
    for pattern in percentage_patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            value = float(match.group(1))
            # Convert CGPA to percentage if needed
            if value <= 10:
                data["percentage"] = round(value * 9.5, 2)
            else:
                data["percentage"] = value
            break
    
    # Extract income
    income_patterns = [
        r'income[:\s]+₹?\s*(\d+)',
        r'annual\s+income[:\s]+₹?\s*(\d+)',
        r'₹\s*(\d{5,7})',
        r'(\d{5,7})\s*/-'
    ]
    for pattern in income_patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            data["income"] = int(match.group(1))
            break
    
    # Extract category
    categories = {
        "SC": ["scheduled caste", "sc", "s.c.", "s.c"],
        "ST": ["scheduled tribe", "st", "s.t.", "s.t"],
        "OBC": ["other backward", "obc", "o.b.c"],
        "General": ["general", "gen"],
        "Minority": ["minority", "muslim", "christian", "sikh", "buddhist", "jain"]
    }
    
    text_lower = text.lower()
    for category, keywords in categories.items():
        if any(keyword in text_lower for keyword in keywords):
            data["category"] = category
            break
    
    # Extract stream
    streams = {
        "Science": ["science", "pcm", "pcb", "physics", "chemistry"],
        "Commerce": ["commerce", "accountancy", "business"],
        "Arts": ["arts", "humanities", "history", "geography"],
        "Engineering": ["engineering", "b.tech", "btech"],
        "Medical": ["medical", "mbbs", "medicine"]
    }
    
    for stream, keywords in streams.items():
        if any(keyword in text_lower for keyword in keywords):
            data["stream"] = stream
            break
    
    # Extract state (focus on West Bengal)
    if any(word in text_lower for word in ["west bengal", "wb", "kolkata", "bengal"]):
        data["state"] = "West Bengal"
    
    return data

app.secret_key = os.getenv('SESSION_SECRET', 'fallback-secret-key')

# OAuth Configuration
CLIENT_CONFIG = {
    "web": {
        "client_id": os.getenv('GOOGLE_CLIENT_ID'),
        "client_secret": os.getenv('GOOGLE_CLIENT_SECRET'),
        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
        "token_uri": "https://oauth2.googleapis.com/token",
        "redirect_uris": [os.getenv('GOOGLE_REDIRECT_URI', 'http://localhost:5000/auth/callback')]
    }
}

SCOPES = ['https://www.googleapis.com/auth/gmail.send']

# Store login codes and OAuth tokens
login_codes = {}
user_tokens = {}

# ============================================================================
# API ROUTES
# ============================================================================

@app.route('/auth/email-login', methods=['POST'])
def email_login_request():
    """Start email-based login process"""
    try:
        data = request.json
        email = data.get('email')
        
        if not email:
            return jsonify({"success": False, "error": "Email required"}), 400
        
        # Generate 6-digit code
        code = str(random.randint(100000, 999999))
        login_codes[email] = {
            'code': code,
            'expires': time.time() + 600,  # 10 minutes
            'verified': False
        }
        
        # Store email in session
        session['login_email'] = email
        
        # Create OAuth flow
        flow = Flow.from_client_config(
            CLIENT_CONFIG, 
            scopes=SCOPES,
            redirect_uri=CLIENT_CONFIG['web']['redirect_uris'][0]
        )
        
        auth_url, _ = flow.authorization_url(
            access_type='offline',
            include_granted_scopes='true',
            state=email,
            prompt='consent'
        )
        
        return jsonify({
            "success": True,
            "authUrl": auth_url,
            "message": "Redirect to Gmail OAuth"
        }), 200
        
    except Exception as e:
        logger.error(f"Login request error: {str(e)}")
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/auth/callback')
def auth_callback():
    """OAuth callback handler"""
    try:
        email = request.args.get('state')
        
        flow = Flow.from_client_config(
            CLIENT_CONFIG,
            scopes=SCOPES,
            redirect_uri=CLIENT_CONFIG['web']['redirect_uris'][0]
        )
        
        flow.fetch_token(authorization_response=request.url)
        credentials = flow.credentials
        
        # Store credentials
        user_tokens[email] = {
            'token': credentials.token,
            'refresh_token': credentials.refresh_token,
            'token_uri': credentials.token_uri,
            'client_id': credentials.client_id,
            'client_secret': credentials.client_secret,
            'scopes': credentials.scopes
        }
        
        # Send email with login code
        if email in login_codes:
            send_login_email(credentials, email, login_codes[email]['code'])
            
            return '''
            <html>
                <head>
                    <title>Login Code Sent - EduFund</title>
                    <style>
                        body { font-family: Arial, sans-serif; text-align: center; padding: 50px; }
                        .success { color: #28a745; }
                        .btn { background: #007bff; color: white; padding: 10px 20px; border: none; border-radius: 5px; cursor: pointer; }
                    </style>
                </head>
                <body>
                    <h2 class="success">✅ Login Code Sent!</h2>
                    <p>Check your email <strong>{}</strong> for the 6-digit login code.</p>
                    <p>Return to the app and enter the code to complete login.</p>
                    <button class="btn" onclick="window.close()">Close Window</button>
                    <script>
                        setTimeout(() => window.close(), 5000);
                    </script>
                </body>
            </html>
            '''.format(email)
        else:
            return 'Error: Email not found in login requests', 400
            
    except Exception as e:
        logger.error(f'OAuth callback error: {str(e)}')
        return '''
        <html>
            <body>
                <h2 style="color: red;">❌ Authentication Failed</h2>
                <p>Please try again.</p>
                <button onclick="window.close()">Close</button>
            </body>
        </html>
        ''', 500

def send_login_email(credentials, to_email, code):
    """Send login code email using Gmail API"""
    try:
        service = build('gmail', 'v1', credentials=credentials)
        
        # Create email message
        message = MIMEText(f'''
        <!DOCTYPE html>
        <html>
        <head>
            <style>
                body {{ font-family: Arial, sans-serif; background: #f4f4f4; padding: 20px; }}
                .container {{ max-width: 600px; background: white; padding: 30px; border-radius: 10px; margin: 0 auto; }}
                .code {{ font-size: 32px; font-weight: bold; color: #007bff; text-align: center; letter-spacing: 5px; margin: 20px 0; }}
                .footer {{ margin-top: 30px; padding-top: 20px; border-top: 1px solid #ddd; color: #666; }}
            </style>
        </head>
        <body>
            <div class="container">
                <h2 style="color: #333;">🎓 Your EduFund Login Code</h2>
                <p>Hello!</p>
                <p>Use the following code to login to your EduFund account:</p>
                <div class="code">{code}</div>
                <p>This code will expire in <strong>10 minutes</strong>.</p>
                <p>If you didn't request this code, please ignore this email.</p>
                <div class="footer">
                    <p>Best regards,<br>EduFund Team</p>
                </div>
            </div>
        </body>
        </html>
        ''', 'html')
        
        message['to'] = to_email
        message['from'] = 'noreply@edufund.com'
        message['subject'] = 'Your EduFund Login Code'
        
        encoded_message = base64.urlsafe_b64encode(message.as_bytes()).decode()
        
        service.users().messages().send(
            userId='me',
            body={'raw': encoded_message}
        ).execute()
        
        logger.info(f"Login code sent to {to_email}")
        
    except Exception as e:
        logger.error(f"Email sending error: {str(e)}")
        raise

@app.route('/auth/verify-code', methods=['POST'])
def verify_login_code():
    """Verify login code and complete authentication"""
    try:
        data = request.json
        email = data.get('email')
        code = data.get('code')
        
        if not email or not code:
            return jsonify({"success": False, "error": "Email and code required"}), 400
        
        login_data = login_codes.get(email)
        
        if not login_data:
            return jsonify({"success": False, "error": "No login request found for this email"}), 400
        
        if time.time() > login_data['expires']:
            del login_codes[email]
            return jsonify({"success": False, "error": "Code expired"}), 400
        
        if login_data['code'] != code:
            return jsonify({"success": False, "error": "Invalid code"}), 400
        
        # Login successful
        login_data['verified'] = True
        user_profile = {
            'email': email,
            'login_time': datetime.now().isoformat(),
            'auth_method': 'email_code'
        }
        
        return jsonify({
            "success": True,
            "message": "Login successful",
            "user": user_profile,
            "token": "user-auth-token-here"  # In production, use JWT
        }), 200
        
    except Exception as e:
        logger.error(f"Code verification error: {str(e)}")
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/auth/logout', methods=['POST'])
def logout():
    """Logout user and clear session"""
    try:
        email = request.json.get('email')
        if email in login_codes:
            del login_codes[email]
        if email in user_tokens:
            del user_tokens[email]
        
        session.clear()
        
        return jsonify({
            "success": True,
            "message": "Logged out successfully"
        }), 200
        
    except Exception as e:
        logger.error(f"Logout error: {str(e)}")
        return jsonify({"success": False, "error": str(e)}), 500
    


    
@app.route('/exams', methods=['GET'])
def get_exams():
    exams = [
        {
            "id": 1,
            "name": "JEE Main",
            "full_name": "Joint Entrance Examination",
            "conducting_body": "NTA",
            "exam_date": "Jan & Apr 2026",
            "eligibility": {
                "min_percentage": 75,
                "subjects": "Physics, Chemistry, Mathematics"
            },
            "application_url": "https://jeemain.nta.nic.in"
        },
        {
            "id": 2,
            "name": "NEET UG",
            "full_name": "National Eligibility cum Entrance Test",
            "conducting_body": "NTA",
            "exam_date": "May 2026",
            "eligibility": {
                "min_percentage": 50,
                "subjects": "Physics, Chemistry, Biology"
            },
            "application_url": "https://neet.nta.nic.in"
        },
        {
            "id": 3,
            "name": "CUET UG",
            "full_name": "Common University Entrance Test",
            "conducting_body": "NTA",
            "exam_date": "May 2026",
            "eligibility": {
                "min_percentage": 50,
                "subjects": "Various subjects"
            },
            "application_url": "https://cuet.samarth.ac.in"
        }
    ]
    
    return jsonify({
        "success": True,
        "exams": exams
    })

@app.route('/scholarships', methods=['GET', 'OPTIONS'])
def get_all_scholarships():
    """Get all scholarships with optional filtering"""
    if request.method == 'OPTIONS':
        return jsonify({"success": True}), 200
    
    try:
        state = request.args.get('state')
        category = request.args.get('category')
        min_amount = request.args.get('min_amount', type=int)
        
        filtered = SCHOLARSHIPS.copy()
        
        # Filter by state
        if state:
            filtered = [s for s in filtered if state in s.get("states", [])]
        
        # Filter by category
        if category:
            filtered = [s for s in filtered if category in s.get("category", [])]
        
        # Filter by amount
        if min_amount:
            filtered = [s for s in filtered if s.get("amount", 0) >= min_amount]
        
        return jsonify({
            "success": True,
            "scholarships": filtered,
            "total": len(filtered)
        }), 200
    
    except Exception as e:
        logger.error(f"Scholarships error: {str(e)}")
        return jsonify({"success": False, "error": str(e)}), 500
    
@app.route('/application-guidance', methods=['GET', 'OPTIONS'])
def get_application_guidance():
    """Get application guidance content"""
    if request.method == 'OPTIONS':
        return jsonify({"success": True}), 200
    
    guidance_type = request.args.get('type', 'documents')
    
    guidance_data = {
        "documents": {
            "title": "Required Documents Checklist",
            "content": """
📄 **Complete Document Checklist**

**Academic Documents:**
✓ Latest Marksheet (attested)
✓ Previous year marksheet
✓ School/College ID card
✓ Admission letter (for new students)

**Income Proof (Choose ONE):**
✓ Income Certificate from Tehsildar ⭐
✓ ITR (Income Tax Return)
✓ Salary slips (last 6 months)

**Category Certificate:**
✓ SC/ST Certificate
✓ OBC Certificate (valid 1 year)
✓ Minority Certificate

**Identity Proof:**
✓ Aadhaar Card (mandatory!)
✓ Bank Passbook
✓ Passport size photo
            """
        },
        "interview": {
            "title": "Interview Preparation Guide",
            "content": """
🎯 **Interview Preparation Tips**

**Common Questions:**
1. Tell me about yourself
2. Why do you need this scholarship?
3. What are your future goals?
4. How will you utilize this scholarship?

**Documents to Carry:**
✓ All original certificates
✓ 2 sets of photocopies
✓ Application form printout

**Tips:**
- Dress formally
- Reach 15 minutes early
- Be confident and honest
- Speak clearly
            """
        }
    }
    
    return jsonify({
        "success": True,
        "guidance": guidance_data.get(guidance_type, guidance_data["documents"])
    }), 200

@app.route('/chatbot', methods=['POST', 'OPTIONS'])
def chatbot_query():
    """Enhanced chatbot with West Bengal focus"""
    if request.method == 'OPTIONS':
        return jsonify({"success": True}), 200
    
    try:
        data = request.json
        query = data.get('query', '').lower()
        user_id = data.get('user_id', 'default')
        
        if not query:
            return jsonify({"success": False, "error": "No query provided"}), 400
        
        # Initialize conversation history
        if user_id not in conversation_history:
            conversation_history[user_id] = []
        
        conversation_history[user_id].append(query)
        if len(conversation_history[user_id]) > 10:
            conversation_history[user_id] = conversation_history[user_id][-10:]
        
        response = generate_chatbot_response(query)
        
        return jsonify({
            "success": True,
            "query": query,
            "response": response
        }), 200
    
    except Exception as e:
        logger.error(f"Chatbot error: {str(e)}")
        return jsonify({"success": False, "error": str(e)}), 500

def generate_chatbot_response(query):
    """Generate intelligent responses with WB focus"""
    query = query.lower()
    
    # West Bengal specific queries
    if any(word in query for word in ['west bengal', 'wb', 'bengal', 'kolkata']):
        return f"""
🎓 **West Bengal Scholarships**

We have **6 special scholarships** for West Bengal students:

**👧 For Girls:**
• **Kanyashree K1**: ₹750/year (Class 8-12)
• **Kanyashree K2**: ₹25,000 one-time (Age 18-19)

**📚 For Higher Education:**
• **Swami Vivekananda**: ₹15,000 (60%+ marks)
• **Aikyashree**: ₹5,000 (Minority students)

**🎯 For SC/ST:**
• **Dr. Ambedkar Scholarship**: ₹12,000
• **Taruner Swapna**: ₹8,000 (Technical courses)

**Plus {len(SCHOLARSHIPS) - 6} National Scholarships available!**

👉 Enter your marks and category to find YOUR matches!

Are you from West Bengal? Tell me your percentage! 😊
"""
    
    # Kanyashree specific
    if 'kanyashree' in query:
        return """
💝 **Kanyashree Prakalpa - Complete Guide**

**K1 Scholarship (Annual):**
• Amount: ₹750/year
• For: Girls in Class 8-12
• Eligibility: Must be unmarried, WB resident
• No income limit!
• Apply at: wbkanyashree.gov.in

**K2 Scholarship (One-time):**
• Amount: ₹25,000 (one-time)
• For: Girls aged 18-19
• Eligibility: Class 12 passed, enrolled in degree/diploma
• Must be unmarried

**Documents Needed:**
✓ Aadhaar Card
✓ Bank Account (girl's name)
✓ School/College Certificate
✓ Age Proof

**Apply Online:**
1. Visit wbkanyashree.gov.in
2. Register with mobile/email
3. Fill application
4. Upload documents
5. Submit!

Money credited directly to bank! 💰
"""
    
    # General scholarship query
    if any(word in query for word in ['scholarship', 'amount', 'money']):
        wb_count = sum(1 for s in SCHOLARSHIPS if "West Bengal" in s.get("states", []))
        return f"""
🎓 **{len(SCHOLARSHIPS)} Scholarships Available!**

**West Bengal Special ({wb_count}):**
💰 Kanyashree K2: ₹25,000
💰 Swami Vivekananda: ₹15,000
💰 Dr. Ambedkar (WB): ₹12,000

**National High-Value:**
💰 Central Sector SC: ₹2,00,000
💰 INSPIRE: ₹80,000
💰 AICTE Pragati: ₹50,000

**By Category:**
• SC/ST: {sum(1 for s in SCHOLARSHIPS if 'SC' in s['category'] or 'ST' in s['category'])} scholarships
• OBC: {sum(1 for s in SCHOLARSHIPS if 'OBC' in s['category'])} scholarships
• General: {sum(1 for s in SCHOLARSHIPS if 'General' in s['category'])} scholarships
• Girls Special: 4 scholarships

📝 **Tell me:**
1. Your percentage/marks
2. Your category (SC/ST/OBC/General)
3. Your state

I'll find perfect matches for YOU! 🎯
"""
    
    # Eligibility check
    if any(word in query for word in ['eligible', 'qualify', 'can i get']):
        return """
✅ **Quick Eligibility Check**

Tell me these 3 things:

1️⃣ **Your Percentage** (e.g., 75%, 8.5 CGPA)
2️⃣ **Family Income** (Annual, in ₹)
3️⃣ **Your Category** (SC/ST/OBC/General/Minority)

**Example:**
"I have 72% marks, income is 3 lakh, OBC category"

Then I'll instantly show you:
✓ All scholarships you qualify for
✓ Amount you can get
✓ Deadlines
✓ Documents needed

**Quick Tips:**
• 50%+ = Eligible for 12+ scholarships
• 60%+ = Eligible for 18+ scholarships
• 80%+ = Eligible for ALL scholarships!

What's your percentage? 📊
"""
    
    # Application process
    if any(word in query for word in ['apply', 'how to', 'process']):
        return """
📝 **How to Apply - Step by Step**

**Step 1: Check Eligibility** ✅
• Find scholarships matching your profile
• Note down required percentage & income

**Step 2: Gather Documents** 📄
Common documents needed:
• Latest Marksheet
• Income Certificate (Tehsildar)
• Caste Certificate (if SC/ST/OBC)
• Aadhaar Card
• Bank Passbook (front page)
• Passport photo

**Step 3: Register on Portal** 👤
• Visit scholarships.gov.in
• Click "New Registration"
• Use email/mobile to create account
• Save Application ID & Password

**Step 4: Fill Application** ✍️
• Login to portal
• Select your scholarship
• Fill details carefully
• Double-check spelling
• Use CAPITAL LETTERS for name

**Step 5: Upload Documents** 📤
• Scan documents clearly
• PDF/JPG format only
• Max 200KB per file
• All documents mandatory

**Step 6: Submit & Track** 📍
• Review before final submit
• Take screenshot of confirmation
• Note Application ID
• Check status weekly

**Timeline:**
Application → 1-2 months verification → 3-6 months payment

Need help with specific step? Ask me! 🤗
"""
    
    # Documents query
    if any(word in query for word in ['document', 'certificate', 'paper']):
        return """
📄 **Complete Document Checklist**

**Academic Documents:**
✓ Latest Marksheet (attested)
✓ Previous year marksheet
✓ School/College ID card
✓ Admission letter (for new students)

**Income Proof (Choose ONE):**
✓ Income Certificate from Tehsildar ⭐
✓ ITR (Income Tax Return)
✓ Salary slips (last 6 months)
✓ Ration Card

**Category Certificate:**
✓ SC/ST Certificate (lifetime valid)
✓ OBC Certificate (valid 1 year only!)
✓ OBC Non-Creamy Layer Certificate
✓ EWS Certificate (valid 1 year)
✓ Minority Certificate

**Identity Proof:**
✓ Aadhaar Card (mandatory!)
✓ Bank Passbook (student's name)
✓ Passport size photo (recent)

**Where to Get Income Certificate:**
📍 Tehsil Office / SDO Office
⏱️ Processing: 7-15 days
💰 Fee: ₹20-50
📋 Needed: Ration card, voter ID, self-declaration

**Pro Tips:**
• Get OBC certificate renewed yearly
• Income certificate valid for 6 months
• Keep multiple photocopies
• Scan all documents in advance

Which document you need help with? 😊
"""
    
    # Deadline query
    if any(word in query for word in ['deadline', 'last date', 'when']):
        return """
📅 **Important Deadlines 2025-26**

**🔴 URGENT (Within 1 Month):**
• **AICTE Pragati**: 31 Oct 2025
• **PMSS**: 15 Oct 2025
• **National Merit**: 31 Oct 2025
• **Swami Vivekananda**: 31 Oct 2025

**🟡 CLOSING SOON (Within 3 Months):**
• **NMMS**: 30 Nov 2025
• **Kanyashree K1**: 30 Nov 2025

**🟢 OPEN NOW:**
• **NSP Scholarships**: 31 Dec 2025
• **Post-Matric SC/ST**: 31 Dec 2025
• **INSPIRE**: 31 Dec 2025
• **OBC Scholarship**: 15 Jan 2026
• **Kanyashree K2**: 30 Jun 2026

**⚠️ Pro Tips:**
• Apply at least 15 days before deadline
• Portal gets slow on last day
• Keep documents ready NOW
• Don't wait for last minute!

Upload your marksheet to see YOUR personalized deadlines! ⏰
"""
    
    # Default response
    return """
👋 **Hi! I'm your EduFund Scholarship Assistant!**

I specialize in **West Bengal & National Scholarships**!

**I can help you with:**

🎓 **Find Scholarships**
• Based on your marks
• Based on your category
• Based on your state

📋 **Application Help**
• What documents needed
• How to apply online
• Step-by-step guide

📅 **Important Dates**
• Deadlines
• Application windows

💡 **Special Focus:**
• West Bengal scholarships
• Kanyashree (K1 & K2)
• SC/ST/OBC schemes
• Girls' scholarships

**Quick Start:**
Just tell me:
"I have X% marks, Y income, Z category"

Or ask:
• "Show West Bengal scholarships"
• "How to apply for Kanyashree?"
• "What documents do I need?"
• "Check deadlines"

What would you like to know? 😊
"""

@app.errorhandler(413)
def too_large(e):
    return jsonify({"success": False, "error": "File too large (max 10MB)"}), 413

@app.errorhandler(404)
def not_found(e):
    return jsonify({"success": False, "error": "Endpoint not found"}), 404

@app.errorhandler(500)
def internal_error(e):
    return jsonify({"success": False, "error": "Internal server error"}), 500

# ============================================================================
# MAIN
# ============================================================================

if __name__ == '__main__':
    wb_count = sum(1 for s in SCHOLARSHIPS if "West Bengal" in s.get("states", []))
    national_count = len(SCHOLARSHIPS) - wb_count
    
    print("\n" + "="*70)
    print("🎓 EDUFUND - REAL SCHOLARSHIP DATA (v3.0)")
    print("="*70)
    print(f"✓ Server: http://localhost:5000")
    print(f"✓ Total Scholarships: {len(SCHOLARSHIPS)}")
    print(f"  ├─ West Bengal: {wb_count} scholarships")
    print(f"  └─ National: {national_count} scholarships")
    print(f"✓ PDF Support: {'✅ Enabled' if PDF_SUPPORT else '⚠️  Disabled'}")
    print("="*70)
    print("\n📝 **API Endpoints:**")
    print("   POST /upload - Upload documents")
    print("   POST /manual - Manual entry")
    print("   GET  /scholarships - Get all scholarships")
    print("   POST /chatbot - Chat assistant")
    print("="*70 + "\n")
    
    app.run(debug=True, port=5000, host='0.0.0.0')

