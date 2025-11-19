from pymongo import MongoClient
import os
import json
import bcrypt
from dotenv import load_dotenv
from datetime import datetime

load_dotenv()

MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017/")
client = MongoClient(MONGO_URI)
db = client["citizen_portal"]

# Collections
services_col = db["services"]       # This will store Super Category documents directly
categories_col = db["categories"]   # This will be dynamically populated from services_col if empty
officers_col = db["officers"]
ads_col = db["ads"]
admins_col = db["admins"]

# Clear existing data in relevant collections
print("Clearing existing data...")
services_col.delete_many({})
categories_col.delete_many({}) # Clear this, as it will be dynamically generated or used differently
officers_col.delete_many({})
ads_col.delete_many({})

print("Seeding initial data...")

# Helper function to ensure consistent naming for localized fields
def get_localized_name_obj(en_name, si_name=None, ta_name=None):
    return {"en": en_name, "si": si_name or en_name, "ta": ta_name or en_name}


# --- 1. Seed Officers ---
officers_data = [
    {"id":"off_it_01","name":"Ms. Nayana Perera","role":"Director - Digital Services","ministry_id":"ministry_it","contact":{"email":"nayana@it.gov.lk","phone":"071-1234567"}},
    {"id":"off_public_01","name":"Mr. Ruwan Silva","role":"Assistant Secretary - Public Admin","ministry_id":"ministry_public","contact":{"email":"ruwan@pub.gov.lk","phone":"071-2345678"}},
    {"id":"off_health_01","name":"Dr. Anusha Kumari","role":"Chief Medical Officer","ministry_id":"ministry_health","contact":{"email":"anusha@health.gov.lk","phone":"077-3456789"}},
    {"id":"off_edu_01","name":"Mr. Kamal Priyantha","role":"Education Reforms Director","ministry_id":"ministry_education","contact":{"email":"kamal@edu.gov.lk","phone":"077-4567890"}}
]
officers_col.insert_many(officers_data)
print(f"Seeded {len(officers_data)} officers.")

# --- 2. Seed Ads ---
ads_data = [
    {"id":"ad_courses_01","title":get_localized_name_obj("Free Digital Skills Course", "නොමිලේ ඩිජිටල් කුසලතා පාඨමාලාව", "இலவச டிஜிட்டல் திறன் பாடநெறி"),"body":get_localized_name_obj("Enroll now for government digital skills training. Limited seats.", "රාජ්‍ය ඩිජිටල් කුසලතා පුහුණුව සඳහා දැන්ම ලියාපදිංචි වන්න. ආසන සීමිතයි.", "அரசு டிஜிட்டல் திறன் பயிற்சிக்கு இப்போதே பதிவு செய்யவும். இடங்கள் குறைவு."),
     "link":"https://spacexp.edu.lk/courses","start":None,"end":None,"image":"/static/img/course-card.png", "source":"ad_panel"},
    {"id":"ad_exams_01","title":get_localized_name_obj("Exam Results Portal", "විභාග ප්‍රතිඵල ද්වාරය", "தேர்வு முடிவுகள் போர்டல்"),"body":get_localized_name_obj("Check latest exam results online here.", "නවතම විභාග ප්‍රතිඵල මාර්ගගතව මෙතැනින් පරීක්ෂා කරන්න.", "சமீபத்திய தேர்வு முடிவுகளை ஆன்லைனில் சரிபார்க்கவும்."),
     "link":"https://exam.gov.lk/results", "source":"ad_panel"},
    {"id":"ad_housing_loan","title":get_localized_name_obj("Affordable Housing Loans", "පහසු නිවාස ණය", "மலிவு விலை வீட்டு கடன்கள்"),"body":get_localized_name_obj("Apply for new government housing loan schemes.", "නව රාජ්‍ය නිවාස ණය යෝජනා ක්‍රම සඳහා අයදුම් කරන්න.", "புதிய அரசு வீட்டு கடன் திட்டங்களுக்கு விண்ணப்பிக்கவும்."),
     "link":"https://housing.gov.lk/loans", "source":"ad_panel"}
]
ads_col.insert_many(ads_data)
print(f"Seeded {len(ads_data)} ads.")


