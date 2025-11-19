"""
SCHOLARCONNECT PRO - AI-POWERED MULTILINGUAL PLATFORM
Complete production-ready backend with OCR, Chatbot, PDF Support, Bookmarks
Version: 2.0 - Frontend Compatible
"""

from flask import Flask, request, jsonify, send_from_directory, send_file
from flask_cors import CORS
import pytesseract
from PIL import Image
import cv2
import numpy as np
import re
import os
import random
from datetime import datetime
import json
from werkzeug.utils import secure_filename
import logging
import tempfile

# PDF Support (Optional)
try:
    from pdf2image import convert_from_path
    PDF_SUPPORT = True
except ImportError:
    PDF_SUPPORT = False
    print("⚠️  PDF support disabled. Install with: pip3 install pdf2image poppler-utils")

# Initialize Flask app
app = Flask(__name__)

# Configure logging
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
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'pdf'}  # NEW: Added PDF
MAX_FILE_SIZE = 10 * 1024 * 1024  # NEW: Increased to 10MB for PDFs

if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = MAX_FILE_SIZE

# Set Tesseract path based on OS
import platform
if platform.system() == "Windows":
    pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'
elif platform.system() == "Darwin":  # macOS
    if os.path.exists('/opt/homebrew/bin/tesseract'):
        pytesseract.pytesseract.tesseract_cmd = '/opt/homebrew/bin/tesseract'
    elif os.path.exists('/usr/local/bin/tesseract'):
        pytesseract.pytesseract.tesseract_cmd = '/usr/local/bin/tesseract'

# NEW: Conversation history store
conversation_history = {}

# NEW: User bookmarks store (in-memory)
user_bookmarks = {}

# ============================================================================
# LANGUAGE SUPPORT
# ============================================================================

SUPPORTED_LANGUAGES = {
    'en': 'English',
    'hi': 'हिंदी',
    'bn': 'বাংলা',
    'ta': 'தமிழ்',
    'mr': 'मराठी',
    'te': 'తెలుగు',
    'gu': 'ગુજરાતી'
}

UI_TRANSLATIONS = {
    'en': {
        'upload_document': 'Upload Document',
        'manual_entry': 'Manual Entry',
        'find_scholarships': 'Find Scholarships',
        'matched': 'scholarships matched',
        'no_match': 'No matching scholarships found'
    },
    'hi': {
        'upload_document': 'दस्तावेज़ अपलोड करें',
        'manual_entry': 'मैन्युअल एंट्री',
        'find_scholarships': 'छात्रवृत्ति खोजें',
        'matched': 'छात्रवृत्तियां मिलीं',
        'no_match': 'कोई मिलती-जुलती छात्रवृत्ति नहीं मिली'
    }
}

# ============================================================================
# COMPREHENSIVE SCHOLARSHIP DATABASE
# ============================================================================

