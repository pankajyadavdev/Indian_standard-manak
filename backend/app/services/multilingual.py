"""
Phase 14: Multilingual Support — English + Hindi

Provides:
1. Hindi translation of common IS standard terms, compliance labels, and alert messages
2. Language detection (English vs Hindi)
3. Transliteration for standard codes (IS → आई.एस.)
4. Hindi standard title mapping for all 6 seeded BIS standards
"""

import re
from typing import Dict, Optional

HINDI_TERMS: Dict[str, str] = {
    # Standard categories
    "Civil": "सिविल",
    "Electrical": "विद्युत",
    "Mechanical": "यांत्रिक",
    "Metallurgy": "धातुकर्म",
    "General Engineering": "सामान्य इंजीनियरिंग",

    # Compliance statuses
    "MANDATORY_COMPLIANT": "अनिवार्य अनुपालन — सही",
    "MANDATORY_MISSING": "अनिवार्य अनुपालन — गुम",
    "ADVISORY": "सलाहकार",
    "UNKNOWN": "अज्ञात",
    "NOT_APPLICABLE": "लागू नहीं",
    "COMPLIANT": "अनुपालन में",
    "NON_COMPLIANT": "गैर-अनुपालन",
    "current": "वर्तमान",
    "superseded": "अप्रचलित",
    "withdrawn": "वापस ली गई",
    "not_found": "नहीं मिला",

    # Search types
    "exact": "सटीक",
    "keyword": "कीवर्ड",
    "semantic": "अर्थगत",
    "hybrid": "संयुक्त",

    # Alert keywords
    "CRITICAL": "अत्यंत महत्वपूर्ण",
    "HIGH": "उच्च",
    "MEDIUM": "मध्यम",
    "LOW": "निम्न",

    # Standard terms
    "Insufficient verified evidence.": "पर्याप्त सत्यापित साक्ष्य उपलब्ध नहीं है।",
    "BIS Standard Mark": "भारतीय मानक ब्यूरो का मानक चिह्न",
    "ISI Mark": "आई.एस.आई. चिह्न",
    "Quality Control Order": "गुणवत्ता नियंत्रण आदेश",
    "Bureau of Indian Standards": "भारतीय मानक ब्यूरो",

    # Entity types
    "products": "उत्पाद",
    "materials": "सामग्री",
    "dimensions": "आयाम",
    "capacities": "क्षमताएँ",
    "performance": "प्रदर्शन",
    "applications": "अनुप्रयोग",
    "environments": "पर्यावरण",
    "safety": "सुरक्षा",
    "testing": "परीक्षण",
    "installation": "स्थापना",
    "certification_hints": "प्रमाणन संकेत",
    "standards_cited": "उद्धृत मानक",
}

HINDI_STANDARD_TITLES: Dict[str, str] = {
    "IS 456": "सादा और प्रबलित कंक्रीट — अभ्यास की संहिता",
    "IS 1786": "उच्च शक्ति विकृत स्टील की छड़ें और तार — विशिष्टता",
    "IS 2062": "संरचनात्मक उपयोग के लिए गर्म लुढ़का मध्यम और उच्च तन्य संरचनात्मक स्टील",
    "IS 694": "विद्युत तारों के लिए पी.वी.सी. इन्सुलेटेड केबल",
    "IS 732": "विद्युत तारों की स्थापना — अभ्यास की संहिता",
    "IS 3043": "भूमि संपर्क — अभ्यास की संहिता",
    "IS 269": "सामान्य पोर्टलैंड सीमेंट — विशिष्टता",
    "IS 1608": "धातु सामग्री का तन्य परीक्षण",
    "IS 1239": "इस्पात पाइप और फिटिंग — विशिष्टता",
    "IS 1950": "कंक्रीट और कंक्रीट समुच्चय से संबंधित शब्दों की शब्दावली",
}

STANDARD_CODE_TRANSLITERATION: Dict[str, str] = {
    "IS": "आई.एस.",
}

HINDI_SEARCH_EXPANSIONS: Dict[str, str] = {
    "सादा और प्रबलित कंक्रीट": "plain and reinforced concrete",
    "प्रबलित कंक्रीट": "reinforced concrete",
    "अभ्यास की संहिता": "code of practice",
    "उच्च शक्ति विकृत स्टील की छड़ें": "high strength deformed steel bars",
    "स्टील की छड़ें": "steel bars reinforcement",
    "विद्युत तारों की स्थापना": "electrical wiring installation",
    "पी.वी.सी. इन्सुलेटेड केबल": "PVC insulated cables",
    "भूमि संपर्क": "earthing grounding",
    "संरचनात्मक स्टील": "structural steel",
}


def expand_search_query(query: str) -> str:
    """Add deterministic English terms and standard codes for supported Hindi phrases."""
    additions = []
    folded_query = query.casefold()
    for code, title in HINDI_STANDARD_TITLES.items():
        if title.casefold() in folded_query:
            additions.extend((code, title))
    for hindi, english in HINDI_SEARCH_EXPANSIONS.items():
        if hindi.casefold() in folded_query:
            additions.append(english)
    if not additions:
        return query
    return f"{query} {' '.join(additions)}"


def translate_term(term: str, language: str = "hi") -> str:
    """Translate a known English term to Hindi."""
    if language != "hi":
        return term
    return HINDI_TERMS.get(term, term)


def get_standard_title_hindi(standard_code: str) -> Optional[str]:
    """Return Hindi title for a BIS standard code if available."""
    return HINDI_STANDARD_TITLES.get(standard_code.strip())


def transliterate_standard_code(code: str) -> str:
    """Transliterate IS standard code to Hindi representation."""
    parts = code.strip().split()
    result = []
    for part in parts:
        if part.upper() == "IS":
            result.append("आई.एस.")
        else:
            result.append(part)
    return " ".join(result)


def detect_language(text: str) -> str:
    """Detect if text is primarily Hindi (Devanagari script) or English."""
    devanagari = re.findall(r"[\u0900-\u097F]", text)
    if len(devanagari) > len(text) * 0.2:
        return "hi"
    return "en"


def translate_entity_labels(entities_dict: dict, language: str = "hi") -> dict:
    """Return entity dict with translated labels for Hindi UI rendering."""
    if language != "hi":
        return entities_dict
    translated = {}
    for key, val in entities_dict.items():
        label = HINDI_TERMS.get(key, key)
        translated[label] = val
    return translated
