import re
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field

class SpecificationEntities(BaseModel):
    products: List[str] = Field(default_factory=list)
    categories: List[str] = Field(default_factory=list)
    materials: List[str] = Field(default_factory=list)
    dimensions: List[str] = Field(default_factory=list)
    capacities: List[str] = Field(default_factory=list)
    performance: List[str] = Field(default_factory=list)
    applications: List[str] = Field(default_factory=list)
    environments: List[str] = Field(default_factory=list)
    safety: List[str] = Field(default_factory=list)
    testing: List[str] = Field(default_factory=list)
    installation: List[str] = Field(default_factory=list)
    certification_hints: List[str] = Field(default_factory=list)
    standards_cited: List[str] = Field(default_factory=list)
    confidence_score: float = 1.0

# Domain patterns tailored for Indian Procurement & Bureau of Indian Standards (BIS) specifications
PATTERNS = {
    "standards_cited": [
        r"\b(?:IS\s*(?:/ISO)?\s*\d{3,5}(?:\s*(?:Part|Pt\.?)\s*\d+)?(?:\s*:\s*\d{4})?)\b",
        r"\b(?:IS\s*:\s*\d{3,5})\b"
    ],
    "products": [
        r"\b(?:TMT\s+rebars?|steel\s+bars?|structural\s+steel|reinforced\s+concrete|ready\s+mix\s+concrete|RMC|cables?|wires?|submersible\s+pumps?|centrifugal\s+pumps?|transformers?|pipes?|fittings?|insulators?|switchgears?|circuit\s+breakers?|conduits?|valves?)\b",
        r"\b(?:high\s+strength\s+deformed\s+(?:steel\s+)?bars?)\b",
        r"\b(?:polyvinyl\s+chloride\s+insulated\s+cables?)\b",
        r"\b(?:hot\s+rolled\s+(?:medium\s+and\s+high\s+tensile\s+)?structural\s+steel)\b"
    ],
    "materials": [
        r"\b(?:Fe\s*415(?:D)?|Fe\s*500(?:D)?|Fe\s*550(?:D)?|Fe\s*600)\b",
        r"\b(?:M\s*20|M\s*25|M\s*30|M\s*35|M\s*40|M\s*45|M\s*50|M\s*55|M\s*60)\b",
        r"\b(?:E\s*250|E\s*300|E\s*350|E\s*410|E\s*450)\b",
        r"\b(?:copper\s+conductor|aluminum\s+conductor|annealed\s+copper|PVC|XLPE|mild\s+steel|stainless\s+steel|HDPE|ductile\s+iron)\b"
    ],
    "dimensions": [
        r"\b(?:\d+(?:\.\d+)?\s*(?:mm|cm|m|inch|inches|dia|diameter|sq\s*mm|sqmm|gauge))\b",
        r"\b(?:\d+\s*[xX]\s*\d+(?:\s*[xX]\s*\d+)?\s*(?:mm|cm|m)?)\b",
        r"\b(?:NB\s*\d+\s*mm|nominal\s+bore\s+\d+\s*mm)\b"
    ],
    "capacities": [
        r"\b(?:\d+(?:\.\d+)?\s*(?:kVA|MVA|kW|MW|HP|volts?|kV|amperes?|amps?|A|litres?(?:/hr)?|LPH|m3/hr|tons?|MT))\b",
        r"\b(?:\d+\s*V\s*(?:,\s*\d+\s*Hz)?)\b"
    ],
    "performance": [
        r"\b(?:(?:minimum\s+)?tensile\s+strength\s*(?:>=|>|not\s+less\s+than|minimum|of|is)?\s*\d+(?:\.\d+)?\s*(?:N/mm2|MPa)?)\b",
        r"\b(?:(?:minimum\s+)?yield\s+(?:stress|strength)\s*(?:>=|>|minimum|of|is)?\s*\d+(?:\.\d+)?\s*(?:N/mm2|MPa)?)\b",
        r"\b(?:(?:minimum\s+)?elongation\s*(?:>=|>|of|is)?\s*\d+(?:\.\d+)?\s*%)\b",
        r"\b(?:(?:minimum\s+)?characteristic\s+compressive\s+strength\s*(?:>=|>|of|is)?\s*\d+\s*(?:N/mm2|MPa))\b",
        r"\b(?:current\s+carrying\s+capacity\s*(?:up\s+to|of)?\s*\d+\s*A)\b"
    ],
    "applications": [
        r"\b(?:potable\s+water\s+supply|drinking\s+water|sewage\s+disposal|structural\s+framework|foundation\s+footings?|substation|transmission\s+lines?|internal\s+electrification|building\s+wiring|bridge\s+girders?|earthquake\s+resistant\s+construction|seismic\s+zones?\s*(?:III|IV|V)?)\b"
    ],
    "environments": [
        r"\b(?:coastal|marine|corrosive|saline|severe\s+exposure|very\s+severe|extreme\s+weather|indoor\s+dry|underground\s+buried|high\s+temperature|submerged)\b"
    ],
    "safety": [
        r"\b(?:flame\s+retardant|FRLS|low\s+smoke\s+halogen\s+free|LSOH|fire\s+resistant|earthing|grounding|residual\s+current|overload\s+protection|short\s+circuit\s+protection|dielectric\s+breakdown)\b"
    ],
    "testing": [
        r"\b(?:tensile\s+test|bend\s+and\s+rebend\s+test|charpy\s+v-notch\s+impact\s+test|hydrostatic\s+pressure\s+test|spark\s+test|insulation\s+resistance\s+test|compressive\s+strength\s+cube\s+test|ultrasonic\s+testing|radiographic\s+inspection)\b"
    ],
    "installation": [
        r"\b(?:conduit\s+wiring|surface\s+mounting|concealed\s+conduit|trench\s+laying|socket\s+jointing|butt\s+welding|torque\s+tightening|anchorage\s+length|lap\s+length|clear\s+cover)\b"
    ],
    "certification_hints": [
        r"\b(?:BIS\s+(?:standard\s+)?mark|ISI\s+mark(?:ed)?|QCO|Quality\s+Control\s+Order|Compulsory\s+Registration\s+Scheme|CRS|hallmark(?:ed)?|CE\s+mark|ISO\s*9001|CPRI\s+tested|NABL\s+accredited)\b"
    ]
}