SCHOLARSHIPS = [
    {
        "id": 1,
        "name": "National Scholarship Portal - Pre-Matric SC/ST",
        "name_hi": "राष्ट्रीय छात्रवृत्ति पोर्टल - प्री-मैट्रिक SC/ST",
        "min_percentage": 50,
        "max_income": 250000,
        "category": ["SC", "ST"],
        "amount": 20000,
        "deadline": "31-12-2025",
        "description": "For SC/ST students from Class 9-10. Covers tuition fees and maintenance allowance.",
        "description_hi": "कक्षा 9-10 के SC/ST छात्रों के लिए। ट्यूशन फीस और रखरखाव भत्ता शामिल है।",
        "apply_url": "https://scholarships.gov.in",
        "eligibility": ["Class 9-10", "SC/ST category", "Annual family income < ₹2.5 lakh"],
        "documents": ["Marksheet", "Income Certificate", "Caste Certificate", "Bank Details"],
        "eligible_streams": ["All"],
        "states": ["All States"]
    },
    {
        "id": 11,
        "name": "Swami Vivekananda Single Girl Child Scholarship",
        "name_hi": "स्वामी विवेकानंद एकल बालिका छात्रवृत्ति",
        "min_percentage": 53,
        "max_income": 6000000,
        "category": ["General", "OBC", "SC", "ST"],
        "amount": 31000,
        "deadline": "31-12-2025",
        "description": "For single girl child pursuing UG/PG courses. Only one girl child in family.",
        "description_hi": "UG/PG करने वाली एकल बालिका के लिए।",
        "apply_url": "https://scholarships.gov.in",
        "eligibility": ["Single girl child", "53%+ marks", "UG/PG courses"],
        "documents": ["Marksheet", "Single Girl Child Certificate", "Admission Proof"],
        "eligible_streams": ["All"],
        "states": ["All States"]
    },
    {
        "id": 12,
        "name": "Saksham Scholarship for PwD Students",
        "name_hi": "सक्षम छात्रवृत्ति - दिव्यांग छात्रों के लिए",
        "min_percentage": 40,
        "max_income": 800000,
        "category": ["General", "OBC", "SC", "ST"],
        "amount": 30000,
        "deadline": "31-12-2025",
        "description": "For Persons with Disabilities (40%+) pursuing technical courses. AICTE approved institutions.",
        "description_hi": "दिव्यांग छात्रों (40%+ विकलांगता) के लिए तकनीकी पाठ्यक्रम।",
        "apply_url": "https://www.aicte-india.org",
        "eligibility": ["PwD (40%+)", "AICTE approved courses", "40%+ marks"],
        "documents": ["PwD Certificate", "Marksheet", "Admission Proof"],
        "eligible_streams": ["Engineering", "Pharmacy", "Management"],
        "states": ["All States"]
    },
    {
        "id": 13,
        "name": "Dr. Ambedkar Post-Matric Scholarship for Economically Backward Classes",
        "name_hi": "डॉ. अंबेडकर पोस्ट-मैट्रिक छात्रवृत्ति (EBC)",
        "min_percentage": 50,
        "max_income": 100000,
        "category": ["General"],
        "amount": 25000,
        "deadline": "31-12-2025",
        "description": "For economically backward general category students. EWS certificate required.",
        "description_hi": "आर्थिक रूप से कमजोर सामान्य वर्ग के छात्रों के लिए।",
        "apply_url": "https://scholarships.gov.in",
        "eligibility": ["General category", "EWS certificate", "50%+ marks", "Income < ₹1 lakh"],
        "documents": ["EWS Certificate", "Marksheet", "Income Certificate"],
        "eligible_streams": ["All"],
        "states": ["All States"]
    },
    {
        "id": 14,
        "name": "Top Class Education Scheme for SC Students",
        "name_hi": "SC छात्रों के लिए शीर्ष वर्ग शिक्षा योजना",
        "min_percentage": 60,
        "max_income": 6000000,
        "category": ["SC"],
        "amount": 42000,
        "deadline": "31-12-2025",
        "description": "For SC students pursuing professional courses in top institutions.",
        "description_hi": "शीर्ष संस्थानों में व्यावसायिक पाठ्यक्रम करने वाले SC छात्रों के लिए।",
        "apply_url": "https://socialjustice.gov.in",
        "eligibility": ["SC category", "Top institutions", "60%+ marks"],
        "documents": ["SC Certificate", "Marksheet", "Admission Letter"],
        "eligible_streams": ["Engineering", "Medical", "Management", "Law"],
        "states": ["All States"]
    },
    {
        "id": 15,
        "name": "National Fellowship for OBC Students",
        "name_hi": "OBC छात्रों के लिए राष्ट्रीय फेलोशिप",
        "min_percentage": 60,
        "max_income": 8000000,
        "category": ["OBC"],
        "amount": 31000,
        "deadline": "31-12-2025",
        "description": "For OBC students pursuing MPhil/PhD. ₹31,000/month + contingency grant.",
        "description_hi": "MPhil/PhD करने वाले OBC छात्रों के लिए।",
        "apply_url": "https://socialjustice.gov.in",
        "eligibility": ["OBC (Non-Creamy Layer)", "MPhil/PhD courses", "60%+ in PG"],
        "documents": ["OBC Certificate", "PG Marksheet", "Research Proposal"],
        "eligible_streams": ["All"],
        "states": ["All States"]
    },
    {
        "id": 16,
        "name": "Central Sector Scholarship Scheme (CSSS)",
        "name_hi": "केंद्रीय क्षेत्र छात्रवृत्ति योजना",
        "min_percentage": 80,
        "max_income": 800000,
        "category": ["General", "OBC", "SC", "ST"],
        "amount": 10000,
        "deadline": "31-10-2025",
        "description": "For meritorious students securing 80%+ in Class 12. Renewable for 3-5 years.",
        "description_hi": "कक्षा 12 में 80%+ अंक प्राप्त करने वाले मेधावी छात्रों के लिए।",
        "apply_url": "https://scholarships.gov.in",
        "eligibility": ["80%+ in Class 12", "All categories", "UG/PG courses"],
        "documents": ["12th Marksheet", "Admission Proof", "Income Certificate"],
        "eligible_streams": ["All"],
        "states": ["All States"]
    },
    {
        "id": 17,
        "name": "Kishore Vaigyanik Protsahan Yojana (KVPY)",
        "name_hi": "किशोर वैज्ञानिक प्रोत्साहन योजना",
        "min_percentage": 75,
        "max_income": 8000000,
        "category": ["General", "OBC", "SC", "ST"],
        "amount": 70000,
        "deadline": "15-09-2025",
        "description": "For students pursuing basic science courses. Monthly stipend + annual contingency.",
        "description_hi": "बुनियादी विज्ञान पाठ्यक्रम करने वाले छात्रों के लिए।",
        "apply_url": "https://kvpy.iisc.ac.in",
        "eligibility": ["Science stream", "75%+ marks", "Research orientation"],
        "documents": ["Marksheet", "Research Statement", "Recommendation Letters"],
        "eligible_streams": ["Science"],
        "states": ["All States"]
    },
    {
        "id": 18,
        "name": "Rajiv Gandhi National Fellowship for SC/ST Students",
        "name_hi": "राजीव गांधी राष्ट्रीय फेलोशिप (SC/ST)",
        "min_percentage": 55,
        "max_income": 6000000,
        "category": ["SC", "ST"],
        "amount": 31000,
        "deadline": "31-12-2025",
        "description": "For SC/ST students pursuing MPhil/PhD. Monthly fellowship + contingency.",
        "description_hi": "MPhil/PhD करने वाले SC/ST छात्रों के लिए।",
        "apply_url": "https://socialjustice.gov.in",
        "eligibility": ["SC/ST category", "55%+ in PG", "MPhil/PhD"],
        "documents": ["Caste Certificate", "PG Marksheet", "Research Proposal"],
        "eligible_streams": ["All"],
        "states": ["All States"]
    },
    {
        "id": 19,
        "name": "Maulana Azad National Fellowship for Minority Students",
        "name_hi": "मौलाना आजाद राष्ट्रीय फेलोशिप (अल्पसंख्यक)",
        "min_percentage": 50,
        "max_income": 6000000,
        "category": ["Minority"],
        "amount": 31000,
        "deadline": "31-12-2025",
        "description": "For minority students pursuing MPhil/PhD. ₹31,000/month + contingency.",
        "description_hi": "MPhil/PhD करने वाले अल्पसंख्यक छात्रों के लिए।",
        "apply_url": "https://www.maef.nic.in",
        "eligibility": ["Minority community", "50%+ in PG", "MPhil/PhD"],
        "documents": ["Minority Certificate", "PG Marksheet", "Research Proposal"],
        "eligible_streams": ["All"],
        "states": ["All States"]
    },
    {
        "id": 20,
        "name": "Padho Pardesh - Interest Subsidy Scheme for Minority Students",
        "name_hi": "पढ़ो परदेस - अल्पसंख्यक छात्रों के लिए",
        "min_percentage": 50,
        "max_income": 600000,
        "category": ["Minority"],
        "amount": 150000,
        "deadline": "31-12-2025",
        "description": "Interest subsidy on education loans for minority students studying abroad.",
        "description_hi": "विदेश में पढ़ने वाले अल्पसंख्यक छात्रों के लिए शिक्षा ऋण पर ब्याज सब्सिडी।",
        "apply_url": "https://www.maef.nic.in",
        "eligibility": ["Minority community", "Education loan", "Studying abroad"],
        "documents": ["Minority Certificate", "Loan Sanction Letter", "Admission Proof"],
        "eligible_streams": ["All"],
        "states": ["All States"]
    },
    {
        "id": 21,
        "name": "Begum Hazrat Mahal National Scholarship for Minority Girls",
        "name_hi": "बेगम हज़रत महल राष्ट्रीय छात्रवृत्ति (अल्पसंख्यक लड़कियां)",
        "min_percentage": 50,
        "max_income": 200000,
        "category": ["Minority"],
        "amount": 15000,
        "deadline": "31-12-2025",
        "description": "For minority girl students from Class 9-12. Encouraging girls' education.",
        "description_hi": "कक्षा 9-12 की अल्पसंख्यक बालिकाओं के लिए।",
        "apply_url": "https://www.maef.nic.in",
        "eligibility": ["Minority girls", "Class 9-12", "50%+ marks"],
        "documents": ["Minority Certificate", "Marksheet", "Income Certificate"],
        "eligible_streams": ["All"],
        "states": ["All States"]
    },
    {
        "id": 22,
        "name": "ISRO Young Scientist Programme (YUVIKA)",
        "name_hi": "इसरो युवा वैज्ञानिक कार्यक्रम",
        "min_percentage": 78,
        "max_income": 8000000,
        "category": ["General", "OBC", "SC", "ST"],
        "amount": 0,
        "deadline": "28-02-2025",
        "description": "2-week training programme at ISRO centres for Class 9 students. Free training + travel.",
        "description_hi": "कक्षा 9 के छात्रों के लिए इसरो केंद्रों पर 2-सप्ताह का प्रशिक्षण।",
        "apply_url": "https://isro.gov.in",
        "eligibility": ["Class 9 students", "78%+ marks", "Science interest"],
        "documents": ["Class 8 Marksheet", "School Recommendation", "Parental Consent"],
        "eligible_streams": ["Science"],
        "states": ["All States"]
    },
    {
        "id": 23,
        "name": "DBT Junior Research Fellowship (JRF)",
        "name_hi": "DBT जूनियर रिसर्च फेलोशिप",
        "min_percentage": 60,
        "max_income": 8000000,
        "category": ["General", "OBC", "SC", "ST"],
        "amount": 31000,
        "deadline": "Varies",
        "description": "For students pursuing research in Biotechnology and Life Sciences.",
        "description_hi": "जैव प्रौद्योगिकी और जीवन विज्ञान में अनुसंधान करने वाले छात्रों के लिए।",
        "apply_url": "https://dbtindia.gov.in",
        "eligibility": ["MSc in Life Sciences", "60%+ marks", "Research focus"],
        "documents": ["MSc Marksheet", "Research Proposal", "Recommendation Letters"],
        "eligible_streams": ["Science"],
        "states": ["All States"]
    },
    {
        "id": 24,
        "name": "NCERT National Talent Search Examination (NTSE) Scholarship",
        "name_hi": "NCERT राष्ट्रीय प्रतिभा खोज परीक्षा छात्रवृत्ति",
        "min_percentage": 60,
        "max_income": 8000000,
        "category": ["General", "OBC", "SC", "ST"],
        "amount": 12500,
        "deadline": "Varies by State",
        "description": "For Class 10 students. ₹12,500/year for 4 years (Class 11-14).",
        "description_hi": "कक्षा 10 के छात्रों के लिए।",
        "apply_url": "https://ncert.nic.in",
        "eligibility": ["Class 10 students", "NTSE qualified", "60%+ marks"],
        "documents": ["Class 10 Marksheet", "NTSE Certificate", "School Certificate"],
        "eligible_streams": ["All"],
        "states": ["All States"]
    },
    {
        "id": 25,
        "name": "AICTE - PG (GATE/GPAT) Scholarship",
        "name_hi": "AICTE - PG (GATE/GPAT) छात्रवृत्ति",
        "min_percentage": 60,
        "max_income": 8000000,
        "category": ["General", "OBC", "SC", "ST"],
        "amount": 12400,
        "deadline": "31-10-2025",
        "description": "For GATE/GPAT qualified students pursuing M.Tech/M.Pharm. ₹12,400/month.",
        "description_hi": "GATE/GPAT उत्तीर्ण छात्रों के लिए M.Tech/M.Pharm में।",
        "apply_url": "https://www.aicte-india.org",
        "eligibility": ["GATE/GPAT qualified", "M.Tech/M.Pharm", "60%+ in UG"],
        "documents": ["GATE/GPAT Scorecard", "UG Marksheet", "Admission Proof"],
        "eligible_streams": ["Engineering", "Pharmacy"],
        "states": ["All States"]
    },
    {
        "id": 2,
        "name": "National Scholarship Portal - Post-Matric SC/ST",
        "name_hi": "राष्ट्रीय छात्रवृत्ति पोर्टल - पोस्ट-मैट्रिक SC/ST",
        "min_percentage": 50,
        "max_income": 250000,
        "category": ["SC", "ST"],
        "amount": 50000,
        "deadline": "31-12-2025",
        "description": "For SC/ST students pursuing higher education (Class 11 onwards). Full tuition + maintenance.",
        "description_hi": "कक्षा 11 से ऊपर की शिक्षा प्राप्त करने वाले SC/ST छात्रों के लिए। पूर्ण ट्यूशन + रखरखाव।",
        "apply_url": "https://scholarships.gov.in",
        "eligibility": ["Class 11 onwards", "SC/ST category", "Annual income < ₹2.5 lakh"],
        "documents": ["Marksheet", "Income Certificate", "Caste Certificate", "Admission Proof"],
        "eligible_streams": ["All"],
        "states": ["All States"]
    },
    {
        "id": 3,
        "name": "Post Matric Scholarship for OBC Students",
        "name_hi": "OBC छात्रों के लिए पोस्ट मैट्रिक छात्रवृत्ति",
        "min_percentage": 50,
        "max_income": 100000,
        "category": ["OBC"],
        "amount": 30000,
        "deadline": "15-01-2026",
        "description": "Central sector scheme for OBC students in higher education with merit-based selection.",
        "description_hi": "उच्च शिक्षा में OBC छात्रों के लिए केंद्रीय क्षेत्र योजना।",
        "apply_url": "https://scholarships.gov.in",
        "eligibility": ["OBC (Non-Creamy Layer)", "Class 11+", "Income < ₹1 lakh"],
        "documents": ["Marksheet", "OBC Certificate", "Income Certificate", "Bank Details"],
        "eligible_streams": ["All"],
        "states": ["All States"]
    },
    {
        "id": 4,
        "name": "Merit-cum-Means Scholarship for Professional Courses",
        "name_hi": "व्यावसायिक पाठ्यक्रमों के लिए मेरिट-कम-मीन्स छात्रवृत्ति",
        "min_percentage": 75,
        "max_income": 450000,
        "category": ["General", "OBC", "SC", "ST"],
        "amount": 50000,
        "deadline": "15-01-2026",
        "description": "For meritorious students pursuing technical/professional courses like Engineering, Medical, MBA.",
        "description_hi": "इंजीनियरिंग, मेडिकल, MBA जैसे व्यावसायिक पाठ्यक्रमों में प्रवेश लेने वाले मेधावी छात्रों के लिए।",
        "apply_url": "https://scholarships.gov.in",
        "eligibility": ["75%+ in qualifying exam", "Professional course", "Income < ₹4.5 lakh"],
        "documents": ["12th Marksheet", "Admission Letter", "Income Certificate"],
        "eligible_streams": ["Science", "Engineering", "Medical", "Management"],
        "states": ["All States"]
    },
    {
        "id": 5,
        "name": "Central Sector Scheme of National Merit Scholarship",
        "name_hi": "राष्ट्रीय मेरिट छात्रवृत्ति की केंद्रीय क्षेत्र योजना",
        "min_percentage": 80,
        "max_income": 600000,
        "category": ["General", "OBC", "SC", "ST"],
        "amount": 100000,
        "deadline": "31-10-2025",
        "description": "For students who secure 80%+ in Class 12 board. Full tuition waiver for UG/PG courses.",
        "description_hi": "कक्षा 12 में 80%+ अंक प्राप्त करने वाले छात्रों के लिए। UG/PG पाठ्यक्रमों के लिए पूर्ण ट्यूशन छूट।",
        "apply_url": "https://scholarships.gov.in",
        "eligibility": ["80%+ in Class 12", "All categories", "Income < ₹6 lakh"],
        "documents": ["12th Marksheet", "Admission Proof", "Income Certificate"],
        "eligible_streams": ["All"],
        "states": ["All States"]
    },
    {
        "id": 6,
        "name": "Prime Minister's Scholarship Scheme (PMSS)",
        "name_hi": "प्रधानमंत्री छात्रवृत्ति योजना (PMSS)",
        "min_percentage": 75,
        "max_income": 600000,
        "category": ["General", "OBC", "SC", "ST"],
        "amount": 36000,
        "deadline": "15-11-2025",
        "description": "For wards of ex-servicemen, coast guard personnel. ₹3000/month for professional courses.",
        "description_hi": "भूतपूर्व सैनिकों के बच्चों के लिए। व्यावसायिक पाठ्यक्रमों के लिए ₹3000/माह।",
        "apply_url": "https://ksb.gov.in",
        "eligibility": ["Ex-servicemen wards", "75%+ marks", "Professional courses"],
        "documents": ["ESM Identity Card", "Marksheet", "College Admission Letter"],
        "eligible_streams": ["All"],
        "states": ["All States"]
    },
    {
        "id": 7,
        "name": "INSPIRE Scholarship for Higher Education (SHE)",
        "name_hi": "उच्च शिक्षा के लिए INSPIRE छात्रवृत्ति",
        "min_percentage": 85,
        "max_income": 500000,
        "category": ["General", "OBC", "SC", "ST"],
        "amount": 80000,
        "deadline": "31-12-2025",
        "description": "For top 1% students in Class 12 pursuing BSc/MSc in Natural Sciences. ₹80,000/year fixed.",
        "description_hi": "कक्षा 12 में शीर्ष 1% छात्रों के लिए जो प्राकृतिक विज्ञान में BSc/MSc कर रहे हैं।",
        "apply_url": "https://online-inspire.gov.in",
        "eligibility": ["Top 1% in Class 12", "Natural Science courses", "Income < ₹5 lakh"],
        "documents": ["12th Marksheet (85%+)", "BSc/MSc Admission Proof", "Income Certificate"],
        "eligible_streams": ["Science"],
        "states": ["All States"]
    },
    {
        "id": 8,
        "name": "Post-Matric Scholarship for Minorities",
        "name_hi": "अल्पसंख्यकों के लिए पोस्ट-मैट्रिक छात्रवृत्ति",
        "min_percentage": 50,
        "max_income": 200000,
        "category": ["Minority"],
        "amount": 15000,
        "deadline": "31-12-2025",
        "description": "For Muslim, Christian, Sikh, Buddhist, Jain, Parsi students. 30% seats for girls.",
        "description_hi": "मुस्लिम, ईसाई, सिख, बौद्ध, जैन, पारसी छात्रों के लिए। लड़कियों के लिए 30% सीटें।",
        "apply_url": "https://scholarships.gov.in",
        "eligibility": ["Minority community", "Class 11+", "Income < ₹2 lakh"],
        "documents": ["Minority Certificate", "Marksheet", "Income Certificate"],
        "eligible_streams": ["All"],
        "states": ["All States"]
    },
    {
        "id": 9,
        "name": "National Means-cum-Merit Scholarship (NMMS)",
        "name_hi": "राष्ट्रीय मीन्स-कम-मेरिट छात्रवृत्ति (NMMS)",
        "min_percentage": 55,
        "max_income": 150000,
        "category": ["General", "OBC", "SC", "ST"],
        "amount": 12000,
        "deadline": "30-11-2025",
        "description": "For Class 9-12 students. ₹12,000/year to prevent dropouts from economically weaker sections.",
        "description_hi": "कक्षा 9-12 के छात्रों के लिए। आर्थिक रूप से कमजोर वर्गों से ड्रॉपआउट रोकने के लिए।",
        "apply_url": "https://scholarships.gov.in",
        "eligibility": ["Class 9-12", "55%+ in Class 8", "Income < ₹1.5 lakh"],
        "documents": ["Class 8 Marksheet", "Income Certificate", "School Certificate"],
        "eligible_streams": ["All"],
        "states": ["All States"]
    },
    {
        "id": 10,
        "name": "AICTE Pragati Scholarship for Girls",
        "name_hi": "लड़कियों के लिए AICTE प्रगति छात्रवृत्ति",
        "min_percentage": 60,
        "max_income": 800000,
        "category": ["General", "OBC", "SC", "ST"],
        "amount": 50000,
        "deadline": "31-10-2025",
        "description": "For girl students in AICTE-approved Engineering/Pharmacy courses. 1 girl per family.",
        "description_hi": "AICTE-स्वीकृत इंजीनियरिंग/फार्मेसी पाठ्यक्रमों में लड़कियों के लिए।",
        "apply_url": "https://www.aicte-india.org",
        "eligibility": ["Girl students only", "AICTE approved colleges", "Income < ₹8 lakh"],
        "documents": ["Marksheet", "Admission Proof", "Income Certificate", "Single Girl Declaration"],
        "eligible_streams": ["Engineering", "Pharmacy"],
        "states": ["All States"]
    }
]

