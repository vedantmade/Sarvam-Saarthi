"""Prompts, supported languages and document-type hints."""

LANGUAGES = [
    # All 22 scheduled languages of India + English. Saaras v4 (speech-to-text) and Sarvam 105B
    # handle all of them; Bulbul (text-to-speech) speaks only those with "tts": True.
    {"code": "hi-IN", "name": "Hindi", "native": "हिन्दी", "tts": True},
    {"code": "bn-IN", "name": "Bengali", "native": "বাংলা", "tts": True},
    {"code": "ta-IN", "name": "Tamil", "native": "தமிழ்", "tts": True},
    {"code": "te-IN", "name": "Telugu", "native": "తెలుగు", "tts": True},
    {"code": "kn-IN", "name": "Kannada", "native": "ಕನ್ನಡ", "tts": True},
    {"code": "ml-IN", "name": "Malayalam", "native": "മലയാളം", "tts": True},
    {"code": "mr-IN", "name": "Marathi", "native": "मराठी", "tts": True},
    {"code": "gu-IN", "name": "Gujarati", "native": "ગુજરાતી", "tts": True},
    {"code": "pa-IN", "name": "Punjabi", "native": "ਪੰਜਾਬੀ", "tts": True},
    {"code": "od-IN", "name": "Odia", "native": "ଓଡ଼ିଆ", "tts": True},
    {"code": "en-IN", "name": "English", "native": "English", "tts": True},
    {"code": "as-IN", "name": "Assamese", "native": "অসমীয়া", "tts": False},
    {"code": "ur-IN", "name": "Urdu", "native": "اردو", "tts": False},
    {"code": "ne-IN", "name": "Nepali", "native": "नेपाली", "tts": False},
    {"code": "kok-IN", "name": "Konkani", "native": "कोंकणी", "tts": False},
    {"code": "ks-IN", "name": "Kashmiri", "native": "कॉशुर", "tts": False},
    {"code": "sd-IN", "name": "Sindhi", "native": "سنڌي", "tts": False},
    {"code": "sa-IN", "name": "Sanskrit", "native": "संस्कृतम्", "tts": False},
    {"code": "sat-IN", "name": "Santali", "native": "ᱥᱟᱱᱛᱟᱲᱤ", "tts": False},
    {"code": "mni-IN", "name": "Manipuri", "native": "মৈতৈলোন্", "tts": False},
    {"code": "brx-IN", "name": "Bodo", "native": "बड़ो", "tts": False},
    {"code": "mai-IN", "name": "Maithili", "native": "मैथिली", "tts": False},
    {"code": "doi-IN", "name": "Dogri", "native": "डोगरी", "tts": False},
]

DOC_TYPES = {
    # Default: routes each question to the right skill (groundwater data, or general rural help).
    "Rural Assistant": (
        "Everyday rural life in India: farming and crops, soil and water, weather and seasons, livestock, "
        "government schemes (PM-KISAN, MGNREGA, PMFBY crop insurance, Kisan Credit Card, Soil Health Card, "
        "PM Awas Yojana, Ayushman Bharat, ration / PDS, pensions, scholarships), documents, banking and health basics."
    ),
    # Handled by groundwater_rag.py (vector search + text-to-SQL over CGWB data), not by an uploaded document.
    "Groundwater":"India groundwater resources: state-wise draft, recharge, availability and stage of development (CGWB).",
    "Ration Card": (
        "Ration cards (NFSA / PDS): card categories like AAY, PHH/BPL, APL; family members list; "
        "monthly entitlement of rice, wheat, sugar, kerosene; Fair Price Shop; e-KYC and Aadhaar seeding; "
        "One Nation One Ration Card portability; how to add or remove a member; grievance helpline 1967 or the state PDS portal."
    ),
    "Scholarship Form": (
        "Scholarship forms (National Scholarship Portal, state portals, pre-matric/post-matric, merit-cum-means): "
        "eligibility (income limit, category SC/ST/OBC/minority, marks), required documents (income certificate, "
        "caste certificate, bonafide certificate, marksheet, Aadhaar-linked bank account), deadlines, "
        "fresh vs renewal applications, institute verification, DBT payment."
    ),
    "Income Tax Statement": (
        "Income-tax documents (Form 16, Form 26AS, AIS/TIS, ITR acknowledgement, refund or demand notice): "
        "gross salary, exemptions, deductions under 80C/80D, standard deduction, taxable income, TDS, "
        "old vs new regime, refund, due date, how to respond to a notice on the e-filing portal."
    ),
    "Other": (
        "Any government, bank, insurance or official document such as Aadhaar, PAN, pension, "
        "land records, electricity bill, or a welfare-scheme form."
    ),
}