CATEGORY_KEYWORDS = {
    "Civil": ["concrete", "cement", "rebar", "aggregate", "sand", "brick", "masonry", "structural", "foundation", "is 456", "is 1786"],
    "Electrical": ["cable", "wire", "voltage", "current", "earthing", "switchgear", "transformer", "insulation", "is 694", "is 732", "is 3043"],
    "Metallurgy": ["steel", "tensile", "yield", "elongation", "plates", "tubes", "rebars", "fe 500", "is 2062", "is 1786"],
    "Mechanical": ["pipe", "pump", "valve", "fittings", "hydrostatic", "pressure", "flange", "is 1239", "is 4984"]
}

def extract_entities(text: str) -> SpecificationEntities:
    """
    Extract technical tender entities across all 12 target dimensions:
    product, category, material, dimensions, capacity, performance, application,
    environment, safety, testing, installation, certification hints.
    """
    if not text:
        return SpecificationEntities()

    results: Dict[str, set] = {key: set() for key in PATTERNS}

    # Regex pattern extraction
    for entity_type, pattern_list in PATTERNS.items():
        for pat in pattern_list:
            matches = re.finditer(pat, text, re.IGNORECASE)
            for m in matches:
                clean_val = re.sub(r"\s+", " ", m.group(0)).strip()
                # Normalize IS standard format (e.g., "IS  456 : 2000" -> "IS 456:2000")
                if entity_type == "standards_cited":
                    clean_val = re.sub(r"IS\s*:\s*", "IS ", clean_val, flags=re.IGNORECASE)
                    clean_val = re.sub(r"\s*:\s*", ":", clean_val)
                    clean_val = re.sub(r"\s+", " ", clean_val)
                results[entity_type].add(clean_val)

    # Category classification based on contextual keywords and detected standards
    categories = set()
    text_lower = text.lower()
    for cat, kws in CATEGORY_KEYWORDS.items():
        if any(kw in text_lower for kw in kws):
            categories.add(cat)

    # Fallback to General if no category triggered
    if not categories:
        categories.add("General Engineering")

    # Calculate confidence based on extraction density
    total_extracted = sum(len(items) for items in results.values())
    confidence = min(1.0, max(0.4, 0.4 + (total_extracted * 0.05)))

    return SpecificationEntities(
        products=sorted(list(results["products"])),
        categories=sorted(list(categories)),
        materials=sorted(list(results["materials"])),
        dimensions=sorted(list(results["dimensions"])),
        capacities=sorted(list(results["capacities"])),
        performance=sorted(list(results["performance"])),
        applications=sorted(list(results["applications"])),
        environments=sorted(list(results["environments"])),
        safety=sorted(list(results["safety"])),
        testing=sorted(list(results["testing"])),
        installation=sorted(list(results["installation"])),
        certification_hints=sorted(list(results["certification_hints"])),
        standards_cited=sorted(list(results["standards_cited"])),
        confidence_score=round(confidence, 2)
    )