# --- 3. Seed Super Categories (directly into services_col) ---
# This is YOUR desired hierarchical structure: Super Category -> Ministries -> Subservices
super_categories_docs = [
    {
        "id": "governance_public_affairs", # This is the Super Category ID
        "name": get_localized_name_obj("Governance & Public Affairs", "පාලනය සහ පොදු කටයුතු", "ஆளுகை மற்றும் பொது விவகாரங்கள்"),
        "ministries": [ # This array holds the Ministries
            {
                "id": "ministry_public_administration",
                "name": get_localized_name_obj("Ministry of Public Administration", "රාජ්‍ය පරිපාලන අමාත්‍යාංශය", "பொது நிர்வாக அமைச்சு"),
                "subservices": [
                    {
                        "id": "civil_servant_info",
                        "name": get_localized_name_obj("Civil Servant Information", "රාජ්‍ය සේවක තොරතුරු", "அரசாங்க ஊழியர் தகவல்"),
                        "brief": "Information and guidelines for Sri Lankan civil servants, including recruitment, transfers, and retirement.",
                        "eligibility": "Sri Lankan citizens who meet the minimum qualifications for civil service positions.",
                        "documents": "National ID, educational certificates, service records, and application forms.",
                        "fees": "No fees for information. Application fees may apply for certain services.",
                        "application_steps": "1. Visit the Public Administration website or nearest office. 2. Fill out the relevant application form. 3. Submit required documents. 4. Await confirmation or further instructions.",
                        "contact": "Ministry of Public Administration, Colombo 07. Tel: 011-2698000 | Email: info@pubadmin.gov.lk",
                        "office_hours": "Monday to Friday, 8:30 AM - 4:00 PM",
                        "location": "Ministry of Public Administration, Independence Square, Colombo 07, Sri Lanka.",
                        "questions": [
                            {
                                "q": get_localized_name_obj("Civil service guidelines?", "රාජ්‍ය සේවා මාර්ගෝපදේශ?", "அரசாங்க சேவை வழிகாட்டல்கள்?"),
                                "answer": get_localized_name_obj("Check Public Admin portal for latest guidelines and circulars.", "රාජ්‍ය පරිපාලන ද්වාරය පරීක්ෂා කරන්න.", "பொது நிர்வாக தளத்தைப் பார்க்கவும்."),
                                "instructions": "Refer to the circular section for updates.",
                                "downloads": ["/static/forms/civil-service-guidelines.pdf"]
                            },
                            {
                                "q": get_localized_name_obj("How to apply for a transfer?", "මාරු සඳහා අයදුම් කරන්නේ කෙසේද?", "மாற்றத்திற்கு எப்படி விண்ணப்பிப்பது?"),
                                "answer": get_localized_name_obj("Submit a transfer application form with supporting documents.", "අයදුම්පත සහ සහාය ලේඛන ඉදිරිපත් කරන්න.", "விண்ணப்பப் படிவம் மற்றும் ஆதார ஆவணங்களை சமர்ப்பிக்கவும்."),
                                "instructions": "Attach service record and approval from current department.",
                                "downloads": ["/static/forms/transfer-application.pdf"]
                            }
                        ]
                    }
                ]
            },
            {
                "id": "ministry_justice",
                "name": get_localized_name_obj("Ministry of Justice", "අධිකරණ අමාත්‍යාංශය", "நீதி அமைச்சு"),
                "subservices": [
                    {
                        "id": "court_services",
                        "name": get_localized_name_obj("Court Services", "අධිකරණ සේවා", "நீதிமன்ற சேவைகள்"),
                        "brief": "Provides information and assistance for all court-related services in Sri Lanka, including case status, legal aid, and document requests.",
                        "eligibility": "Sri Lankan citizens, legal residents, and registered attorneys.",
                        "documents": "National ID, case reference number, supporting legal documents.",
                        "fees": "Varies by service (e.g., Rs. 500 for certified copies, Rs. 1000 for case filing).",
                        "application_steps": "1. Visit the nearest court or official website. 2. Fill out the application/request form. 3. Submit required documents. 4. Pay applicable fees. 5. Receive confirmation and follow up as needed.",
                        "contact": "Ministry of Justice, Colombo 12. Tel: 011-2477000 | Email: info@justice.gov.lk",
                        "office_hours": "Monday to Friday, 8:30 AM - 4:00 PM",
                        "location": "Ministry of Justice, Superior Courts Complex, Colombo 12, Sri Lanka.",
                        "questions": [
                            {
                                "q": get_localized_name_obj("How do I check my court case status?", "මගේ නඩු තත්ත්වය පරීක්ෂා කරන්නේ කෙසේද?", "என் வழக்கின் நிலையை எப்படிச் சரிபார்க்கலாம்?"),
                                "answer": get_localized_name_obj("You can check your case status online at www.justiceministry.gov.lk/cases or by visiting the relevant court registry.", "ඔබට www.justiceministry.gov.lk/cases වෙබ් අඩවිය හරහා හෝ අදාළ අධිකරණය වෙත ගොස් නඩු තත්ත්වය පරීක්ෂා කළ හැක.", "நீங்கள் www.justiceministry.gov.lk/cases இணையதளத்தில் அல்லது சம்பந்தப்பட்ட நீதிமன்றத்தில் நேரில் சென்று உங்கள் வழக்கின் நிலையை சரிபார்க்கலாம்."),
                                "instructions": "Have your case reference number ready when checking status.",
                                           "downloads": ["/static/forms/case-status-request.pdf"]
                            },
                            {
                                "q": get_localized_name_obj("How to request legal aid?", "නීති උපකාරය ඉල්ලන්නේ කෙසේද?", "சட்ட உதவியை எப்படிக் கோரலாம்?"),
                                "answer": get_localized_name_obj("Submit a legal aid application at the Legal Aid Commission office or online.", "නීති උපකාරය සඳහා අයදුම්පත නීති උපකාර කොමිෂන් සභාව වෙත හෝ අන්තර්ජාලය හරහා ඉදිරිපත් කරන්න.", "சட்ட உதவி விண்ணப்பத்தை சட்ட உதவி ஆணையத்தில் அல்லது ஆன்லைனில் சமர்ப்பிக்கவும்."),
                                "instructions": "Attach proof of income and ID copy.",
                                "downloads": ["https://justice.gov.lk/forms/legal-aid-application.pdf"]
                            }
                        ]
                    }
                ]
            },
            {
                "id": "ministry_foreign",
                "name": get_localized_name_obj("Ministry of Foreign Affairs", "විදේශ කටයුතු අමාත්‍යාංශය", "வெளிவிவகார அமைச்சு"),
                "subservices": [
                    {
                        "id": "consular_services",
                        "name": get_localized_name_obj("Consular Services", "කොන්සියුලර් සේවා", "தூதரக சேவைகள்"),
                        "brief": "Assistance for Sri Lankan citizens abroad, including passport renewal, lost documents, and emergency help.",
                        "eligibility": "Sri Lankan citizens residing or traveling abroad.",
                        "documents": "National ID, passport, proof of residence, application forms.",
                        "fees": "Rs. 2,500 for passport renewal, Rs. 1,000 for document attestation.",
                        "application_steps": "1. Contact nearest Sri Lankan embassy or consulate. 2. Fill out the consular service application form. 3. Submit required documents. 4. Pay applicable fees. 5. Receive service confirmation.",
                        "contact": "Ministry of Foreign Affairs, Colombo 01. Tel: 011-2437635 | Email: consular@foreignmin.gov.lk",
                        "office_hours": "Monday to Friday, 8:30 AM - 4:00 PM",
                        "location": "Ministry of Foreign Affairs, Republic Building, Colombo 01, Sri Lanka.",
                        "questions": [
                            {
                                "q": get_localized_name_obj("Consular assistance?", "කොන්සියුලර් ආධාර?", "தூதரக உதவி?"),
                                "answer": get_localized_name_obj("Contact your nearest Sri Lankan embassy for help with passports, emergencies, and legal matters.", "ඔබගේ ෆ්‍රාන්සිස් තානාපති කාර්යාලය අමතන්න.", "உங்கள் இலங்கை தூதரகத்தைத் தொடர்பு கொள்ளவும்."),
                                "instructions": "Visit the embassy website for appointment booking.",
                                "downloads": ["/static/forms/consular-service-application.pdf"]
                            },
                            {
                                "q": get_localized_name_obj("How to renew a passport abroad?", "විදේශයේදී පුරප්පාඩු පත්‍රය නවීකරණය කරන්නේ කෙසේද?", "வெளிநாட்டில் பாஸ்போர்ட்டை புதுப்பிப்பது எப்படி?"),
                                "answer": get_localized_name_obj("Submit renewal form and old passport at the embassy.", "නවීකරණය සඳහා පෝරමය සහ පැරණි පුරප්පාඩු පත්‍රය ඉදිරිපත් කරන්න.", "புதுப்பிப்பிற்கான படிவம் மற்றும் பழைய பாஸ்போர்ட்டை தூதரகத்தில் சமர்ப்பிக்கவும்."),
                                "instructions": "Attach passport photos and pay renewal fee.",
                                "downloads": ["/static/forms/passport-renewal.pdf"]
                            }
                        ]
                    }
                ]
            },
            {
                "id": "ministry_imm",
                "name": get_localized_name_obj("Ministry of Immigration", "ආගමන හා විගමන අමාත්‍යාංශය", "குடிவரவு அமைச்சு"),
                "subservices": [
                    {"id": "visa_services", "name": get_localized_name_obj("Visa Services", "වීසා සේවා", "வீසා சேவைகள்"), "questions": [{"q": get_localized_name_obj("How to apply for visa?", "වීසා සඳහා අයදුම් කරන්නේ කෙසේද?", "வீசாவுக்கு விண்ணப்பிப்பது எப்படி?"), "answer": get_localized_name_obj("Visit Immigration Dept.", "ආගමන හා විගමන දෙපාර්තමේන්තුවට පිවිසෙන්න.", "குடிவரவு திணைக்களத்திற்குச் செல்லவும்.")}]}
                ]
            },
            {
                "id": "ministry_defence",
                "name": get_localized_name_obj("Ministry of Defence", "ආරක්ෂක අමාත්‍යාංශය", "பாதுகாப்பு அமைச்சு"),
                "subservices": [
                    {"id": "military_recruitment", "name": get_localized_name_obj("Military Recruitment", "හමුදා බඳවා ගැනීම්", "இராணுவ ஆட்சேர்ப்பு"), "questions": [{"q": get_localized_name_obj("How to join military?", "හමුදාවට බැඳෙන්නේ කෙසේද?", "இராணுவத்தில் சேர்வது எப்படி?"), "answer": get_localized_name_obj("Check defence ministry website.", "ආරක්ෂක අමාත්‍යාංශයේ වෙබ් අඩවිය පරීක්ෂා කරන්න.", "பாதுகாப்பு அமைச்சு வலைத்தளத்தைப் பார்க்கவும்.")}]}
                ]
            }
        ]
    },
    {
        "id": "economic_development_infra",
        "name": get_localized_name_obj("Economic Development & Infrastructure", "ආර්ථික සංවර්ධනය සහ යටිතල පහසුකම්", "பொருளாதார அபிவிருத்தி மற்றும் உட்கட்டமைப்பு"),
        "ministries": [
            {
                "id": "ministry_finance",
                "name": get_localized_name_obj("Ministry of Finance", "මුදල් අමාත්‍යාංශය", "நிதி அமைச்சு"),
                "subservices": [
                    {
                        "id": "tax_info",
                        "name": get_localized_name_obj("Tax Information", "බදු තොරතුරු", "வரி தகவல்"),
                        "brief": "Comprehensive information and assistance for Sri Lankan taxpayers, including tax registration, filing, payment, and refunds.",
                        "eligibility": "Sri Lankan citizens, residents, and registered businesses who earn taxable income.",
                        "documents": "National ID, Taxpayer Identification Number (TIN), income statements, business registration (for companies), completed tax forms.",
                        "fees": "No fees for information. Tax filing fees and penalties may apply as per Inland Revenue regulations.",
                        "application_steps": "1. Register for a Taxpayer Identification Number (TIN) at the Inland Revenue Department (IRD). 2. Gather all required documents. 3. Complete the relevant tax return form (individual or business). 4. Submit the form online via www.ird.gov.lk or at the IRD office. 5. Pay any taxes due and collect receipt.",
                        "contact": "Inland Revenue Department, Sir Chittampalam A. Gardiner Mawatha, Colombo 02. Tel: 011-2135000 | Email: info@ird.gov.lk",
                        "office_hours": "Monday to Friday, 8:30 AM - 4:00 PM",
                        "location": "Inland Revenue Department, Colombo 02, Sri Lanka.",
                        "questions": [
                            {
                                "q": get_localized_name_obj("How to file taxes?", "බදු ගොනු කරන්නේ කෙසේද?", "வரிகளை எவ்வாறு தாக்கல் செய்வது?"),
                                "answer": get_localized_name_obj("File taxes online at www.ird.gov.lk or visit the IRD office.", "www.ird.gov.lk හරහා හෝ IRD කාර්යාලයට ගොස් බදු ගොනු කරන්න.", "www.ird.gov.lk இல் அல்லது IRD அலுவலகத்தில் வரிகளை தாக்கல் செய்யவும்."),
                                "instructions": "Have your TIN and income documents ready.",
                                "downloads": ["/static/forms/tax-return-individual.pdf", "/static/forms/tax-return-business.pdf"]
                            },
                            {
                                "q": get_localized_name_obj("How to get a TIN?", "TIN ලබා ගන්නේ කෙසේද?", "TIN எப்படிப் பெறுவது?"),
                                "answer": get_localized_name_obj("Apply at IRD with your National ID and proof of income.", "ජාතික හැඳුනුම්පත සහ ආදායම් සාධක IRD වෙත ඉදිරිපත් කරන්න.", "தேசிய அடையாள அட்டை மற்றும் வருமான ஆதாரத்துடன் IRD இல் விண்ணப்பிக்கவும்."),
                                "instructions": "Fill out the TIN application form and submit at IRD.",
                                "downloads": ["/static/forms/tin-application.pdf"]
                            },
                            {
                                "q": get_localized_name_obj("How to claim a tax refund?", "බදු ආපසු ලබාගන්නේ කෙසේද?", "வரி திரும்பப் பெறுவது எப்படி?"),
                                "answer": get_localized_name_obj("Submit refund request form with supporting documents at IRD.", "ආපසු ලබා ගැනීමේ අයදුම්පත සහ සහාය ලේඛන IRD වෙත ඉදිරිපත් කරන්න.", "திரும்பப் பெறும் விண்ணப்பம் மற்றும் ஆதார ஆவணங்களை IRD இல் சமர்ப்பிக்கவும்."),
                                "instructions": "Attach proof of tax payment and bank details.",
                                "downloads": ["/static/forms/tax-refund-request.pdf"]
                            }
                        ]
                    }
                ]
            },
            {
                "id": "ministry_industry_trade",
                "name": get_localized_name_obj("Ministry of Industry & Trade", "කර්මාන්ත හා වෙළඳ අමාත්‍යාංශය", "கைத்தொழில் மற்றும் வர்த்தக அமைச்சு"),
                "subservices": [
                    {"id": "business_registration", "name": get_localized_name_obj("Business Registration", "ව්‍යාපාර ලියාපදිංචිය", "வியாபார பதிவு"), "questions": [{"q": get_localized_name_obj("Register a new business?", "නව ව්‍යාපාරයක් ලියාපදිංචි කරන්නේ කෙසේද?", "புதிய வியாபாரத்தைப் பதிவு செய்வது எப்படி?"), "answer": get_localized_name_obj("Contact Registrar of Companies.", "සමාගම් රෙජිස්ට්‍රාර් අමතන්න.", "நிறுவனங்கள் பதிவாளரைத் தொடர்பு கொள்ளவும்.")}]}
                ]
            },
            {
                "id": "ministry_power_energy",
                "name": get_localized_name_obj("Ministry of Power & Energy", "බලශක්ති හා බලශක්ති අමාත්‍යාංශය", "மின்சக்தி மற்றும் எரிசக்தி அமைச்சு"),
                "subservices": [
                    {"id": "electricity_bills", "name": get_localized_name_obj("Electricity Bills", "විදුලි බිල්පත්", "மின்சாரக் கட்டණங்கள்"), "questions": [{"q": get_localized_name_obj("Pay electricity bill?", "විදුලි බිල ගෙවන්නේ කෙසේද?", "மின்சாரக் கட்டணத்தை செலுத்துவது எப்படி?"), "answer": get_localized_name_obj("Online or post office.", "ඔන්ලයින් හෝ තැපැල් කාර්යාලය.", "இணையம் மூலமாக அல்லது தபால் அலுவலகத்தில்.")}]}
                ]
            },
            {
                "id": "ministry_transport",
                "name": get_localized_name_obj("Ministry of Transport", "ප්‍රවාහන අමාත්‍යාංශය", "போக்குவரத்து அமைச்சு"),
                "subservices": [
                    {"id": "driving_license", "name": get_localized_name_obj("Driving License Services", "රියදුරු බලපත්‍ර සේවා", "சாரதி அனுமதிப்பத்திர சேவைகள்"), "questions": [{"q": get_localized_name_obj("How to get a driving license?", "රියදුරු බලපත්‍රයක් ලබා ගන්නේ කෙසේද?", "சாரதி அனுமதிப்பத்திரம் பெறுவது எப்படி?"), "answer": get_localized_name_obj("Visit DMT.", "මෝටර් රථ දෙපාර්තමේන්තුවට පිවිසෙන්න.", "மோட்டார் வாகன போக்குவரத்து திணைக்களத்திற்குச் செல்லவும்.")}]}
                ]
            },
            {
                "id": "ministry_it",
                "name": get_localized_name_obj("Ministry of IT & Digital Affairs", "තොරතුරු තාක්ෂණ හා ඩිජිටල් කටයුතු අමාත්‍යාංශය", "தகவல் தொழில்நுட்ப மற்றும் டிஜிட்டல் விவகாரங்கள் அமைச்சு"),
                "subservices": [
                    {
                        "brief": "Visa application, renewal, and information for foreign nationals and Sri Lankan citizens.",
                        "eligibility": "Foreign nationals visiting Sri Lanka and Sri Lankan citizens requiring travel visas.",
                        "documents": "Passport, completed visa application form, passport-size photos, supporting documents (invitation letter, travel itinerary, etc.).",
                        "fees": "Tourist visa: USD 35; Business visa: USD 40; Transit visa: USD 20.",
                        "application_steps": "1. Visit the Department of Immigration & Emigration website or office. 2. Fill out the visa application form. 3. Submit required documents. 4. Pay visa fee. 5. Await approval and collect visa.",
                        "contact": "Department of Immigration & Emigration, Colombo 08. Tel: 011-5329000 | Email: info@immigration.gov.lk",
                        "office_hours": "Monday to Friday, 8:30 AM - 4:00 PM",
                        "location": "Department of Immigration & Emigration, No. 41, Ananda Rajakaruna Mawatha, Colombo 08, Sri Lanka.",
                        "questions": [
                            {
                                "q": get_localized_name_obj("How to apply for visa?", "වීසා සඳහා අයදුම් කරන්නේ කෙසේද?", "வீசாவுக்கு விண்ணப்பிப்பது எப்படி?"),
                                "answer": get_localized_name_obj("Apply online or at the Immigration office.", "ඔන්ලයින් හෝ ආගමන දෙපාර්තමේන්තුවේදී අයදුම් කරන්න.", "ஆன்லைனில் அல்லது குடிவரவு திணைக்களத்தில் விண்ணපිටු කරන්න."),
                                "instructions": "Complete the online form and upload documents.",
                                "downloads": ["/static/forms/visa-application.pdf"]
                            },
                            {
                                "q": get_localized_name_obj("Visa extension process?", "වීසා දිගු කිරීමේ ක්‍රියාවලිය කුමක්ද?", "வீசா நீட்டிப்பு செயல்முறை என்ன?"),
                                "answer": get_localized_name_obj("Submit extension form before visa expiry.", "වීසා කල් ඉකුත්වීමට පෙර දිගු කිරීමේ පෝරමය ඉදිරිපත් කරන්න.", "வீசா காலாவதියට පෙර நீட்டிப்பு படிவத்தை சமர்ப்பிக்கவும்."),
                                "instructions": "Attach current visa and pay extension fee.",
                                "downloads": ["/static/forms/visa-extension.pdf"]
                            }
                        ],
                        "name": get_localized_name_obj("IT Certificates", "තොරතුරු තාක්ෂණ සහතික", "தகவல் தொழில்நுட்ப சான்றிதழ்கள்"),
                        "questions": [
                            {
                                "q": get_localized_name_obj("How to apply for an IT certificate?", "තොරතුරු තාක්ෂණ සහතිකයක් සඳහා අයදුම් කරන්නේ කෙසේද?", "தகவல் தொழில்நுட்ப சான்றிதழுக்கு எவ்வாறு விண்ணப்பிப்பது?"),
                                "answer": get_localized_name_obj("Fill online form and upload NIC.", "ඔන්ලයින් පෝරමය පුරවා ජාතික හැඳුනුම්පත උඩුගත කරන්න.", "ஆன்லைன் படிவத்தை பூர்த்தி செய்து தேசிய அடையாள அட்டையை பதிவேற்றவும்."),
                                "downloads": ["/static/forms/it_cert_form.pdf"],
                                "location": "https://maps.google.com/?q=Ministry+of+IT",
                                "instructions": "Visit the digital portal, register and submit application."
                            }
                        ]
                    }
                ]
            }
        ]
    },
    {
        "id": "social_human_development",
        "name": get_localized_name_obj("Social & Human Development", "සමාජ හා මානව සංවර්ධනය", "சமூக மற்றும் மனித அபிவிருத்தி"),
        "ministries": [
            {
                "id": "ministry_health",
                "name": get_localized_name_obj("Ministry of Health", "සෞඛ්‍ය අමාත්‍යාංශය", "சுகாதார அமைச்சு"),
                "subservices": [
                    {"id": "public_hospitals", "name": get_localized_name_obj("Public Hospitals", "රාජ්‍ය රෝහල්", "பொது மருத்துவமனைகள்"), "questions": [{"q": get_localized_name_obj("Nearest hospital?", "ළඟම ඇති රෝහල?", "அருகிலுள்ள மருத்துவமனை?"), "answer": get_localized_name_obj("Check health ministry portal.", "සෞඛ්‍ය අමාත්‍යාංශයේ වෙබ් අඩවිය පරීක්ෂා කරන්න.", "சுகாதார அமைச்சு தளத்தைப் பார்க்கவும்.")}]}
                ]
            },
            {
                "id": "ministry_education",
                "name": get_localized_name_obj("Ministry of Education", "අධ්‍යාපන අමාත්‍යාංශය", "கல்வி அமைச்சு"),
                "subservices": [
                    {
                        "id": "schools",
                        "name": get_localized_name_obj("Schools", "පාසල්", "பாடசாலைகள்"),
                        "questions": [
                            {
                                "q": get_localized_name_obj("How to register a school?", "පාසලක් ලියාපදිංචි කරන්නේ කෙසේද?", "பாடசாலையை பதிவு செய்வது எப்படி?"),
                                "answer": get_localized_name_obj("Complete registration form and submit documents.", "ලියාපදිංචි පෝරමය සම්පූර්ණ කර ලියකියවිලි ඉදිරිපත් කරන්න.", "பதிவு படிவத்தை பூர்த்தி செய்து ஆவணங்களை சமர்ப்பிக்கவும்."),
                                "downloads": ["/static/forms/school_reg.pdf"],
                                "location": "https://maps.google.com/?q=Ministry+of+Education",
                                "instructions": "Follow the guidelines on the education portal."
                            }
                        ]
                    },
                    {
                        "id": "exams",
                        "name": get_localized_name_obj("Exams & Results", "විභාග සහ ප්‍රතිඵල", "பரீட்சைகள் மற்றும் முடிவுகள்"),
                        "questions": [
                            {
                                "q": get_localized_name_obj("How to apply for national exam?", "ජාතික විභාගයට අයදුම් කරන්නේ කෙසේද?", "தேசிய பரீட்சைக்கு எவ்வாறு விண்ணப்பிப்பது?"),
                                "answer": get_localized_name_obj("Register via examination portal.", "විභාග ද්වාරය හරහා ලියාපදිංචි වන්න.", "பரீட்சை போர்டல் வழியாக பதிவு செய்யவும்."),
                                "downloads": [], "location": "", "instructions": "Check exam schedule and fee."
                            }
                        ]
                    }
                ]
            },
            {
                "id": "ministry_labour",
                "name": get_localized_name_obj("Ministry of Labour", "කම්කරු අමාත්‍යාංශය", "தொழிலாளர் அமைச்சு"),
                "subservices": [
                    {"id": "employment_services", "name": get_localized_name_obj("Employment Services", "රැකියා සේවා", "வேலைவாய்ப்பு சேவைகள்"), "questions": [{"q": get_localized_name_obj("Find job openings?", "රැකියා අවස්ථා සොයන්නේ කෙසේද?", "வேலை வாய்ப்புகளை எவ்வாறு கண்டுபிடிப்பது?"), "answer": get_localized_name_obj("Visit employment exchange.", "රැකියා විනිමය කාර්යාලයට පිවිසෙන්න.", "வேலைவாய்ப்பு பரிமாற்ற அலுவலகத்திற்குச் செல்லவும்.")}]}
                ]
            },
            {
                "id": "ministry_youth",
                "name": get_localized_name_obj("Ministry of Youth Affairs", "තරුණ කටයුතු අමාත්‍යාංශය", "இளைஞர் விவகார அமைச்சு"),
                "subservices": [
                    {"id": "youth_programs", "name": get_localized_name_obj("Youth Programs", "තරුණ වැඩසටහන්", "இளைஞர் திட்டங்கள்"), "questions": [{"q": get_localized_name_obj("Youth development programs?", "තරුණ සංවර්ධන වැඩසටහන්?", "இளைஞர் மேம்பாட்டு திட்டங்கள்?"), "answer": get_localized_name_obj("Check youth services council.", "තරුණ සේවා කවුන්සිලය පරීක්ෂා කරන්න.", "இளைஞர் சேவைகள் சபையை பார்க்கவும்.")}]}
                ]
            },
            {
                "id": "ministry_housing",
                "name": get_localized_name_obj("Ministry of Housing", "නිවාස අමාත්‍යාංශය", "வீடமைப்பு அமைச்சு"),
                "subservices": [
                    {"id": "housing_schemes", "name": get_localized_name_obj("Housing Schemes", "නිවාස යෝජනා ක්‍රම", "வீடமைப்பு திட்டங்கள்"), "questions": [{"q": get_localized_name_obj("Apply for housing?", "නිවාස සඳහා අයදුම් කරන්නේ කෙසේද?", "வீடமைப்புக்கு விண்ணப்பிப்பது எப்படி?"), "answer": get_localized_name_obj("Contact NHDA.", "ජාතික නිවාස සංවර්ධන අධිකාරිය අමතන්න.", "தேசிய வீடமைப்பு அபிவிருத்தி அதிகார சபையைத் தொடர்பு கொள்ளவும்.")}]}
                ]
            },
            {
                "id": "ministry_agri",
                "name": get_localized_name_obj("Ministry of Agriculture", "කෘෂිකර්ම අමාත්‍යාංශය", "விவசாய அமைச்சு"),
                "subservices": [
                    {"id": "farmer_support", "name": get_localized_name_obj("Farmer Support Services", "ගොවි සහාය සේවා", "விவசாயி ஆதரவு சேவைகள்"), "questions": [{"q": get_localized_name_obj("Subsidies for farmers?", "ගොවීන් සඳහා සහනාධාර?", "விவசாயிகளுக்கான மானியங்கள்?"), "answer": get_localized_name_obj("Contact Agrarian Services.", "කෘෂිකාර්මික සේවා දෙපාර්තමේන්තුව අමතන්න.", "விவசாய சேவைகள் திணைக்களத்தை தொடர்பு கொள்ளவும்.")}]}
                ]
            },
            {
                "id": "ministry_water_supply",
                "name": get_localized_name_obj("Ministry of Water Supply", "ජල සම්පාදන අමාත්‍යාංශය", "நீர் வழங்கல் அமைச்சு"),
                "subservices": [
                    {"id": "water_connections", "name": get_localized_name_obj("Water Connections", "ජල සම්බන්ධතා", "நீர் இணைப்புகள்"), "questions": [{"q": get_localized_name_obj("Apply for new water connection?", "නව ජල සම්බන්ධතාවක් සඳහා අයදුම් කරන්න?", "புதிய நீர் இணைப்புக்கு விண்ணப்பிப்பது எப்படி?"), "answer": get_localized_name_obj("Contact NWSDB.", "ජාතික ජල සම්පාදන හා ජලාපවහන මණ්ඩලය අමතන්න.", "தேசிய நீர் வழங்கல் மற்றும் வடிகால் வாரியத்தை தொடர்பு கொள்ளவும்.")}]}
                ]
            }
        ]
    },
    {
        "id": "environment_culture_tourism",
        "name": get_localized_name_obj("Environment, Culture & Tourism", "පරිසරය, සංස්කෘතිය සහ සංචාරක", "சுற்றுச்சூழல், கலாசாரம் மற்றும் சுற்றுலா"),
        "ministries": [
            {
                "id": "ministry_environment",
                "name": get_localized_name_obj("Ministry of Environment", "පරිසර අමාත්‍යාංශය", "சுற்றுச்சூழல் அமைச்சு"),
                "subservices": [
                    {"id": "waste_management", "name": get_localized_name_obj("Waste Management", "අපද්‍රව්‍ය කළමනාකරණය", "கழிவு மேலாண்மை"), "questions": [{"q": get_localized_name_obj("Waste disposal guidelines?", "අපද්‍රව්‍ය බැහැර කිරීමේ මාර්ගෝපදේශ?", "கழிவு அகற்றல் வழிகாட்டல்கள்?"), "answer": get_localized_name_obj("Check CEA guidelines.", "මධ්‍යම පරිසර අධිකාරියේ මාර්ගෝපදේශ පරීක්ෂා කරන්න.", "மத்திய சுற்றுச்சூழல் அதிகார சபையின் வழிகாட்டல்களைப் பார்க்கவும்.")}]}
                ]
            },
            {
                "id": "ministry_culture",
                "name": get_localized_name_obj("Ministry of Culture", "සංස්කෘතික අමාත්‍යාංශය", "கலாசார அமைச்சு"),
                "subservices": [
                    {"id": "cultural_events", "name": get_localized_name_obj("Cultural Events", "සංස්කෘතික උත්සව", "கலாசார நிகழ்வுகள்"), "questions": [{"q": get_localized_name_obj("Upcoming cultural events?", "ළඟදීම පැවැත්වෙන සංස්කෘතික උත්සව?", "வரவிருக்கும் கலாசார நிகழ்வுகள்?"), "answer": get_localized_name_obj("Visit cultural affairs department.", "සංස්කෘතික කටයුතු දෙපාර්තමේන්තුවට පිවිසෙන්න.", "கலாசார விவகாரங்கள் திணைக்களத்திற்குச் செல்லவும்.")}]}
                ]
            },
            {
                "id": "ministry_tourism",
                "name": get_localized_name_obj("Ministry of Tourism", "සංචාරක අමාත්‍යාංශය", "சுற்றுலா அமைச்சு"),
                "subservices": [
                    {"id": "tourist_info", "name": get_localized_name_obj("Tourist Information", "සංචාරක තොරතුරු", "சுற்றுலா தகவல்"), "questions": [{"q": get_localized_name_obj("Popular tourist spots?", "ජනප්‍රිය සංචාරක ස්ථාන?", "பிரபலமான சுற்றுலாத் தலங்கள்?"), "answer": get_localized_name_obj("Check SL Tourism website.", "ශ්‍රී ලංකා සංචාරක වෙබ් අඩවිය පරීක්ෂා කරන්න.", "இலங்கை சுற்றுலா வலைத்தளத்தைப் பார்க்கவும்.")}]}
                ]
            }
        ]
    },
    {
        "id": "other_government_services", # A general category for any unlisted or broad services
        "name": get_localized_name_obj("Other Government Services", "වෙනත් රාජ්‍ය සේවා", "ஏனைய அரசாங்க சேவைகள்"),
        "ministries": [
            {
                "id": "ministry_general",
                "name": get_localized_name_obj("General Government Services", "සාමාන්‍ය රාජ්‍ය සේවා", "பொது அரசாங்க சேவைகள்"),
                "subservices": [
                    {"id": "general_inquiries", "name": get_localized_name_obj("General Inquiries", "සාමාන්‍ය විමසීම්", "பொது விசாரணைகள்"), "questions": [{"q": get_localized_name_obj("What services are offered?", "කුමන සේවාවන් ලබා දෙනවාද?", "என்ன சேவைகள் வழங்கப்படுகின்றன?"), "answer": get_localized_name_obj("Please check the service list on the portal.", "කරුණාකර ද්වාරයේ සේවා ලැයිස්තුව පරීක්ෂා කරන්න.", "தளத்தில் சேவைப் பட்டியலை சரிபார்க்கவும்.")}]}
                ]
            }
        ]
    }
]
services_col.insert_many(super_categories_docs)
print(f"Seeded {len(super_categories_docs)} super category documents with nested ministries.")