# ============================================================================
# EXAM INFORMATION DATABASE
# ============================================================================

EXAMS_INFO = [
    {
        "id": 1,
        "name": "JEE Main",
        "name_hi": "JEE मेन",
        "full_name": "Joint Entrance Examination - Main",
        "conducting_body": "NTA",
        "exam_date": "January & April 2026",
        "eligibility": {
            "min_percentage": 75,
            "subjects": ["Physics", "Chemistry", "Mathematics"],
            "age_limit": "No age limit",
            "attempts": "Unlimited"
        },
        "documents_required": [
            "Class 10 Certificate",
            "Class 12 Marksheet",
            "Category Certificate (if applicable)",
            "Photograph",
            "Signature"
        ],
        "application_fee": {
            "General": 1000,
            "OBC": 800,
            "SC/ST": 500
        },
        "syllabus_url": "https://nta.ac.in/jee-main",
        "application_url": "https://jeemain.nta.nic.in"
    },
    {
        "id": 2,
        "name": "NEET UG",
        "name_hi": "NEET UG",
        "full_name": "National Eligibility cum Entrance Test",
        "conducting_body": "NTA",
        "exam_date": "May 2026",
        "eligibility": {
            "min_percentage": 50,
            "subjects": ["Physics", "Chemistry", "Biology"],
            "age_limit": "17 years minimum",
            "attempts": "Unlimited"
        },
        "documents_required": [
            "Class 10 Certificate",
            "Class 12 Marksheet",
            "Category Certificate",
            "Photograph",
            "Medical Fitness Certificate"
        ],
        "application_fee": {
            "General": 1700,
            "OBC": 1600,
            "SC/ST": 1000
        },
        "syllabus_url": "https://nta.ac.in/neet",
        "application_url": "https://neet.nta.nic.in"
    },
    {
        "id": 3,
        "name": "CUET UG",
        "name_hi": "CUET UG",
        "full_name": "Common University Entrance Test",
        "conducting_body": "NTA",
        "exam_date": "May 2026",
        "eligibility": {
            "min_percentage": 50,
            "subjects": "Any stream",
            "age_limit": "No age limit",
            "attempts": "Unlimited"
        },
        "documents_required": [
            "Class 12 Marksheet/Admit Card",
            "Category Certificate",
            "Photograph",
            "Signature"
        ],
        "application_fee": {
            "General": 800,
            "OBC": 700,
            "SC/ST": 400
        },
        "syllabus_url": "https://nta.ac.in/cuet",
        "application_url": "https://cuet.nta.nic.in"
    }
]

# ============================================================================
# GUIDED APPLICATION PATHWAYS
# ============================================================================

APPLICATION_STEPS = {
    "scholarship": [
        {
            "step": 1,
            "title": "Check Eligibility",
            "title_hi": "पात्रता जांचें",
            "description": "Verify if you meet percentage, income, and category requirements",
            "description_hi": "जांचें कि क्या आप प्रतिशत, आय और श्रेणी की आवश्यकताओं को पूरा करते हैं",
            "icon": "✓"
        },
        {
            "step": 2,
            "title": "Gather Documents",
            "title_hi": "दस्तावेज़ इकट्ठा करें",
            "description": "Collect marksheet, income certificate, caste certificate, bank details",
            "description_hi": "मार्कशीट, आय प्रमाण पत्र, जाति प्रमाण पत्र, बैंक विवरण एकत्र करें",
            "icon": "📄"
        },
        {
            "step": 3,
            "title": "Register on Portal",
            "title_hi": "पोर्टल पर पंजीकरण करें",
            "description": "Create account on National Scholarship Portal with valid email and mobile",
            "description_hi": "वैध ईमेल और मोबाइल के साथ राष्ट्रीय छात्रवृत्ति पोर्टल पर खाता बनाएं",
            "icon": "👤"
        },
        {
            "step": 4,
            "title": "Fill Application",
            "title_hi": "आवेदन भरें",
            "description": "Complete the form with accurate details. Double-check all entries.",
            "description_hi": "सटीक विवरण के साथ फॉर्म पूरा करें। सभी प्रविष्टियों को दोबारा जांचें।",
            "icon": "✍️"
        },
        {
            "step": 5,
            "title": "Upload Documents",
            "title_hi": "दस्तावेज़ अपलोड करें",
            "description": "Upload scanned copies in PDF/JPG format (Max 2MB each)",
            "description_hi": "PDF/JPG प्रारूप में स्कैन की गई प्रतियां अपलोड करें (प्रत्येक अधिकतम 2MB)",
            "icon": "📤"
        },
        {
            "step": 6,
            "title": "Submit & Track",
            "title_hi": "सबमिट करें और ट्रैक करें",
            "description": "Submit application and save application ID for tracking status",
            "description_hi": "आवेदन जमा करें और स्थिति ट्रैक करने के लिए आवेदन आईडी सहेजें",
            "icon": "✅"
        }
    ]
}

# ============================================================================
# ACADEMIC RULES SIMPLIFIER
# ============================================================================

ACADEMIC_RULES = {
    "attendance": {
        "rule": "Students must maintain 75% attendance to be eligible for exams",
        "simple_explanation": "You need to attend at least 3 out of 4 classes. If there are 100 classes, attend minimum 75.",
        "simple_explanation_hi": "आपको हर 4 में से कम से कम 3 क्लास में उपस्थित होना होगा। अगर 100 क्लास हैं, तो कम से कम 75 में आएं।",
        "consequences": "Less than 75% = Not allowed in semester exams",
        "consequences_hi": "75% से कम = सेमेस्टर परीक्षा में शामिल नहीं हो सकते"
    },
    "grading": {
        "rule": "CGPA to Percentage Conversion: CGPA × 9.5",
        "simple_explanation": "If your CGPA is 8.5, then percentage = 8.5 × 9.5 = 80.75%",
        "simple_explanation_hi": "अगर आपका CGPA 8.5 है, तो प्रतिशत = 8.5 × 9.5 = 80.75%",
        "grade_scale": {
            "O": "90-100%",
            "A+": "80-89%",
            "A": "70-79%",
            "B+": "60-69%",
            "B": "50-59%"
        }
    },
    "backlog": {
        "rule": "Maximum 5 backlogs allowed to proceed to next semester",
        "simple_explanation": "If you fail in more than 5 subjects, you can't move to next semester. Clear backlogs first.",
        "simple_explanation_hi": "अगर 5 से अधिक विषयों में फेल हो गए, तो अगले सेमेस्टर में नहीं जा सकते। पहले बैकलॉग क्लियर करें।"
    }
}

# ============================================================================
# CHATBOT KNOWLEDGE BASE
# ============================================================================

