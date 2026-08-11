# Dragon Fruit Disease Database
# Comprehensive information about dragon fruit diseases

DISEASE_DATABASE = {
    'Anthracnose': {
        'symptoms': [
            'Small, water-soaked lesions on stems and fruits',
            'Lesions expand and become sunken with raised margins',
            'Orange to pinkish spore masses appear in humid conditions',
            'Fruit may rot and drop prematurely',
            'Black acervuli develop on infected tissue'
        ],
        'causes': [
            'Fungal infection by Colletotrichum gloeosporioides',
            'High humidity and warm temperatures (25-30°C)',
            'Poor air circulation in dense plantings',
            'Rain splash and overhead irrigation',
            'Wounded plant tissues serve as entry points'
        ],
        'treatment': [
            'Remove and destroy infected plant parts',
            'Apply copper-based fungicides (Bordeaux mixture)',
            'Use systemic fungicides like benomyl or carbendazim',
            'Improve air circulation and drainage',
            'Avoid overhead irrigation',
            'Practice proper sanitation and tool sterilization'
        ],
        'severity': 'high',
        'prevention': [
            'Use disease-free planting material',
            'Maintain proper spacing between plants',
            'Apply preventive fungicides during rainy season',
            'Ensure good drainage and ventilation'
        ]
    },
    'Black Spot': {
        'symptoms': [
            'Small, circular, dark brown to black spots on stems',
            'Spots may coalesce forming larger lesions',
            'Yellowing of tissue around spots',
            'Stem cracking and splitting in severe cases',
            'Reduced plant vigor and yield'
        ],
        'causes': [
            'Fungal infection by Alternaria sp. or other dematiaceous fungi',
            'High moisture and humidity',
            'Poor plant nutrition',
            'Mechanical damage to stems',
            'Stress from environmental factors'
        ],
        'treatment': [
            'Prune affected stems with sterilized tools',
            'Apply fungicides containing mancozeb or copper',
            'Improve plant nutrition with balanced fertilizers',
            'Reduce humidity around plants',
            'Apply neem oil or other organic fungicides'
        ],
        'severity': 'medium',
        'prevention': [
            'Maintain proper plant spacing',
            'Avoid overwatering',
            'Use resistant varieties when available',
            'Regular monitoring and early detection'
        ]
    },
    'Brown Spot': {
        'symptoms': [
            'Brown, irregular spots on stems and cladodes',
            'Spots may have dark borders and lighter centers',
            'Lesions can expand and cause tissue death',
            'Premature drop of affected fruits',
            'Stem weakening and breakage'
        ],
        'causes': [
            'Fungal infection by various pathogenic fungi',
            'Excessive moisture and poor drainage',
            'Nutrient deficiencies (especially calcium)',
            'Physical damage to plant tissues',
            'Environmental stress'
        ],
        'treatment': [
            'Remove infected plant parts promptly',
            'Apply appropriate fungicides (copper-based or systemic)',
            'Correct nutrient deficiencies with proper fertilization',
            'Improve soil drainage',
            'Reduce irrigation frequency'
        ],
        'severity': 'medium',
        'prevention': [
            'Use well-draining soil mixtures',
            'Maintain proper irrigation practices',
            'Provide balanced nutrition',
            'Ensure good air circulation'
        ]
    },
    'Root Rot': {
        'symptoms': [
            'Yellowing and wilting of stems',
            'Soft, mushy, and discolored roots',
            'Foul odor from root zone',
            'Stunted growth and poor vigor',
            'Plant collapse in severe cases',
            'Dark brown to black root discoloration'
        ],
        'causes': [
            'Fungal infection by Phytophthora, Pythium, or Fusarium',
            'Overwatering and poor drainage',
            'Compacted soil with poor aeration',
            'Contaminated potting media',
            'High soil moisture for extended periods'
        ],
        'treatment': [
            'Remove severely infected plants (cannot be saved)',
            'For mild cases: stop watering and improve drainage',
            'Apply systemic fungicides (metalaxyl, mefenoxam)',
            'Repot in fresh, sterile soil mix',
            'Treat with beneficial microorganisms (Trichoderma)',
            'Reduce watering frequency significantly'
        ],
        'severity': 'high',
        'prevention': [
            'Use well-draining soil mixtures',
            'Water only when soil is dry',
            'Ensure pots have adequate drainage holes',
            'Use sterile potting media',
            'Avoid over-fertilization'
        ]
    },
    'Soft Rot': {
        'symptoms': [
            'Water-soaked, soft, mushy areas on fruits and stems',
            'Rapid tissue breakdown and liquefaction',
            'Foul, rotten odor from infected areas',
            'Fruit collapse within days of infection',
            'White or pinkish fungal growth in advanced stages'
        ],
        'causes': [
            'Bacterial infection (Erwinia, Pseudomonas) or fungal pathogens',
            'High humidity and warm temperatures',
            'Physical damage to fruits and stems',
            'Poor sanitation and handling practices',
            'Insect wounds serving as entry points'
        ],
        'treatment': [
            'Remove and destroy infected fruits immediately',
            'Apply copper-based bactericides/fungicides',
            'Improve air circulation and reduce humidity',
            'Handle fruits carefully to avoid damage',
            'Use sterile cutting tools for pruning'
        ],
        'severity': 'high',
        'prevention': [
            'Harvest and handle fruits carefully',
            'Maintain clean growing conditions',
            'Control insect populations',
            'Proper storage conditions post-harvest',
            'Regular sanitation practices'
        ]
    },
    'Stem Rot': {
        'symptoms': [
            'Soft, watery lesions at stem base or along stems',
            'Brown to black discoloration of internal stem tissue',
            'Stem becomes mushy and collapses',
            'Fungal growth (white mold) on affected areas',
            'Plant wilting and eventual death'
        ],
        'causes': [
            'Fungal infection by Sclerotium, Rhizoctonia, or Fusarium',
            'Excessive moisture around stem base',
            'Poor air circulation',
            'Soil-borne pathogens from contaminated media',
            'Physical stem injuries'
        ],
        'treatment': [
            'Remove infected stems or entire plant if severe',
            'Apply fungicides (thiophanate-methyl, azoxystrobin)',
            'Improve drainage and air circulation',
            'Avoid getting water on stem bases',
            'Use sterile soil and containers'
        ],
        'severity': 'high',
        'prevention': [
            'Use raised beds or well-draining containers',
            'Water soil directly, not stems',
            'Maintain proper plant spacing',
            'Use clean potting media',
            'Monitor for early signs of infection'
        ]
    },
    'Stem_Canker': {
        'symptoms': [
            'Sunken, dead areas on stems (cankers)',
            'Cracking and splitting of stem tissue',
            'Discolored (brown to black) tissue within cankers',
            'Gum or sap exudation from affected areas',
            'Stem weakening and potential breakage'
        ],
        'causes': [
            'Fungal or bacterial infections through wounds',
            'Environmental stress (extreme temperatures)',
            'Mechanical damage from pruning or handling',
            'Nutrient imbalances',
            'Secondary infections following initial injury'
        ],
        'treatment': [
            'Prune out cankered areas with sterilized tools',
            'Apply wound sealant after pruning',
            'Use copper-based fungicides on wounds',
            'Improve plant nutrition and care',
            'Protect stems from mechanical damage'
        ],
        'severity': 'medium',
        'prevention': [
            'Make clean pruning cuts with sharp tools',
            'Disinfect tools between plants',
            'Avoid unnecessary stem damage',
            'Maintain plant health and vigor',
            'Protect from extreme weather'
        ]
    },
    'Twig Blight': {
        'symptoms': [
            'Dieback of stem tips and young growth',
            'Brown to black discoloration of affected stems',
            'Wilting and death of terminal shoots',
            'Small, dark fruiting bodies on dead tissue',
            'Progressive death from tips downward'
        ],
        'causes': [
            'Fungal infection by Botryosphaeria or related species',
            'Environmental stress (drought, temperature extremes)',
            'Poor plant nutrition',
            'Physical damage to growing tips',
            'Secondary infections following initial damage'
        ],
        'treatment': [
            'Prune out affected stem tips well below infection',
            'Apply systemic fungicides (tebuconazole, propiconazole)',
            'Improve plant nutrition and watering',
            'Reduce environmental stress',
            'Monitor for spread to other parts'
        ],
        'severity': 'medium',
        'prevention': [
            'Maintain consistent watering practices',
            'Provide balanced nutrition',
            'Protect from extreme weather',
            'Prune during dry weather when possible',
            'Monitor plant health regularly'
        ]
    },
    'White Spot': {
        'symptoms': [
            'Small, white, circular spots on stems and fruits',
            'Spots may be raised or flat',
            'Yellowing of tissue around spots',
            'Spots can coalesce forming larger patches',
            'Reduced photosynthetic capacity'
        ],
        'causes': [
            'Fungal infection by various pathogenic fungi',
            'Mineral nutrient imbalances',
            'Environmental stress factors',
            'Poor air circulation',
            'Water stress (too much or too little)'
        ],
        'treatment': [
            'Apply appropriate fungicides (sulfur-based, copper)',
            'Correct nutrient deficiencies',
            'Improve air circulation around plants',
            'Adjust watering practices',
            'Remove severely affected plant parts'
        ],
        'severity': 'medium',
        'prevention': [
            'Maintain proper plant spacing',
            'Provide balanced fertilization',
            'Ensure good ventilation',
            'Monitor environmental conditions',
            'Practice good sanitation'
        ]
    }
}