# --- 5. Seed Products (Public Store) ---
products_col = db["products"]
orders_col = db["orders"]
payments_col = db["payments"]

# Clear existing store data (safe in dev/seeding)
products_col.delete_many({})
orders_col.delete_many({})
payments_col.delete_many({})

products = [
    {
        "id": "prod_degree_01",
        "name": "Bachelor of IT (SpaceXP Campus)",
        "category": "education",
        "subcategory": "degree_programs",
        "price": 185000,
        "original_price": 225000,
        "currency": "LKR",
        "images": ["/static/store/degree_it.jpg"],
        "description": "Complete your IT degree with flexible payment options. Government employee discount available.",
        "features": ["3-year program", "Weekend classes", "Online support", "Government discount"],
        "tags": ["degree", "it", "government", "career_advancement"],
        "target_segments": ["needs_qualification", "government_employee", "mid_career_family"],
        "in_stock": True,
        "delivery_options": ["online", "campus"],
        "rating": 4.5,
        "reviews_count": 47,
        "created": datetime.utcnow()
    },
    {
        "id": "prod_ielts_01",
        "name": "IELTS Preparation Course",
        "category": "education",
        "subcategory": "language_courses",
        "price": 25000,
        "original_price": 35000,
        "currency": "LKR",
        "images": ["/static/store/ielts_course.jpg"],
        "description": "Comprehensive IELTS preparation with mock tests and speaking practice.",
        "features": ["4-week intensive", "Expert trainers", "Mock tests", "Speaking practice"],
        "tags": ["ielts", "english", "overseas", "government"],
        "target_segments": ["government_employee", "early_career", "mid_education"],
        "in_stock": True,
        "delivery_options": ["online", "classroom"],
        "rating": 4.7,
        "reviews_count": 89,
        "created": datetime.utcnow()
    },
    {
        "id": "prod_japan_visa_01",
        "name": "Japan Work Visa Assistance",
        "category": "visa_services",
        "subcategory": "job_visas",
        "price": 45000,
        "currency": "LKR",
        "images": ["/static/store/japan_visa.jpg"],
        "description": "Complete assistance for Japan work visa applications. IT and healthcare opportunities.",
        "features": ["Visa processing", "Job matching", "Document preparation", "Pre-departure orientation"],
        "tags": ["japan", "work_visa", "overseas_jobs", "it_jobs"],
        "target_segments": ["early_career", "mid_career_family", "needs_qualification"],
        "in_stock": True,
        "delivery_options": ["consultation"],
        "rating": 4.3,
        "reviews_count": 34,
        "created": datetime.utcnow()
    },
    {
        "id": "prod_laptop_01",
        "name": "Government Employee Laptop Deal",
        "category": "electronics",
        "subcategory": "computers",
        "price": 85000,
        "original_price": 115000,
        "currency": "LKR",
        "images": ["/static/store/laptop_deal.jpg"],
        "description": "Special laptop package for government employees with extended warranty.",
        "features": ["Intel i5 processor", "8GB RAM", "256GB SSD", "2-year warranty", "Government discount"],
        "tags": ["laptop", "electronics", "government_deal", "technology"],
        "target_segments": ["government_employee", "early_career", "mid_career_family"],
        "in_stock": True,
        "delivery_options": ["delivery", "pickup"],
        "rating": 4.4,
        "reviews_count": 156,
        "created": datetime.utcnow()
    },
    {
        "id": "prod_saree_01",
        "name": "Handloom Batik Saree Collection",
        "category": "fashion",
        "subcategory": "traditional_wear",
        "price": 4500,
        "original_price": 6500,
        "currency": "LKR",
        "images": ["/static/store/batik_saree.jpg"],
        "description": "Authentic handloom batik sarees with traditional designs. Limited edition.",
        "features": ["Pure cotton", "Handmade", "Traditional designs", "Multiple colors"],
        "tags": ["saree", "batik", "handloom", "traditional", "fashion"],
        "target_segments": ["mid_career_family", "established_professional", "senior"],
        "in_stock": True,
        "delivery_options": ["delivery", "pickup"],
        "rating": 4.6,
        "reviews_count": 203,
        "created": datetime.utcnow()
    }
]