CHATBOT_RESPONSES = {
    'scholarship': {
        'keywords': ['scholarship', 'छात्रवृत्ति', 'financial aid', 'grant', 'funding'],
        'responses': [
            "I can help you find scholarships! 🎓 We have {count} scholarships available. Would you like me to:\n\n1️⃣ Find scholarships based on your details\n2️⃣ Show all available scholarships\n3️⃣ Explain eligibility criteria\n\nJust tell me what you need!",
            "Great question about scholarships! 💰 Here's what I can help with:\n\n✓ Upload your documents for automatic matching\n✓ Manually enter your percentage, income & category\n✓ Browse {count} scholarships by category\n\nWhat would you prefer?",
        ]
    },
    'exam': {
        'keywords': ['exam', 'परीक्षा', 'test', 'jee', 'neet', 'cuet', 'entrance'],
        'responses': [
            "I have information about major entrance exams! 📚\n\n🎯 JEE Main - Engineering (Jan & Apr 2026)\n🩺 NEET UG - Medical (May 2026)\n🎓 CUET UG - Universities (May 2026)\n\nWhich exam would you like to know about?",
        ]
    },
    'documents': {
        'keywords': ['document', 'दस्तावेज़', 'certificate', 'papers', 'proof', 'marksheet', 'income'],
        'responses': [
            "Documents you'll typically need: 📄\n\n✓ Class 10 & 12 Marksheets\n✓ Income Certificate\n✓ Caste Certificate (if applicable)\n✓ Bank Account Details\n✓ Aadhaar Card\n\nNeed help with any specific document?",
        ]
    },
    'eligibility': {
        'keywords': ['eligible', 'पात्र', 'qualify', 'criteria', 'requirement', 'can i apply'],
        'responses': [
            "Let me help check your eligibility! 🎯\n\nI need to know:\n1. Your percentage/CGPA\n2. Annual family income\n3. Category (SC/ST/OBC/General/Minority)\n\nOnce you provide these, I'll show you all scholarships you're eligible for!",
        ]
    },
    'apply': {
        'keywords': ['apply', 'आवेदन', 'application', 'how to', 'process', 'submit'],
        'responses': [
            "Application process made easy! 🗺️\n\nStep 1: Check eligibility ✓\nStep 2: Gather documents 📄\nStep 3: Register on portal 👤\nStep 4: Fill application ✍️\nStep 5: Upload documents 📤\nStep 6: Submit & track 📍\n\nWant detailed guidance?",
        ]
    },
    'deadline': {
        'keywords': ['deadline', 'समय सीमा', 'last date', 'when', 'date', 'time'],
        'responses': [
            "Important deadlines 📅\n\n🔴 Urgent: Most scholarships close by Dec 31, 2025\n🟡 AICTE closes Oct 31\n🟢 Open: Several scholarships accepting applications\n\nUpload your details to see personalized deadlines!",
        ]
    },
    'help': {
        'keywords': ['help', 'मदद', 'guide', 'how', 'what', 'info', 'hi', 'hello', 'hey'],
        'responses': [
            "I'm here to help! 🤖 I can assist with:\n\n🎓 Scholarships - Find & apply\n📚 Exams - JEE, NEET, CUET info\n📄 Documents - Requirements\n✓ Eligibility - Check if you qualify\n\nWhat do you need help with?",
        ]
    }
}

# NEW: Detailed Responses for Context-Aware Chatbot
DETAILED_RESPONSES = {
    'jee_main': """📚 JEE Main Complete Guide:

🎯 **Exam Pattern:**
• Paper 1 (B.E/B.Tech): Physics, Chemistry, Maths (90 questions, 300 marks)
• Paper 2 (B.Arch): Mathematics, Aptitude, Drawing (82 questions, 400 marks)

📅 **Important Dates:**
• Registration: December 2025
• Exam: January & April 2026
• Admit Card: 1 week before exam

✅ **Eligibility:**
• 75% in Class 12 (65% for SC/ST)
• Physics, Chemistry, Maths compulsory
• No age limit

📝 **Application Process:**
1. Visit jeemain.nta.nic.in
2. Register with email/mobile
3. Fill application form
4. Upload photo & signature (JPG, <50KB)
5. Pay fees (₹1000 General, ₹500 SC/ST)
6. Submit & save confirmation

💰 **Fees:**
• General/OBC: ₹1000 (1 paper), ₹1800 (both papers)
• SC/ST/PwD: ₹500 (1 paper), ₹900 (both papers)

📄 **Documents Needed:**
• Class 10 Certificate (DOB proof)
• Class 12 Marksheet
• Category Certificate (if applicable)
• PwD Certificate (if applicable)
• Photograph (3.5 x 4.5 cm)
• Signature specimen

🔗 **Official Website:** https://jeemain.nta.nic.in

Need help with anything specific about JEE Main?""",

    'neet_ug': """🩺 NEET UG Complete Guide:

🎯 **Exam Pattern:**
• Physics: 50 questions (180 marks)
• Chemistry: 50 questions (180 marks)
• Biology (Botany + Zoology): 100 questions (360 marks)
• Total: 200 questions, 720 marks
• Duration: 3 hours 20 minutes

📅 **Important Dates:**
• Registration: March 2026
• Exam: May 2026 (First Sunday)
• Result: June 2026

✅ **Eligibility:**
• 50% in PCB (40% for SC/ST/OBC, 45% for PwD)
• Minimum age: 17 years (as on Dec 31, 2026)
• Upper age: No limit (removed from 2024)

📝 **Application Steps:**
1. Visit neet.nta.nic.in
2. Register & get application number
3. Fill form with accurate details
4. Upload documents (photo, signature, category certificate)
5. Pay fees
6. Print confirmation page

💰 **Application Fees:**
• General/OBC: ₹1,700
• SC/ST/PwD: ₹1,000
• Outside India: ₹9,500

📄 **Required Documents:**
• Class 10 Certificate
• Class 12 Marksheet (PCB)
• Category Certificate (SC/ST/OBC)
• PwD Certificate (if applicable)
• Passport-size photograph
• Signature specimen

🔗 **Official Website:** https://neet.nta.nic.in

Want to know about NEET preparation tips or counseling?""",

    'cuet_ug': """🎓 CUET UG Complete Guide:

🎯 **Exam Pattern:**
• Section IA: Languages (13 options)
• Section IB: Languages (20 options)
• Section II: Domain Subjects (27 subjects, choose max 6)
• Section III: General Test (optional)

📅 **Timeline:**
• Registration: March 2026
• Exam: May 2026
• Result: June 2026

✅ **Eligibility:**
• Passed/Appearing in Class 12
• No percentage criteria
• All streams eligible

📝 **How to Apply:**
1. Visit cuet.nta.nic.in
2. Register with basic details
3. Select universities & courses
4. Choose subjects (based on program requirements)
5. Upload photo & documents
6. Pay fees online
7. Download confirmation

💰 **Fees Structure:**
• 1-4 subjects: ₹800
• 5-9 subjects: ₹1,500
• 10+ subjects: ₹2,000
• SC/ST get ₹400 discount

📄 **Documents:**
• Class 12 Marksheet/Admit Card
• Category Certificate
• Photograph (recent passport size)
• Signature
• EWS Certificate (if applicable)

🎯 **Universities:** 200+ Central, State & Private universities accept CUET

🔗 **Official Website:** https://cuet.nta.nic.in

Which university are you targeting?""",

    'scholarship_apply': """📝 Scholarship Application Complete Guide:

**Step 1: Check Eligibility** ✓
• Verify percentage requirement
• Check income limit
• Confirm category eligibility
• Check class/course requirement

**Step 2: Prepare Documents** 📄
Required documents:
• Latest Marksheet
• Income Certificate (valid for 6 months)
• Caste/Category Certificate
• Aadhaar Card copy
• Bank account details (passbook front page)
• College/School ID
• Bonafide Certificate
• Recent passport-size photos

**Step 3: Register on Portal** 👤
For NSP (National Scholarship Portal):
1. Visit scholarships.gov.in
2. Click "New Registration"
3. Enter mobile & email (verify OTP)
4. Create password
5. Note your Application ID

**Step 4: Fill Application Form** ✍️
Tips:
• Fill in English only
• Double-check all details
• Use BLOCK LETTERS for name
• Match details with documents exactly
• Don't use special characters

**Step 5: Upload Documents** 📤
Format requirements:
• PDF or JPG format only
• Max size: 200KB per document
• Clear, readable scans
• Color scans preferred
• All 4 corners visible

**Step 6: Submit & Track** ✅
After submission:
• Take screenshot of confirmation page
• Note down Application ID
• Save acknowledgment receipt
• Track status regularly
• Keep checking for institute verification

⏰ **Timeline:**
• Application: Oct-Dec usually
• Verification: 1-2 months
• Approval: 2-3 months
• Disbursement: 3-6 months

💡 **Pro Tips:**
• Apply early (don't wait for deadline)
• Keep original documents safe
• Upload clear scans
• Check email regularly for updates
• Contact helpdesk if stuck

Need help with a specific scholarship?""",

    'documents_guide': """📄 Complete Document Requirements Guide:

**For Scholarships:**

1. **Academic Documents** 📚
   • Latest Marksheet (semester/annual)
   • Previous year marksheet
   • College/School bonafide certificate
   • Admission receipt/fee receipt
   • ID Card (student)

2. **Income Proof** 💰
   • Income Certificate from Tehsildar (valid 6 months)
   • OR Income Tax Return (ITR)
   • OR Salary slips (last 6 months)
   • Important: Must be in parent's name

3. **Category Certificates** 🏷️
   • SC/ST Certificate (lifetime validity)
   • OBC Certificate (valid 1 year, non-creamy layer)
   • EWS Certificate (valid 1 year)
   • Minority Certificate (if applicable)
   • PwD Certificate (40%+ disability)

4. **Identity Proof** 🆔
   • Aadhaar Card (mandatory)
   • Voter ID (optional)
   • Passport (if available)
   • Ration Card

5. **Bank Details** 🏦
   • Bank passbook front page copy
   • IFSC Code clearly visible
   • Account holder: Student's name
   • Account type: Savings

6. **Address Proof** 🏠
   • Domicile Certificate
   • Ration Card
   • Electricity Bill
   • Rent Agreement

**For Entrance Exams:**

1. **Age Proof** 📅
   • Class 10 Certificate (most important)
   • Birth Certificate
   • School leaving certificate

2. **Academic Proof** 📖
   • Class 12 Marksheet (original + photocopy)
   • Class 10 Certificate
   • Migration Certificate (if applicable)

3. **Category Proof** 📋
   • SC/ST/OBC Certificate
   • EWS Certificate
   • PwD Certificate (40%+)

4. **Digital Documents** 💾
   • Passport-size photograph (3.5 x 4.5 cm, white background)
   • Signature specimen (on white paper, black ink)
   • Scanned copies (PDF/JPG, <200KB)

**📍 Where to Get:**

• **Income Certificate:**
  Visit: Tehsil Office/Revenue Office
  Documents needed: Ration card, property details, salary slips
  Time: 7-15 days
  Fee: ₹20-50

• **Caste Certificate:**
  Visit: Tehsil Office
  Documents: Birth certificate, parents' caste certificate, Aadhaar
  Time: 15-30 days
  Fee: Free

• **EWS Certificate:**
  Visit: Tehsil/District Office
  Valid for: 1 year
  Time: 7-15 days

💡 **Pro Tips:**
• Make 10 photocopies of each document
• Get documents attested by gazetted officer
• Keep originals in plastic folder
• Scan all documents and save digitally
• Check expiry dates regularly

Which document do you need help getting?"""
}

# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def allowed_file(filename):
    """Check if file extension is allowed"""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def process_pdf(filepath):
    """Convert PDF to images and extract text - NEW"""
    if not PDF_SUPPORT:
        raise Exception("PDF support not available. Install: pip3 install pdf2image")
    
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
    """Enhanced image preprocessing for better OCR accuracy"""
    try:
        img_array = np.array(image)
        
        if len(img_array.shape) == 3:
            gray = cv2.cvtColor(img_array, cv2.COLOR_RGB2GRAY)
        else:
            gray = img_array
        
        denoised = cv2.fastNlMeansDenoising(gray, None, 10, 7, 21)
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8,8))
        enhanced = clahe.apply(denoised)
        thresh = cv2.threshold(enhanced, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)[1]
        kernel = np.ones((1, 1), np.uint8)
        opening = cv2.morphologyEx(thresh, cv2.MORPH_OPEN, kernel)
        
        return Image.fromarray(opening)
    except Exception as e:
        logger.error(f"Image preprocessing error: {str(e)}")
        return image

def extract_data(text):
    """Enhanced data extraction with multiple pattern matching"""
    data = {
        "percentage": None,
        "income": None,
        "category": None,
        "name": None
    }
    
    # Extract name
    name_patterns = [
        r'name[:\s]+([A-Za-z\s]+?)(?:\n|percentage|marks|class)',
        r'student[:\s]+([A-Za-z\s]+?)(?:\n|percentage)',
        r'naam[:\s]+([A-Za-z\s]+?)(?:\n|percentage)'
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
        r'grade[:\s]+(\d+\.?\d*)'
    ]
    for pattern in percentage_patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            value = float(match.group(1))
            if value <= 10:
                data["percentage"] = value * 9.5
            else:
                data["percentage"] = value
            break
    
    # Extract income
    income_patterns = [
        r'income[:\s]+₹?\s*(\d+)',
        r'annual\s+income[:\s]+₹?\s*(\d+)',
        r'₹\s*(\d+)',
        r'(\d{5,7})\s*/-',
        r'salary[:\s]+(\d+)'
    ]
    for pattern in income_patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            data["income"] = int(match.group(1))
            break
    
    # Extract category
    categories = {
        "SC": ["sc", "schedule caste", "scheduled caste"],
        "ST": ["st", "schedule tribe", "scheduled tribe"],
        "OBC": ["obc", "other backward", "backward class"],
        "General": ["general", "gen"],
        "Minority": ["minority", "muslim", "christian", "sikh", "buddhist", "jain", "parsi"]
    }
    
    text_lower = text.lower()
    for category, keywords in categories.items():
        if any(keyword in text_lower for keyword in keywords):
            data["category"] = category
            break
    
    return data

def match_scholarships(student_data):
    """Enhanced scholarship matching with stream and state filtering - UPDATED"""
    matched = []
    
    for scholarship in SCHOLARSHIPS:
        eligibility_score = 0
        reasons = []
        max_score = 3
        
        # Check percentage
        if student_data.get("percentage"):
            if student_data["percentage"] >= scholarship["min_percentage"]:
                eligibility_score += 1
                reasons.append(f"✓ Percentage requirement met ({student_data['percentage']:.1f}% >= {scholarship['min_percentage']}%)")
            else:
                continue
        
        # Check income
        if student_data.get("income"):
            if student_data["income"] <= scholarship["max_income"]:
                eligibility_score += 1
                reasons.append(f"✓ Income eligible (₹{student_data['income']:,} <= ₹{scholarship['max_income']:,})")
            else:
                continue
        
        # Check category
        if student_data.get("category"):
            if student_data["category"] in scholarship["category"]:
                eligibility_score += 1
                reasons.append(f"✓ Category matches ({student_data['category']})")
            else:
                continue
        
        # NEW: Check stream
        if student_data.get("stream"):
            eligible_streams = scholarship.get("eligible_streams", ["All"])
            if "All" not in eligible_streams and student_data["stream"] not in eligible_streams:
                continue
            if "All" not in eligible_streams:
                reasons.append(f"✓ Stream eligible ({student_data['stream']})")
        
        # NEW: Check state
        if student_data.get("state"):
            eligible_states = scholarship.get("states", ["All States"])
            if "All States" not in eligible_states and student_data["state"] not in eligible_states:
                continue
            if "All States" not in eligible_states:
                reasons.append(f"✓ State eligible ({student_data['state']})")
        
        match_percentage = (eligibility_score / max_score) * 100
        
        scholarship_copy = scholarship.copy()
        scholarship_copy["eligibility_score"] = eligibility_score
        scholarship_copy["match_percentage"] = round(match_percentage, 1)
        scholarship_copy["match_reasons"] = reasons
        
        # Calculate days until deadline
        try:
            deadline_date = datetime.strptime(scholarship["deadline"], "%d-%m-%Y")
            days_left = (deadline_date - datetime.now()).days
            scholarship_copy["days_until_deadline"] = days_left
            
            if days_left < 7:
                scholarship_copy["urgency"] = "high"
            elif days_left < 30:
                scholarship_copy["urgency"] = "medium"
            else:
                scholarship_copy["urgency"] = "low"
        except:
            scholarship_copy["days_until_deadline"] = None
            scholarship_copy["urgency"] = "unknown"
        
        matched.append(scholarship_copy)
    
    # Sort by match quality first, then by amount
    # Higher match percentage + higher amount = better match
    matched.sort(key=lambda x: (
        -x.get("match_percentage", 0),  # Higher match % first
        -x.get("amount", 0),  # Higher amount second
        x.get("days_until_deadline", 9999) if x.get("days_until_deadline") else 9999  # Urgent deadlines first
    ))
    
    return matched

def calculate_statistics(matched_scholarships):
    """Calculate statistics for matched scholarships"""
    if not matched_scholarships:
        return {
            "total_amount": 0,
            "avg_amount": 0,
            "highest_scholarship": None,
            "urgent_count": 0
        }
    
    total_amount = sum(s["amount"] for s in matched_scholarships)
    avg_amount = total_amount // len(matched_scholarships)
    highest = max(matched_scholarships, key=lambda x: x["amount"])
    urgent = sum(1 for s in matched_scholarships if s.get("urgency") == "high")
    
    return {
        "total_amount": total_amount,
        "avg_amount": avg_amount,
        "highest_scholarship": highest["name"],
        "highest_amount": highest["amount"],
        "urgent_count": urgent
    }

# ============================================================================
# API ROUTES
# ============================================================================



@app.route('/exams', methods=['GET'])
def get_exams():
    """Get exam information"""
    try:
        exam_name = request.args.get('name')
        language = request.args.get('language', 'en')
        
        if exam_name:
            exam = next((e for e in EXAMS_INFO if e['name'].lower() == exam_name.lower()), None)
            if exam:
                return jsonify({
                    "success": True,
                    "exam": exam
                }), 200
            else:
                return jsonify({
                    "success": False,
                    "error": "Exam not found"
                }), 404
        
        return jsonify({
            "success": True,
            "exams": EXAMS_INFO
        }), 200
    
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

@app.route('/guidance/<path_type>', methods=['GET'])
def get_guidance(path_type):
    """Get guided pathway steps"""
    try:
        language = request.args.get('language', 'en')
        
        if path_type not in APPLICATION_STEPS:
            return jsonify({
                "success": False,
                "error": "Invalid pathway type"
            }), 400
        
        steps = APPLICATION_STEPS[path_type]
        
        return jsonify({
            "success": True,
            "pathway": path_type,
            "steps": steps,
            "language": language
        }), 200
    
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

@app.route('/simplify-rule', methods=['POST'])
def simplify_rule():
    """Simplify academic rules"""
    try:
        data = request.json
        rule_type = data.get('rule_type')
        language = data.get('language', 'en')
        
        if rule_type not in ACADEMIC_RULES:
            return jsonify({
                "success": False,
                "error": "Rule type not found"
            }), 404
        
        rule = ACADEMIC_RULES[rule_type]
        
        if language == 'hi' and f'simple_explanation_{language}' in rule:
            explanation = rule[f'simple_explanation_{language}']
        else:
            explanation = rule['simple_explanation']
        
        return jsonify({
            "success": True,
            "rule_type": rule_type,
            "original_rule": rule['rule'],
            "simplified": explanation,
            "language": language
        }), 200
    
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

@app.route('/statistics', methods=['GET'])
def get_statistics():
    """Get overall platform statistics"""
    try:
        by_category = {}
        for scholarship in SCHOLARSHIPS:
            for cat in scholarship["category"]:
                by_category[cat] = by_category.get(cat, 0) + 1
        
        return jsonify({
            "success": True,
            "total_scholarships": len(SCHOLARSHIPS),
            "total_exams": len(EXAMS_INFO),
            "supported_languages": len(SUPPORTED_LANGUAGES),
            "scholarships_by_category": by_category
        }), 200
    
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500
    
    # ============================================================================
# INTELLIGENT CHATBOT WITH CONTEXT AWARENESS - RAG STYLE
# ============================================================================

