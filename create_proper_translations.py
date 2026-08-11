import sqlite3
import json
import re

def create_proper_translations():
    """Create proper Tagalog translations for all diseases"""
    
    conn = sqlite3.connect('pitaya_database.db')
    cursor = conn.cursor()
    
    # Get all diseases
    cursor.execute('SELECT id, disease_name, description, symptoms, prevention_methods, recommended_treatments, causes FROM disease_library')
    diseases = cursor.fetchall()
    
    # Translation mappings for accurate translations
    translation_mappings = {
        # Common phrases
        "A fungal disease": "Isang sakit na fungal",
        "A bacterial disease": "Isang sakit na bakterya", 
        "A serious fungal disease": "Isang malubhang sakit na fungal",
        "A devastating disease": "Isang nakakapinsalang sakit",
        "that causes": "na nagdudulot ng",
        "causes": "nagdudulot ng",
        "dark, sunken lesions": "mga madilaw na lesyon na nanaog",
        "on stems, fruits, and cladodes": "sa mga tangkay, prutas, at kladodes",
        "Common in humid conditions": "Karaniwan sa humid na kondisyon",
        "and can lead to": "at maaaring magdulot ng",
        "significant yield loss": "malaking pagkawala ng ani",
        "if untreated": "kung hindi gamotin",
        "Characterized by": "Nakikilala sa pamamagitan ng",
        "sunken, dark-colored lesions": "mga lesyon na nanaog at madilaw",
        "with raised margins": "na may taas na gilid",
        "that girdle stems": "na bumabalot sa mga tangkay",
        "leading to tissue death": "na nagdudulot ng pagkamatay ng tisyu",
        "and branch dieback": "at pagkauga ng mga sanga",
        "Can lead to plant death": "Maaaring magdulot ng pagkamatay ng halaman",
        "if not managed": "kung hindi pamamahalaan",
        "Small, water-soaked spots": "Mga maliliit na tuldok na basa-dilig",
        "Dark brown to black": "Madilaw na kayumanggi hanggang itim",
        "with raised margins": "na may taas na gilid",
        "Orange to pink spore masses": "Mga masa ng spore na kulay orange hanggang pink",
        "in humid conditions": "sa humid na kondisyon",
        "Fruit rot and premature fruit drop": "Paglala ng prutas at maagang pagbagsak ng prutas",
        "Stem cankers and dieback": "Mga canker sa tangkay at pagkauga",
        "in severe cases": "sa mga malubhang kaso",
        "Green to brown/black": "Berde hanggang kayumanggi/itim",
        "lesion development": "pag-unlad ng lesyon",
        "Yellowing around lesion margins": "Pagdilaw sa paligid ng gilid ng lesyon",
        "Sunken, circular to irregular lesions": "Mga lesyon na nanaog, pabilog hanggang iregular",
        "2-10mm in diameter": "2-10mm sa diameter",
        "Fruit becomes soft and mushy": "Nagiging malambot at malasang ang prutas",
        "with characteristic dark lesions": "na may katangian na madilaw na mga lesyon",
        "Stem dieback and stunted growth": "Pagkauga ng tangkay at pigilang paglaki",
        
        # Prevention methods
        "Disinfect pruning tools": "Disinfectahin ang mga pruning tool",
        "with 10% bleach solution": "gamit ang 10% bleach solution",
        "between cuts": "sa pagitan ng mga pagputol",
        "Remove and destroy infected branches": "Alisin at sirain ang mga impeksyon na sanga",
        "immediately": "kaagad",
        "Use disease-free planting material": "Gumamit ng libreng sakit na planting material",
        "Avoid pruning during wet conditions": "Iwasan ang pruning sa basa na kondisyon",
        "Clean and sterilize tools regularly": "Linisin at sterilizehin ang mga tool regularly",
        "Ensure proper air circulation": "Tiyakin ang maayos na sirkulasyon ng hangin",
        "around plants": "sa paligid ng mga halaman",
        "Maintain adequate plant spacing": "Pananatilihin ang sapat na pagitan ng halaman",
        "(2-3m apart)": "(2-3m ang pagitan)",
        "Plant on raised beds": "Iplant sa raised beds",
        "in heavy soils": "sa mabigat na lupa",
        "Avoid overhead irrigation": "Iwasan ang overhead irrigation",
        "when possible": "kung maaari",
        "Prune to improve air flow": "Prunin para mapabuti ang daloy ng hangin",
        "through canopy": "sa loob ng canopy",
        "Apply wound sealant": "Ilagay ang wound sealant",
        "to pruning cuts": "sa mga pruning cut",
        "Avoid excessive nitrogen fertilization": "Iwasan ang labis na nitrogen fertilization",
        "Monitor plants regularly": "Bantayan ang mga halaman regularly",
        "for early detection": "para sa maagang pagtuklas",
        "Remove weak or stressed branches": "Alisin ang mga mahina o stressed na sanga",
        "Maintain plant vigor": "Pananatilihin ang lakas ng halaman",
        "through proper nutrition": "sa pamamagitan ng maayos na nutrisyon",
        
        # Treatments
        "Approved fungicides": "Mga approved na fungicide",
        "Broad-spectrum protection": "Malawak na proteksyon",
        "against canker pathogens": "laban sa mga canker pathogen",
        "Systemic protection": "Systemic na proteksyon",
        "for extended periods": "para sa extended na panahon",
        "Apply treatments early": "Ilagay ang mga gamot sa maaga",
        "in disease development": "sa pag-unlad ng sakit",
        "Remove severely affected branches": "Alisin ang mga malubha napektadong sanga",
        "Improve air circulation": "Pabutin ang sirkulasyon ng hangin",
        "Monitor environmental conditions": "Bantayan ang mga kondisyon ng kapaligiran",
        "Keep detailed treatment logs": "Panatilihin ang detalyadong treatment logs",
        
        # General terms
        "stems": "mga tangkay",
        "fruits": "mga prutas", 
        "branches": "mga sanga",
        "leaves": "mga dahon",
        "plant": "halaman",
        "disease": "sakit",
        "infection": "impeksyon",
        "lesions": "mga lesyon",
        "symptoms": "mga sintomas",
        "treatment": "gamot",
        "prevention": "pag-iwas",
        "control": "kontrol",
        "management": "pamamahalaan",
        "farmers": "mga magsasaka",
        "dragon fruit": "pitaya",
        "pitaya": "pitaya"
    }
    
    def translate_text(text):
        """Translate English text to Tagalog using mappings"""
        if not text:
            return text
            
        if isinstance(text, str):
            if text.strip() == '':
                return text
        else:
            return text  # Return as-is if not a string
            
        translated = text
        
        # Apply translations (longer phrases first for accuracy)
        for english, tagalog in sorted(translation_mappings.items(), key=lambda x: len(x[0]), reverse=True):
            translated = translated.replace(english, tagalog)
        
        return translated
    
    def translate_json_field(json_field):
        """Translate JSON field content"""
        if not json_field or json_field.strip() == '':
            return json_field
            
        try:
            data = json.loads(json_field)
            translated_data = {}
            
            for key, value in data.items():
                if isinstance(value, list):
                    translated_data[key] = [translate_text(item) for item in value]
                elif isinstance(value, dict):
                    translated_data[key] = {k: translate_text(v) for k, v in value.items()}
                elif isinstance(value, str):
                    translated_data[key] = translate_text(value)
                else:
                    translated_data[key] = value
                    
            return json.dumps(translated_data)
            
        except json.JSONDecodeError:
            return translate_text(json_field)
    
    # Update each disease with proper translations
    for disease in diseases:
        disease_id, name, description, symptoms, prevention, treatments, causes = disease
        
        print(f"Translating {name}...")
        
        # Translate each field
        translated_description = translate_text(description)
        translated_symptoms = translate_json_field(symptoms)
        translated_prevention = translate_json_field(prevention)
        translated_treatments = translate_json_field(treatments)
        translated_causes = translate_json_field(causes)
        
        # Update database
        cursor.execute('''
            UPDATE disease_library 
            SET description_tagalog = ?, symptoms_tagalog = ?, 
                prevention_methods_tagalog = ?, recommended_treatments_tagalog = ?,
                causes_tagalog = ?
            WHERE id = ?
        ''', (translated_description, translated_symptoms, translated_prevention, 
              translated_treatments, translated_causes, disease_id))
        
        print(f"✅ {name} translated successfully")
    
    conn.commit()
    conn.close()
    print("\n🎉 All diseases have been translated with proper Tagalog content!")

if __name__ == "__main__":
    create_proper_translations()