# If a demo Stripe price id is configured via env, attach it to a demo product
try:
    demo_price = os.getenv('STRIPE_PRICE_PREMIUM_MONTHLY')
    if demo_price:
        for p in products:
            if p.get('id') == 'prod_degree_01':
                p['stripe_price_id'] = demo_price
                break
except Exception:
    pass

if products:
    products_col.insert_many(products)
    print("Seeded products:", products_col.count_documents({}))


# --- 4. Seed Admin User (or update if exists) ---
admin_username = "admin"
admin_pwd = os.getenv("ADMIN_PWD", "admin123") # Get from .env or default

existing_admin = admins_col.find_one({"username": admin_username})
hashed_password = bcrypt.hashpw(admin_pwd.encode("utf-8"), bcrypt.gensalt())

if existing_admin:
    try:
        # Check if password needs updating (e.g., if it was plain text before)
        # This is a robust way to ensure it's always hashed
        if not bcrypt.checkpw(admin_pwd.encode("utf-8"), existing_admin["password"]):
            admins_col.update_one({"username": admin_username}, {"$set": {"password": hashed_password}})
            print(f"Updated existing admin user '{admin_username}' with new hashed password.")
        else:
            print(f"Admin user '{admin_username}' already exists with correct hashed password.")
    except Exception:
        # Handle case where existing password is not a valid hash (e.g., was plain text)
        admins_col.update_one({"username": admin_username}, {"$set": {"password": hashed_password}})
        print(f"Updated existing admin user '{admin_username}' (from potentially plain text) with new hashed password.")
else:
    admins_col.insert_one({"username": admin_username, "password": hashed_password})
    print(f"Created admin user '{admin_username}' with hashed password.")

print("Seed complete.")