# Enhanced Knowledge Base
WEBSITE_HELP_KB = {
    "how_to_use": """
    **How to Use ScholarConnect:**
    
    1️⃣ **Document Scan**: Upload your marksheet/documents (PDF/Image)
    2️⃣ **Manual Entry**: Enter details manually if you don't have documents
    3️⃣ **Results**: Get matched scholarships instantly
    4️⃣ **Apply**: Follow step-by-step application guidance
    
    **Quick Tips:**
    - Use OCR for automatic data extraction
    - Check eligibility before applying
    - Bookmark important scholarships
    - Track application deadlines
    """,
    
    "upload_document": """
    **How to Upload Documents:**
    
    ✅ **Supported Formats**: JPG, PNG, PDF
    ✅ **Max Size**: 10MB
    
    **Steps:**
    1. Click "Document Scan" tab
    2. Click "Upload" button
    3. Select your marksheet/income certificate
    4. Wait for OCR processing (5-10 seconds)
    5. Review extracted data
    6. See matched scholarships
    
    **Tips for Best Results:**
    - Use clear, well-lit images
    - Ensure text is readable
    - PDF files work great too!
    """,
    
    "eligibility_check": """
    **Check Your Eligibility:**
    
    We need 3 things:
    1️⃣ **Percentage/CGPA** (We auto-convert CGPA to %)
    2️⃣ **Annual Family Income** (in ₹)
    3️⃣ **Category** (SC/ST/OBC/General/Minority)
    
    **How it Works:**
    - System matches your details with 10+ scholarships
    - Shows only scholarships you qualify for
    - Displays eligibility score for each
    - Highlights urgent deadlines
    
    **Example:**
    - 75% marks, ₹3L income, General → 4-5 scholarships
    - 85% marks, ₹4L income, OBC → 6-8 scholarships
    """,
    
    "scholarships_info": """
    **Available Scholarships (10+):**
    
    🎓 **Pre-Matric (Class 9-10)**
    - SC/ST Pre-Matric: ₹20,000
    
    📚 **Post-Matric (Class 11+)**
    - SC/ST Post-Matric: ₹50,000
    - OBC Scholarship: ₹30,000
    - Merit-cum-Means: ₹50,000
    
    🏆 **Merit-Based**
    - National Merit (80%+): ₹1,00,000
    - INSPIRE (85%+): ₹80,000
    
    👧 **For Girls**
    - AICTE Pragati: ₹50,000
    
    💡 **Special**
    - PMSS (Ex-Servicemen): ₹36,000
    - Minorities: ₹15,000
    - NMMS (Class 9-12): ₹12,000
    """,
    
    "application_process": """
    **Scholarship Application Process:**
    
    **Step 1: Check Eligibility** ✅
    - Verify percentage requirement
    - Check income limit
    - Confirm category
    
    **Step 2: Gather Documents** 📄
    - Marksheet (latest)
    - Income Certificate (valid 6 months)
    - Caste Certificate (if applicable)
    - Bank details (passbook copy)
    - Aadhaar Card
    
    **Step 3: Register on Portal** 👤
    - Visit scholarships.gov.in
    - Create account with email/mobile
    - Note down Application ID
    
    **Step 4: Fill Form** ✍️
    - Enter accurate details
    - Double-check spelling
    - Use CAPITAL LETTERS for name
    
    **Step 5: Upload Documents** 📤
    - PDF/JPG format only
    - Max 200KB per file
    - Clear, readable scans
    
    **Step 6: Submit & Track** 📍
    - Save confirmation page
    - Track status regularly
    - Check email for updates
    
    **Timeline:** 
    Application → 1-2 months verification → 3-6 months disbursement
    """,
    
    "documents_required": """
    **Documents Needed for Scholarships:**
    
    📋 **Academic:**
    - Latest Marksheet
    - Previous year marksheet
    - School/College ID
    - Bonafide certificate
    
    💰 **Income Proof:**
    - Income Certificate (Tehsildar, valid 6 months)
    OR
    - ITR (Income Tax Return)
    OR
    - Salary slips (last 6 months)
    
    🆔 **Category Proof:**
    - SC/ST Certificate (lifetime valid)
    - OBC Certificate (valid 1 year, non-creamy layer)
    - EWS Certificate (valid 1 year)
    - Minority Certificate
    
    🏦 **Bank Details:**
    - Passbook front page copy
    - IFSC code visible
    - Account in student's name
    
    🪪 **Identity:**
    - Aadhaar Card (mandatory)
    - Voter ID (optional)
    
    **Where to Get:**
    - Income/Caste Certificate: Tehsil Office (7-30 days, ₹20-50)
    - Bank passbook: Your bank branch
    """,
    
    "exam_information": """
    **Entrance Exams Information:**
    
    🎯 **JEE Main** (Engineering)
    - Date: Jan & Apr 2026
    - Subjects: Physics, Chemistry, Maths
    - Eligibility: 75% in Class 12
    - Fee: ₹1000 (General), ₹500 (SC/ST)
    - Website: jeemain.nta.nic.in
    
    🩺 **NEET UG** (Medical)
    - Date: May 2026
    - Subjects: Physics, Chemistry, Biology
    - Eligibility: 50% in Class 12
    - Fee: ₹1700 (General), ₹1000 (SC/ST)
    - Website: neet.nta.nic.in
    
    🎓 **CUET UG** (Universities)
    - Date: May 2026
    - Subjects: Domain + Language + General
    - Eligibility: Any stream
    - Fee: ₹800 (General), ₹400 (SC/ST)
    - Website: cuet.nta.nic.in
    """,
    
    "troubleshooting": """
    **Common Issues & Solutions:**
    
    ❌ **Problem:** OCR not extracting data correctly
    ✅ **Solution:** 
    - Use clearer image with good lighting
    - Try PDF format instead
    - Use manual entry as backup
    
    ❌ **Problem:** No scholarships matched
    ✅ **Solution:**
    - Check if percentage meets minimum (usually 50%+)
    - Verify income limit
    - Try different category if applicable
    
    ❌ **Problem:** Upload failing
    ✅ **Solution:**
    - File size under 10MB
    - Use supported formats (JPG/PNG/PDF)
    - Check internet connection
    
    ❌ **Problem:** Can't find specific scholarship
    ✅ **Solution:**
    - Use Manual Entry with your exact details
    - Browse all scholarships in Scholarships tab
    - Contact support via chatbot
    """
}

@app.route('/chatbot', methods=['POST', 'OPTIONS'])
def chatbot_query():
    """Enhanced RAG-style chatbot with context awareness"""
    if request.method == 'OPTIONS':
        return jsonify({"success": True}), 200
    
    try:
        data = request.json
        query = data.get('query', '').lower()
        user_id = data.get('user_id', 'default')
        language = data.get('language', 'en')
        
        if not query:
            return jsonify({"success": False, "error": "No query provided"}), 400
        
        # Initialize conversation history
        if user_id not in conversation_history:
            conversation_history[user_id] = []
        
        # Add current query to history
        conversation_history[user_id].append(query)
        if len(conversation_history[user_id]) > 10:
            conversation_history[user_id] = conversation_history[user_id][-10:]
        
        recent_context = ' '.join(conversation_history[user_id])
        response = ""
        context_type = "general"
        
        # ===== INTELLIGENT KEYWORD MATCHING =====
        
        # How to use website
        if any(word in query for word in ['how to use', 'how do i', 'kaise use', 'website kaise', 'guide', 'tutorial']):
            response = WEBSITE_HELP_KB["how_to_use"]
            context_type = "how_to_use"
        
        # Upload/OCR help
        elif any(word in query for word in ['upload', 'ocr', 'scan', 'document', 'marksheet', 'kaise upload', 'file upload']):
            response = WEBSITE_HELP_KB["upload_document"]
            context_type = "upload"
        
        # Eligibility checking
        elif any(word in query for word in ['eligibility', 'eligible', 'qualify', 'criteria', 'check', 'requirement', 'patr']):
            response = WEBSITE_HELP_KB["eligibility_check"]
            context_type = "eligibility"
        
        # Scholarships information
        elif any(word in query for word in ['scholarship', 'scholarships', 'amount', 'money', 'financial aid', 'chatrvritti']):
            response = WEBSITE_HELP_KB["scholarships_info"]
            context_type = "scholarships"
        
        # Application process
        elif any(word in query for word in ['apply', 'application', 'process', 'how to apply', 'steps', 'avedan']):
            response = WEBSITE_HELP_KB["application_process"]
            context_type = "application"
        
        # Documents required
        elif any(word in query for word in ['document', 'documents', 'certificate', 'required', 'need', 'dastavez']):
            response = WEBSITE_HELP_KB["documents_required"]
            context_type = "documents"
        
        # Exam information
        elif any(word in query for word in ['exam', 'jee', 'neet', 'cuet', 'entrance', 'test', 'pariksha']):
            response = WEBSITE_HELP_KB["exam_information"]
            context_type = "exams"
        
        # Troubleshooting
        elif any(word in query for word in ['error', 'problem', 'issue', 'not working', 'help', 'support', 'samasya']):
            response = WEBSITE_HELP_KB["troubleshooting"]
            context_type = "troubleshooting"
        
        # Specific questions
        elif 'deadline' in query or 'last date' in query:
            response = """
            **Important Deadlines:**
            
            🔴 **Urgent (Closing Soon):**
            - AICTE Pragati: 31 Oct 2025
            - National Merit: 31 Oct 2025
            
            🟡 **This Month:**
            - NMMS: 30 Nov 2025
            - PMSS: 15 Nov 2025
            
            🟢 **Coming Up:**
            - Most NSP Scholarships: 31 Dec 2025
            - INSPIRE: 31 Dec 2025
            - OBC Scholarship: 15 Jan 2026
            
            💡 **Pro Tip:** Don't wait! Apply early to avoid last-minute rush.
            """
            context_type = "deadlines"
        
        elif 'income certificate' in query or 'certificate kaise' in query:
            response = """
            **How to Get Income Certificate:**
            
            📍 **Where:** Visit Tehsil Office / Revenue Office
            
            📄 **Documents Needed:**
            - Aadhaar Card
            - Ration Card
            - Property details (if any)
            - Salary slips (if salaried)
            
            ⏱️ **Time:** 7-15 days
            💰 **Fee:** ₹20-50
            
            **Steps:**
            1. Download application form from office or online
            2. Fill with family income details
            3. Attach required documents
            4. Submit at Tehsil Office
            5. Get acknowledgment receipt
            6. Collect certificate after 7-15 days
            
            **Validity:** 6 months for scholarships
            
            **Online Option (if available in your state):**
            - Visit state e-district portal
            - Apply online with digital documents
            - Track application status
            """
            context_type = "income_certificate"
        
        elif 'category' in query or 'caste' in query:
            response = """
            **Category Certificates:**
            
            **SC/ST Certificate:**
            - Where: Tehsil Office
            - Validity: Lifetime
            - Time: 15-30 days
            - Fee: Free
            - Documents: Birth certificate, Parents' caste certificate
            
            **OBC Certificate:**
            - Where: Tehsil Office
            - Validity: 1 year (need renewal)
            - Must be: Non-Creamy Layer
            - Annual income: < ₹8 lakh
            
            **EWS Certificate:**
            - For: General category (income < ₹8 lakh)
            - Validity: 1 year
            - Renewal: Every year
            
            **Minority Certificate:**
            - For: Muslim, Christian, Sikh, Buddhist, Jain, Parsi
            - Where: District Office
            """
            context_type = "category_certificate"
        
        # Default fallback
        else:
            response = """
            👋 **Hi! I'm your ScholarConnect Assistant!**
            
            I can help you with:
            
            🎯 **Quick Help:**
            - "How to use this website?"
            - "How to upload documents?"
            - "Check my eligibility"
            - "Show me scholarships"
            - "Application process"
            - "Documents required"
            - "Exam information"
            - "Troubleshoot issues"
            
            💡 **Try asking:**
            - "How do I apply for scholarships?"
            - "What documents do I need?"
            - "Tell me about JEE exam"
            - "How to get income certificate?"
            - "Scholarship deadlines"
            
            Just type your question and I'll help! 😊
            """
            context_type = "welcome"
        
        # Track conversation context
        conversation_history[user_id].append(f"answered:{context_type}")
        
        return jsonify({
            "success": True,
            "query": query,
            "response": response,
            "language": language,
            "context_type": context_type,
            "conversation_length": len(conversation_history[user_id])
        }), 200
    
    except Exception as e:
        logger.error(f"Chatbot error: {str(e)}")
        return jsonify({"success": False, "error": str(e)}), 500