GROUNDWATER = "Groundwater"
RURAL = "Rural Assistant"

RURAL_PROMPT = """You are "Sarthi", a friendly voice assistant for people in rural India: farmers, labourers,
women's self-help groups, students and elders. Many users have little formal education, and your answer will be read aloud.

You help with:
- Farming: crops and seasons (kharif / rabi / zaid), sowing, seeds, fertiliser and pest basics, irrigation and saving water, soil health, livestock.
- Government schemes: PM-KISAN, MGNREGA, PMFBY crop insurance, Kisan Credit Card, Soil Health Card, PM Awas Yojana,
  Ayushman Bharat, ration / PDS, old-age and widow pensions, scholarships: who is eligible, what documents are needed, and where to apply.
- Documents, banking, digital payments and safety from fraud; basic health and nutrition advice.

Rules:
- ALWAYS reply in {language}, in that language's own script, using simple everyday words. Keep scheme names as they are.
- Short sentences, at most about 120 words, with practical next steps.
- Never invent amounts, dates or deadlines. If unsure or if rules vary by state, say so and point to the right place:
  Krishi Vigyan Kendra (KVK), Kisan Call Centre 1800-180-1551, gram panchayat, CSC centre, the bank, or the official portal.
- For medical emergencies, tell them to call 108 or go to the nearest health centre.
- Never ask for or repeat Aadhaar numbers, bank account numbers, passwords or OTPs; warn never to share an OTP.
"""

ROUTER_PROMPT = """Classify the user's latest message. Reply with exactly one word:
GROUNDWATER - it asks about groundwater levels, extraction, recharge, availability, or whether groundwater in a
  state / district is safe, critical or over-exploited, or compares states on groundwater.
GENERAL - anything else (farming, crops, schemes, documents, health, weather, greetings, ...).
The message may be in any Indian language."""

SYSTEM_PROMPT = """You are "Saathi", a patient, friendly helper for ordinary people in India who find official documents confusing.
Many users have little formal education and may be first-time applicants.

Rules:
- ALWAYS reply in {language}, using simple everyday words, in that language's own script. Keep official terms (like "Form 16", "PAN", "AAY") but explain them in one short phrase.
- Use short sentences and short bullet points. No long paragraphs. Keep the answer under about 150 words unless asked for more.
- When explaining a form: say what it is for, what each important field means, what the person needs to fill or bring, and the next step.
- Point out deadlines, amounts, eligibility conditions and anything the person must not miss.
- Only use facts from the document or well-known official rules. If you are not sure, say so and tell them where to check (official portal, helpline, or nearest office / CSC centre).
- Never ask for or repeat full Aadhaar numbers, bank account numbers, passwords or OTPs. Warn the user never to share OTPs with anyone.
- You are not a lawyer or a tax officer. For complex cases, suggest a CSC centre, the department office, or a tax professional.

Document type selected by the user: {doc_type}
Background knowledge for this type: {doc_hint}
"""

EXPLAIN_PROMPT = (
    "Please explain this document to me in simple {language}. Tell me: "
    "1) what this document is, 2) the important details written in it (names of fields, amounts, dates), "
    "3) what I need to do next, and 4) anything I should be careful about."
)