# The Library cards and detail page require a short introduction in addition
# to the symptoms, causes, treatments, and prevention lists above.
DISEASE_DESCRIPTIONS = {
    'Anthracnose': 'Anthracnose is a fungal disease that causes dark, sunken lesions on dragon-fruit stems and fruit, especially in warm and humid conditions.',
    'Black Spot': 'Black Spot is a fungal disease that creates dark circular spots on dragon-fruit stems. Untreated spots can join together and weaken the plant.',
    'Brown Spot': 'Brown Spot causes irregular brown lesions on stems and cladodes. It can spread when plants remain wet or stressed.',
    'Root Rot': 'Root Rot damages the root system of dragon-fruit plants, causing wilting, poor growth, and possible plant collapse when drainage is poor.',
    'Soft Rot': 'Soft Rot rapidly breaks down infected stem or fruit tissue, leaving soft, watery areas that may have a foul odor.',
    'Stem Rot': 'Stem Rot causes soft, discolored lesions that can spread through the stem and cause the affected plant section to collapse.',
    'Stem_Canker': 'Stem Canker causes deep, dark, and sometimes cracked lesions on dragon-fruit stems that can restrict the flow of water and nutrients.',
    'Twig Blight': 'Twig Blight causes the tips of stems and young growth to dry, darken, and die back, reducing plant vigor.',
    'White Spot': 'White Spot produces pale circular spots on dragon-fruit stems and fruit. Severe infections can reduce the plant’s photosynthetic capacity.',
}

for _disease_name, _description in DISEASE_DESCRIPTIONS.items():
    DISEASE_DATABASE[_disease_name]['description'] = _description

def get_disease_info(disease_name):
    """Get comprehensive information about a specific disease"""
    return DISEASE_DATABASE.get(disease_name, None)

def get_all_diseases():
    """Get list of all available diseases"""
    return list(DISEASE_DATABASE.keys())

def get_diseases_by_severity(severity):
    """Get diseases filtered by severity level"""
    return {name: info for name, info in DISEASE_DATABASE.items() 
            if info.get('severity') == severity}

def search_diseases(keyword):
    """Search diseases by keyword in symptoms, causes, or treatment"""
    results = {}
    keyword = keyword.lower()
    
    for disease, info in DISEASE_DATABASE.items():
        # Search in symptoms
        for symptom in info.get('symptoms', []):
            if keyword in symptom.lower():
                results[disease] = info
                break
        
        # Search in causes if not found
        if disease not in results:
            for cause in info.get('causes', []):
                if keyword in cause.lower():
                    results[disease] = info
                    break
        
        # Search in treatment if not found
        if disease not in results:
            for treatment in info.get('treatment', []):
                if keyword in treatment.lower():
                    results[disease] = info
                    break
    
    return results