# ============================================================================
# NEW ENDPOINTS FOR FRONTEND
# ============================================================================

@app.route('/api/dashboard/stats', methods=['GET'])
def dashboard_stats():
    """Get dashboard statistics - NEW"""
    try:
        by_category = {}
        for scholarship in SCHOLARSHIPS:
            for cat in scholarship["category"]:
                by_category[cat] = by_category.get(cat, 0) + 1
        
        total_amount = sum(s["amount"] for s in SCHOLARSHIPS)
        
        urgent_count = 0
        for s in SCHOLARSHIPS:
            try:
                deadline_date = datetime.strptime(s["deadline"], "%d-%m-%Y")
                days_left = (deadline_date - datetime.now()).days
                if days_left < 30:
                    urgent_count += 1
            except:
                pass
        
        return jsonify({
            "success": True,
            "stats": {
                "total_scholarships": len(SCHOLARSHIPS),
                "total_amount": total_amount,
                "scholarships_by_category": by_category,
                "urgent_deadlines": urgent_count,
                "supported_languages": len(SUPPORTED_LANGUAGES),
                "total_exams": len(EXAMS_INFO),
                "pdf_support": PDF_SUPPORT
            }
        }), 200
    
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

@app.route('/api/user/bookmarks', methods=['GET', 'POST', 'DELETE'])
def user_bookmarks_api():
    """Manage user bookmarks - NEW"""
    user_id = request.args.get('user_id', 'default')
    
    if request.method == 'GET':
        bookmarks = user_bookmarks.get(user_id, [])
        return jsonify({
            "success": True,
            "bookmarks": bookmarks
        }), 200
    
    elif request.method == 'POST':
        data = request.json
        scholarship_id = data.get('scholarship_id')
        
        if user_id not in user_bookmarks:
            user_bookmarks[user_id] = []
        
        if scholarship_id not in user_bookmarks[user_id]:
            user_bookmarks[user_id].append(scholarship_id)
        
        return jsonify({
            "success": True,
            "message": "Bookmark added"
        }), 200
    
    elif request.method == 'DELETE':
        scholarship_id = request.args.get('scholarship_id')
        
        if user_id in user_bookmarks and scholarship_id:
            if scholarship_id in user_bookmarks[user_id]:
                user_bookmarks[user_id].remove(scholarship_id)
        
        return jsonify({
            "success": True,
            "message": "Bookmark removed"
        }), 200

@app.route('/api/filters', methods=['GET'])
def get_filters():
    """Get available filter options - NEW"""
    categories = set()
    streams = set()
    states = set()
    
    for s in SCHOLARSHIPS:
        categories.update(s["category"])
        if "eligible_streams" in s:
            streams.update(s["eligible_streams"])
        if "states" in s:
            states.update(s["states"])
    
    return jsonify({
        "success": True,
        "filters": {
            "categories": sorted(list(categories)),
            "streams": sorted(list(streams)),
            "states": sorted(list(states))
        }
    }), 200

