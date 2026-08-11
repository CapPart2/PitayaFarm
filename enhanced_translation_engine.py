"""
Enhanced Translation Engine for PITAYA Disease Library
Context-based translation for agricultural and medical content
"""

import json
import sqlite3
from typing import Dict, List, Optional
import re

class EnhancedTranslationEngine:
    def __init__(self, db_path: str = 'pitaya_database.db'):
        self.db_path = db_path
        self.agricultural_terms = self._load_agricultural_terms()
        self.medical_terms = self._load_medical_terms()
        
    def _load_agricultural_terms(self) -> Dict[str, str]:
        """Load agricultural terminology mappings"""
        return {
            # General terms
            'dragon fruit': 'pitaya',
            'pitaya': 'pitaya',
            'cactus': 'kaktus',
            'plant': 'halaman',
            'crop': 'pananim',
            'farm': 'bukid',
            'field': 'bukiran',
            'soil': 'lupa',
            'water': 'tubig',
            'rain': 'ulan',
            'sunlight': 'sinag ng araw',
            'temperature': 'temperatura',
            'humidity': 'halummi',
            'season': 'panahon',
            
            # Plant parts
            'stem': 'tangkay',
            'branch': 'sanga',
            'leaf': 'dahon',
            'leaves': 'mga dahon',
            'fruit': 'prutas',
            'fruits': 'mga prutas',
            'root': 'ugat',
            'roots': 'mga ugat',
            'flower': 'bulaklak',
            'flowers': 'mga bulaklak',
            'cladodes': 'kladodes',
            'spines': 'tinik',
            
            # Diseases and conditions
            'disease': 'sakit',
            'infection': 'impeksyon',
            'fungus': 'fungus',
            'fungal': 'pamumuo ng fungus',
            'bacteria': 'bakterya',
            'viral': 'biral',
            'virus': 'virus',
            'pathogen': 'pathogen',
            'contagious': 'nakakahawa',
            'spreads': 'kumakalat',
            
            # Symptoms
            'spot': 'tuldok',
            'spots': 'mga tuldok',
            'lesion': 'lesyon',
            'lesions': 'mga lesyon',
            'rot': 'paglala',
            'rotting': 'lalabin',
            'wilt': 'malala',
            'wilting': 'paglalala',
            'yellowing': 'pagdilaw',
            'discoloration': 'pagbabago ng kulay',
            'decay': 'paglala',
            'mold': 'amag',
            'mildew': 'amag',
            'blight': 'blight',
            'canker': 'kanker',
            
            # Chemical treatments
            'fungicide': 'fungicide',
            'pesticide': 'pesticide',
            'insecticide': 'insecticide',
            'herbicide': 'herbicide',
            'chemical': 'kemikal',
            'treatment': 'gamot',
            'spray': 'spray',
            'application': 'paglalapat',
            'dose': 'dosis',
            'concentration': 'koncentrasyon',
            
            # Cultural practices
            'sanitation': 'sanitasyon',
            'cleaning': 'pagsisilbi',
            'pruning': 'pagputol',
            'removal': 'pag-alis',
            'quarantine': 'kuwarantina',
            'inspection': 'pagsusuri',
            'monitoring': 'pagmamanman',
            'prevention': 'pag-iwas',
            'control': 'kontrol',
            'management': 'pamamahala',
            
            # Environmental conditions
            'humid': 'halumamog',
            'humidity': 'halummi',
            'moisture': 'halumay',
            'wet': 'basa',
            'dry': 'tuyo',
            'warm': 'mainit',
            'cool': 'malamig',
            'shaded': 'diniliman',
            'exposed': 'nakalantad',
            'ventilation': 'bensilasyon',
            'airflow': 'daloy ng hangin'
        }
    
    def _load_medical_terms(self) -> Dict[str, str]:
        """Load medical terminology mappings"""
        return {
            # Medical conditions
            'symptom': 'sintomas',
            'symptoms': 'mga sintomas',
            'diagnosis': 'diagnosis',
            'prognosis': 'prognosis',
            'treatment': 'gamot',
            'therapy': 'terapiya',
            'medication': 'gamot',
            'medicine': 'gamot',
            'cure': 'gamot',
            'healing': 'paggaling',
            'recovery': 'pagkakagaling',
            
            # Medical actions
            'prevent': 'iwasan',
            'avoid': 'iwasan',
            'protect': 'protektahan',
            'treat': 'gamutin',
            'cure': 'gamutin',
            'manage': 'pamahalaan',
            'control': 'kontrolin',
            'monitor': 'bantayan',
            'observe': 'masdan',
            'check': 'suriin',
            'examine': 'suriin',
            
            # Medical descriptions
            'acute': 'akute',
            'chronic': 'kroniko',
            'severe': 'malala',
            'mild': 'mabagal',
            'moderate': 'katamtaman',
            'serious': 'malubha',
            'critical': 'kritikal',
            'fatal': 'nakamamatay',
            'contagious': 'nakakahawa',
            'infectious': 'nakakahawa',
            
            # Body/Plant conditions
            'healthy': 'malusog',
            'unhealthy': 'hindi malusog',
            'infected': 'na-impeksyon',
            'affected': 'apektado',
            'damaged': 'sira',
            'destroyed': 'nasira',
            'compromised': 'kompromisado'
        }
    
    def translate_text(self, text: str, context: str = 'agricultural') -> str:
        """
        Translate text with context-aware terminology preservation
        """
        if not text or text.strip() == '':
            return text
        
        # Combine terminology dictionaries
        all_terms = {**self.agricultural_terms, **self.medical_terms}
        
        # Process the text
        translated_text = text
        
        # Handle common agricultural/medical phrases
        phrase_mappings = {
            'water-soaked spots': 'mga tuldok na basa-dilig',
            'sunken lesions': 'mga lesyon na nanaog',
            'dark brown': 'madilaw na kayumanggi',
            'black rot': 'itim na paglala',
            'soft rot': 'malambot na paglala',
            'stem rot': 'paglala ng tangkay',
            'root rot': 'paglala ng ugat',
            'leaf spot': 'tuldok sa dahon',
            'powdery mildew': 'amag na pulbos',
            'downy mildew': 'amag na pababa',
            'fungal infection': 'impeksyon na fungal',
            'bacterial infection': 'impeksyon na bakterya',
            'viral infection': 'impeksyon na biral',
            'proper sanitation': 'maayong sanitasyon',
            'regular inspection': 'karaniwang pagsusuri',
            'good airflow': 'mabuting daloy ng hangin',
            'adequate drainage': 'sapat na pagpapauwi',
            'crop rotation': 'pag-ikot ng pananim',
            'resistant varieties': 'mga uri na resistante',
            'biological control': 'biolohikal na kontrol',
            'chemical control': 'kemikal na kontrol',
            'integrated pest management': 'integrated na pamamahala ng peste',
            'disease-free': 'walang sakit',
            'disease-resistant': 'resistante sa sakit',
            'high yield': 'mataas na ani',
            'low yield': 'mababang ani',
            'yield loss': 'pagkawala ng ani',
            'economic impact': 'ekonomikong epekto',
            'market value': 'halaga sa merkado',
            'plant health': 'kalusugan ng halaman',
            'soil health': 'kalusugan ng lupa',
            'environmental conditions': 'kondisyon ng kapaligiran',
            'climatic conditions': 'kondisyon ng klima',
            'weather conditions': 'kondisyon ng panahon'
        }
        
        # Apply phrase mappings first (more specific)
        for english_phrase, tagalog_phrase in phrase_mappings.items():
            translated_text = translated_text.replace(english_phrase, tagalog_phrase)
        
        # Apply word mappings
        for english_term, tagalog_term in all_terms.items():
            # Use word boundaries to avoid partial matches
            pattern = r'\b' + re.escape(english_term) + r'\b'
            translated_text = re.sub(pattern, tagalog_term, translated_text, flags=re.IGNORECASE)
        
        # Handle common sentence structures
        translated_text = self._translate_sentence_structures(translated_text)
        
        return translated_text
    
    def _translate_sentence_structures(self, text: str) -> str:
        """Translate common sentence structures"""
        
        # Common patterns
        structure_mappings = {
            'This is a': 'Ito ay isang',
            'These are': 'Ito ay mga',
            'Caused by': 'Dahil sa',
            'Characterized by': 'Nakikilala sa pamamagitan ng',
            'Results in': 'Nagreresulta sa',
            'Leads to': 'Nagtutungo sa',
            'Associated with': 'Kaugnay sa',
            'Related to': 'Kaugnay sa',
            'Similar to': 'Katulad ng',
            'Different from': 'Magkaiba sa',
            'Affected by': 'Apektado ng',
            'Influenced by': 'Naapektuhan ng',
            'Depends on': 'Nakasalalay sa',
            'Requires': 'Kailangan ng',
            'Needs': 'Kailangan ng',
            'Important for': 'Mahalaga para sa',
            'Essential for': 'Esensyal para sa',
            'Critical for': 'Kritikal para sa',
            'Recommended for': 'Inirerekomenda para sa',
            'Suitable for': 'Angkop para sa',
            'Ideal for': 'Ideal para sa',
            'Best for': 'Pinakamabuti para sa',
            'Good for': 'Mabuti para sa',
            'Bad for': 'Masama para sa',
            'Harmful to': 'nakakasira sa',
            'Dangerous to': 'mapanganib sa',
            'Toxic to': 'toksiko sa',
            'Safe for': 'Ligtas para sa',
            'Effective against': 'Epektibo laban sa',
            'Resistant to': 'Resistante sa',
            'Sensitive to': 'Sensitibo sa',
            'Tolerant to': 'Tolerante sa',
            'Vulnerable to': 'Bulnerable sa',
            'Prone to': 'Madaling magkaroon ng',
            'Susceptible to': 'Susceptible sa'
        }
        
        translated_text = text
        
        for english_structure, tagalog_structure in structure_mappings.items():
            translated_text = translated_text.replace(english_structure, tagalog_structure)
        
        return translated_text
    
    def translate_disease_content(self, disease_data: Dict) -> Dict:
        """
        Translate complete disease content with context preservation
        """
        translated_content = {}
        
        # Translate description
        if 'description' in disease_data:
            translated_content['description'] = self.translate_text(
                disease_data['description'], 
                'disease_description'
            )
        
        # Translate symptoms (handle both string and dict formats)
        if 'symptoms' in disease_data:
            symptoms = disease_data['symptoms']
            if isinstance(symptoms, dict):
                translated_content['symptoms'] = {
                    'visible_signs': [
                        self.translate_text(sign, 'symptoms') 
                        for sign in symptoms.get('visible_signs', [])
                    ],
                    'progression': self.translate_text(
                        symptoms.get('progression', ''), 
                        'symptoms'
                    )
                }
            elif isinstance(symptoms, str):
                translated_content['symptoms'] = self.translate_text(symptoms, 'symptoms')
            else:
                translated_content['symptoms'] = symptoms
        
        # Translate causes
        if 'causes' in disease_data:
            causes = disease_data['causes']
            if isinstance(causes, dict):
                translated_content['causes'] = {
                    'pathogen_type': self.translate_text(
                        causes.get('pathogen_type', ''), 
                        'causes'
                    ),
                    'causal_organism': self.translate_text(
                        causes.get('causal_organism', ''), 
                        'causes'
                    ),
                    'environmental_factors': [
                        self.translate_text(factor, 'causes') 
                        for factor in causes.get('environmental_factors', [])
                    ]
                }
            elif isinstance(causes, str):
                translated_content['causes'] = self.translate_text(causes, 'causes')
            else:
                translated_content['causes'] = causes
        
        # Translate prevention methods
        if 'prevention_methods' in disease_data:
            prevention = disease_data['prevention_methods']
            if isinstance(prevention, dict):
                translated_content['prevention_methods'] = {
                    'cultural_practices': [
                        self.translate_text(practice, 'prevention') 
                        for practice in prevention.get('cultural_practices', [])
                    ],
                    'chemical_control': [
                        self.translate_text(control, 'prevention') 
                        for control in prevention.get('chemical_control', [])
                    ],
                    'biological_control': [
                        self.translate_text(control, 'prevention') 
                        for control in prevention.get('biological_control', [])
                    ]
                }
            elif isinstance(prevention, str):
                translated_content['prevention_methods'] = self.translate_text(prevention, 'prevention')
            else:
                translated_content['prevention_methods'] = prevention
        
        # Translate recommended treatments
        if 'recommended_treatments' in disease_data:
            treatments = disease_data['recommended_treatments']
            if isinstance(treatments, dict):
                translated_content['recommended_treatments'] = {
                    'chemical_treatments': [
                        self.translate_text(treatment, 'treatment') 
                        for treatment in treatments.get('chemical_treatments', [])
                    ],
                    'cultural_treatments': [
                        self.translate_text(treatment, 'treatment') 
                        for treatment in treatments.get('cultural_treatments', [])
                    ],
                    'biological_treatments': [
                        self.translate_text(treatment, 'treatment') 
                        for treatment in treatments.get('biological_treatments', [])
                    ],
                    'application_instructions': self.translate_text(
                        treatments.get('application_instructions', ''), 
                        'treatment'
                    )
                }
            elif isinstance(treatments, str):
                translated_content['recommended_treatments'] = self.translate_text(treatments, 'treatment')
            else:
                translated_content['recommended_treatments'] = treatments
        
        return translated_content
    
    def get_translation_quality_score(self, original: str, translated: str) -> float:
        """
        Calculate translation quality score based on:
        - Length preservation (should be similar)
        - Key term preservation
        - Context accuracy
        """
        if not original or not translated:
            return 0.0
        
        # Base score
        score = 0.8
        
        # Length similarity (should be within reasonable range)
        length_ratio = len(translated) / len(original) if len(original) > 0 else 0
        if 0.7 <= length_ratio <= 1.5:
            score += 0.1
        else:
            score -= 0.1
        
        # Check for key agricultural terms preservation
        key_terms = ['pitaya', 'sakit', 'fungus', 'bakterya', 'gamot', 'kontrol']
        key_terms_found = sum(1 for term in key_terms if term.lower() in translated.lower())
        score += (key_terms_found / len(key_terms)) * 0.1
        
        # Ensure score is within bounds
        return max(0.0, min(1.0, score))

# Initialize the translation engine
translation_engine = EnhancedTranslationEngine()