@app.route('/generate-study-plan', methods=['POST', 'OPTIONS'])
def generate_study_plan():
    """Generate personalized study plan/routine for a specific exam and strategy"""
    
    if request.method == 'OPTIONS':
        return jsonify({"success": True}), 200
    
    try:
        data = request.json
        exam_id = data.get('exam_id')
        exam_name = data.get('exam_name')
        strategy_type = data.get('strategy_type')
        
        if not exam_id or not exam_name or not strategy_type:
            return jsonify({
                "success": False,
                "error": "Missing required fields: exam_id, exam_name, strategy_type"
            }), 400
        
        # Get exam details
        exam = next((e for e in EXAMS_INFO if e['id'] == exam_id), None)
        if not exam:
            return jsonify({
                "success": False,
                "error": "Exam not found"
            }), 404
        
        # Generate study plan based on strategy type
        study_plan = generate_strategy_plan(exam, strategy_type)
        
        strategy_names = {
            'study-plan': 'Study Plan',
            'practice': 'Practice Schedule',
            'weak-areas': 'Weak Areas Strategy',
            'revision': 'Revision Strategy',
            'time-management': 'Time Management Plan',
            'stress-management': 'Stress Management Guide'
        }
        
        return jsonify({
            "success": True,
            "exam_name": exam_name,
            "strategy_type": strategy_type,
            "strategy_name": strategy_names.get(strategy_type, 'Study Plan'),
            "study_plan": study_plan
        }), 200
    
    except Exception as e:
        logger.error(f"Error generating study plan: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

def generate_strategy_plan(exam, strategy_type):
    """Generate detailed study plan based on exam and strategy type"""
    
    exam_name = exam.get('name', '').upper()
    
    if strategy_type == 'study-plan':
        if 'JEE' in exam_name:
            return generate_jee_study_plan()
        elif 'NEET' in exam_name:
            return generate_neet_study_plan()
        elif 'CUET' in exam_name:
            return generate_cuet_study_plan()
        else:
            return generate_generic_study_plan(exam)
    
    elif strategy_type == 'practice':
        if 'JEE' in exam_name:
            return generate_jee_practice_schedule()
        elif 'NEET' in exam_name:
            return generate_neet_practice_schedule()
        else:
            return generate_generic_practice_schedule(exam)
    
    elif strategy_type == 'weak-areas':
        return generate_weak_areas_strategy(exam)
    
    elif strategy_type == 'revision':
        return generate_revision_strategy(exam)
    
    elif strategy_type == 'time-management':
        return generate_time_management_plan(exam)
    
    elif strategy_type == 'stress-management':
        return generate_stress_management_guide()
    
    else:
        return "Study plan generation for this strategy is coming soon!"

def generate_jee_study_plan():
    """Generate JEE Main study plan"""
    return """
**JEE MAIN COMPLETE STUDY PLAN (6 Months)**

### **Daily Routine (8-10 hours)**
- **Morning (4 hours):** Physics & Mathematics (Strong subjects)
- **Afternoon (2 hours):** Chemistry (Theory + Problems)
- **Evening (2-3 hours):** Weak topics revision
- **Night (1 hour):** Previous day revision

### **Weekly Schedule**

**Monday - Wednesday:** Physics
- Mechanics (3 days)
- Thermodynamics (2 days)
- Waves & Optics (2 days)

**Thursday - Saturday:** Mathematics
- Algebra & Trigonometry (2 days)
- Calculus (3 days)
- Coordinate Geometry (2 days)

**Sunday:** Chemistry
- Physical Chemistry (Morning)
- Organic Chemistry (Afternoon)
- Inorganic Chemistry (Evening)

### **Monthly Breakdown**

**Month 1-2: Foundation Phase**
- Complete NCERT thoroughly
- Cover all basic concepts
- Solve 100 problems per subject per week

**Month 3-4: Strengthening Phase**
- Advanced topics
- Previous year papers
- Mock tests (1 per week)

**Month 5: Intensive Practice**
- 2-3 mock tests per week
- Focus on speed & accuracy
- Identify weak areas

**Month 6: Revision & Mock Tests**
- Complete syllabus revision
- 1 mock test daily
- Analyze mistakes
- Focus on formula revision

### **Important Topics Priority**
**Physics:** Mechanics (40%), Electricity & Magnetism (30%), Modern Physics (20%)
**Mathematics:** Calculus (35%), Algebra (25%), Coordinate Geometry (20%)
**Chemistry:** Organic (40%), Physical (35%), Inorganic (25%)

### **Study Tips**
✓ Study in 45-minute blocks with 10-minute breaks
✓ Revise formulas daily before sleep
✓ Maintain a formula book
✓ Solve minimum 50 problems daily
✓ Weekly mock tests are mandatory
"""

def generate_neet_study_plan():
    """Generate NEET study plan"""
    return """
**NEET UG COMPLETE STUDY PLAN (6 Months)**

### **Daily Routine (10-12 hours)**
- **Morning (4-5 hours):** Biology (Theory + Diagrams)
- **Afternoon (3-4 hours):** Physics (Problems)
- **Evening (3 hours):** Chemistry (Theory + NCERT)

### **Weekly Schedule**

**Monday, Wednesday, Friday:** Biology Focus
- Botany (Morning)
- Zoology (Afternoon)
- NCERT Revision (Evening)

**Tuesday, Thursday, Saturday:** Physics & Chemistry
- Physics (Morning - 3 hours)
- Chemistry (Afternoon - 3 hours)
- Mixed Problems (Evening)

**Sunday:** Revision Day
- Weekly revision of all subjects
- Previous year questions
- Mock test

### **Monthly Breakdown**

**Month 1-2: NCERT Foundation**
- Complete NCERT Biology (Class 11 & 12)
- Physics: Mechanics & Thermodynamics
- Chemistry: Physical & Organic basics

**Month 3-4: Advanced Topics**
- Biology: Genetics, Ecology, Human Physiology
- Physics: Electricity, Magnetism, Optics
- Chemistry: Complete Organic & Inorganic

**Month 5: Practice Phase**
- Daily: 200 Biology MCQs
- Daily: 100 Physics problems
- Daily: 100 Chemistry problems
- 2 Mock tests per week

**Month 6: Final Preparation**
- Complete syllabus revision 3 times
- 1 Mock test daily
- NCERT revision (minimum 3 times)
- Formula & concept revision

### **Biology Priority Topics (High Weightage)**
1. Genetics & Evolution (15%)
2. Human Physiology (20%)
3. Plant Physiology (10%)
4. Ecology (12%)
5. Cell Biology (10%)
6. Reproduction (8%)

### **Study Tips**
✓ Read NCERT Biology 3-4 times minimum
✓ Draw diagrams daily
✓ Make flash cards for biology facts
✓ Solve previous 10 years papers
✓ Maintain separate notes for important points
"""

def generate_cuet_study_plan():
    """Generate CUET study plan"""
    return """
**CUET UG COMPLETE STUDY PLAN**

### **Strategy Overview**
CUET tests your Class 12 knowledge. Focus on NCERT and conceptual clarity.

### **Daily Routine (6-8 hours)**
- **Morning (3-4 hours):** Domain subjects
- **Afternoon (2-3 hours):** Language & General Test
- **Evening (1-2 hours):** Revision

### **Subject-wise Approach**

**Domain Subjects (Choose 3-6 subjects):**
1. **English:** Vocabulary, Grammar, Reading Comprehension
2. **Domain Subjects:** NCERT Class 12 thoroughly
3. **General Test:** Current Affairs, Quantitative Aptitude, Logical Reasoning

### **3-Month Plan**

**Month 1: Subject Mastery**
- Complete NCERT Class 12 (all subjects)
- Start practicing MCQs
- Build vocabulary (10 words daily)

**Month 2: Practice & Application**
- Previous year papers
- Mock tests weekly
- Focus on speed (1 minute per question)

**Month 3: Revision & Mock Tests**
- Complete revision
- Daily mock tests
- Error analysis
- Time management practice

### **General Test Preparation**
- **Current Affairs:** Last 6 months news
- **Quantitative Aptitude:** Basic math, percentages, ratios
- **Logical Reasoning:** Series, coding-decoding, puzzles

### **Tips for Success**
✓ NCERT is your bible - master it
✓ Time management is crucial (45 seconds/question)
✓ Practice with timer always
✓ Stay updated with current affairs
✓ Focus on accuracy first, then speed
"""

def generate_generic_study_plan(exam):
    """Generate generic study plan for other exams"""
    return f"""
**STUDY PLAN FOR {exam.get('name', 'EXAM').upper()}**

### **6-Month Preparation Strategy**

**Daily Schedule (8-10 hours)**
- Morning: Core subjects
- Afternoon: Practice & problems
- Evening: Revision

**Key Principles:**
1. Understand syllabus completely
2. Follow a structured timetable
3. Regular revision is essential
4. Mock tests weekly
5. Focus on weak areas

**Month 1-2:** Foundation building
**Month 3-4:** Advanced topics & practice
**Month 5:** Intensive practice & mocks
**Month 6:** Revision & final preparation

Study consistently, take breaks, and stay motivated!
"""

def generate_jee_practice_schedule():
    """Generate JEE practice schedule"""
    return """
**JEE MAIN PRACTICE SCHEDULE**

### **Daily Practice Routine**
- **Morning:** 25 Physics problems (90 minutes)
- **Afternoon:** 25 Mathematics problems (90 minutes)
- **Evening:** 25 Chemistry problems (60 minutes)
- **Night:** Mixed practice (60 minutes)

### **Weekly Mock Test Schedule**
- **Sunday:** Full mock test (3 hours)
- **Monday:** Analyze mock test & weak topics
- **Wednesday:** Subject-wise mock (90 minutes)
- **Saturday:** Previous year paper

### **Practice Sources**
1. Previous 10 years JEE Main papers
2. JEE Advanced papers (for depth)
3. Coaching institute test series
4. NCERT exemplar problems

### **Target Practice**
- Minimum 50 problems daily
- 300+ problems per week
- Complete all previous year papers
- Time-bound practice (speed training)
"""

def generate_neet_practice_schedule():
    """Generate NEET practice schedule"""
    return """
**NEET UG PRACTICE SCHEDULE**

### **Daily Practice Targets**
- **Biology:** 200 MCQs daily (NCERT-based)
- **Physics:** 100 problems daily
- **Chemistry:** 100 MCQs daily

### **Weekly Mock Test Schedule**
- **Sunday:** Full NEET mock test
- **Tuesday:** Biology-only test
- **Thursday:** Physics + Chemistry test
- **Saturday:** Previous year paper

### **Practice Strategy**
1. NCERT exemplar (all questions)
2. Previous 10 years NEET papers
3. AIIMS & JIPMER papers (for practice)
4. Chapter-wise tests

### **Biology Focus**
- Solve NCERT line-by-line
- Diagram-based questions
- Assertion-reason questions
- Match the following

### **Physics & Chemistry**
- Formula-based problems
- Numerical accuracy
- Conceptual clarity
"""

def generate_generic_practice_schedule(exam):
    return f"""
**PRACTICE SCHEDULE FOR {exam.get('name', 'EXAM')}**

### **Daily Practice**
- Solve previous year papers
- Chapter-wise practice
- Time-bound solving

### **Weekly Targets**
- 2-3 full mock tests
- Error analysis
- Weak topic revision

Practice regularly, analyze mistakes, and improve!
"""

def generate_weak_areas_strategy(exam):
    """Generate strategy for weak areas"""
    return """
**STRATEGY TO STRENGTHEN WEAK AREAS**

### **Step 1: Identify Weak Areas**
- Analyze mock test results
- Track mistakes in each topic
- List topics with <60% accuracy

### **Step 2: Prioritize Weak Topics**
- High weightage topics first
- Easy-medium difficulty topics
- Quick win topics

### **Step 3: Action Plan**
1. **Re-learn basics:** Go back to NCERT/fundamentals
2. **Conceptual clarity:** Watch videos, read notes
3. **Practice:** Solve 50+ problems per weak topic
4. **Revision:** Revise weekly until strong

### **Time Allocation**
- Allocate 30% time to weak areas
- Maintain strong areas (40%)
- Mixed practice (30%)

### **Tips**
✓ Don't ignore weak areas - they decide your rank
✓ Start with easier weak topics for confidence
✓ Track improvement weekly
✓ Take help from teachers/online resources
"""

def generate_revision_strategy(exam):
    """Generate revision strategy"""
    return """
**COMPLETE REVISION STRATEGY**

### **3-Tier Revision Plan**

**Tier 1: Quick Revision (Daily - 30 minutes)**
- Yesterday's topics
- Formulas & important points
- Solved problems recap

**Tier 2: Weekly Revision (3-4 hours)**
- Complete week's topics
- Previous year questions
- Mock test analysis

**Tier 3: Complete Revision (Before Exam)**
- Full syllabus 2-3 times
- Formula sheets
- Important topics priority

### **Revision Schedule (Last 2 Months)**

**Month 5:**
- Week 1-2: Physics complete revision
- Week 3-4: Mathematics complete revision
- Week 4: Chemistry complete revision

**Month 6:**
- Week 1-2: Biology complete revision (if applicable)
- Week 3: All subjects mixed revision
- Week 4: Formula & concept revision only

### **Revision Techniques**
1. **Active Recall:** Write without looking
2. **Spaced Repetition:** Revise at increasing intervals
3. **Mind Maps:** Visual representation
4. **Flash Cards:** Quick revision tool
5. **Previous Papers:** Best revision material

### **Formula Revision**
- Revise formulas daily
- Write formulas 3-4 times
- Apply in problems immediately
- Maintain formula sheet
"""

def generate_time_management_plan(exam):
    """Generate time management plan"""
    return """
**TIME MANAGEMENT FOR EXAM PREPARATION**

### **Daily Time Allocation (10 hours)**

**Morning (4 hours - High Energy)**
- 2 hours: Difficult subjects
- 2 hours: Concept learning

**Afternoon (3 hours - Medium Energy)**
- Practice problems
- Solving exercises

**Evening (2 hours - Refreshed)**
- Revision
- Quick notes

**Night (1 hour - Light Study)**
- Formula revision
- Planning next day

### **Weekly Time Distribution**
- Study Days (Monday-Saturday): 10 hours daily
- Revision Day (Sunday): 6-7 hours + Mock test

### **Monthly Planning**
- Week 1: New topics (70%)
- Week 2: New topics (50%) + Practice (50%)
- Week 3: Practice (70%) + Revision (30%)
- Week 4: Mock tests + Revision

### **Time Management Tips**
✓ Use Pomodoro technique (25 min study, 5 min break)
✓ Eliminate distractions (phone, social media)
✓ Set realistic daily goals
✓ Track time spent on each subject
✓ Take regular breaks to maintain focus
✓ Sleep 7-8 hours for optimal performance
"""

def generate_stress_management_guide():
    """Generate stress management guide"""
    return """
**STRESS MANAGEMENT FOR EXAM PREPARATION**

### **Understanding Exam Stress**
It's normal to feel anxious. Channel it positively!

### **Physical Health**

**Sleep:**
- Minimum 7-8 hours daily
- Consistent sleep schedule
- Avoid studying until late night

**Exercise:**
- 30 minutes daily walk/exercise
- Yoga or meditation
- Stretching breaks every 2 hours

**Diet:**
- Balanced meals
- Stay hydrated
- Avoid excessive caffeine
- Healthy snacks

### **Mental Health**

**Positive Mindset:**
- Focus on progress, not perfection
- Celebrate small wins
- Don't compare with others
- Believe in yourself

**Break Routine:**
- Take breaks every 45-60 minutes
- Weekend relaxation (few hours)
- Pursue hobbies occasionally
- Talk to family/friends

### **Study Stress Management**

**When Overwhelmed:**
1. Take deep breaths (5 minutes)
2. Break tasks into smaller chunks
3. Start with easier topics
4. Ask for help when needed

**Before Exam:**
- Trust your preparation
- Don't study new topics
- Revise only
- Stay calm and confident

### **Support System**
- Talk to parents/teachers
- Study group discussions
- Professional help if needed
- Remember: This too shall pass!

**You've got this! Stay strong, stay positive! 💪**
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
    print("\n" + "="*70)
    print("🎓 SCHOLARCONNECT PRO - AI-POWERED MULTILINGUAL PLATFORM")
    print("="*70)
    print(f"✓ Server: http://localhost:5000")
    print(f"✓ Health Check: http://localhost:5000/health")
    print(f"✓ Dashboard: http://localhost:5000/api/dashboard/stats")
    print(f"✓ Total Scholarships: {len(SCHOLARSHIPS)}")
    print(f"✓ Total Exams: {len(EXAMS_INFO)}")
    print(f"✓ Supported Languages: {len(SUPPORTED_LANGUAGES)}")
    print(f"✓ PDF Support: {'✅ Enabled' if PDF_SUPPORT else '⚠️  Disabled'}")
    print(f"✓ New Features: Stream/State Filtering | Bookmarks | Dashboard")
    print("="*70 + "\n")
    
    if not PDF_SUPPORT:
        print("💡 To enable PDF support:")
        print("   pip3 install pdf2image")
        print("   brew install poppler  # For Mac")
        print()
    
    # Production-ready configuration
    import os
    DEBUG_MODE = os.getenv('FLASK_DEBUG', 'False').lower() == 'true'
    
    app.run(debug=DEBUG_MODE, port=5000, host='0.0.0.0')

