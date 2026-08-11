"""
Management command to populate disease library with comprehensive information
Run: python manage.py populate_diseases
"""
from django.core.management.base import BaseCommand
from disease.models import Disease
import os
from pathlib import Path

class Command(BaseCommand):
    help = 'Populate disease library with comprehensive disease information'

    def handle(self, *args, **options):
        # Base directory for disease images
        base_dir = Path(__file__).resolve().parent.parent.parent.parent.parent
        disease_images_dir = base_dir / 'All Disease'
        
        diseases_data = [
            {
                'name': 'Anthracnose',
                'affected_plant_part': 'leaf',
                'symptoms': 'Dark, sunken lesions on leaves and fruits. Lesions may appear water-soaked initially, then turn brown or black. On leaves, lesions are typically circular with dark margins. Fruits show circular, sunken spots that may develop pink spore masses in humid conditions.',
                'causes': 'Caused by Colletotrichum species fungi. Spreads through water splashes, infected plant debris, and contaminated tools. Favored by warm, humid conditions (25-30°C) and high moisture levels.',
                'prevention_methods': '1. Remove and destroy infected plant parts immediately. 2. Improve air circulation by proper spacing. 3. Avoid overhead watering; use drip irrigation. 4. Apply preventive fungicides (copper-based or mancozeb) during wet seasons. 5. Keep the area clean of plant debris. 6. Disinfect pruning tools between uses.',
                'treatment_recommendations': '1. Apply fungicides containing azoxystrobin, propiconazole, or thiophanate-methyl. 2. Remove severely infected leaves and fruits. 3. Improve drainage to reduce humidity. 4. Apply treatments every 7-14 days during active disease periods. 5. Consider biological control agents like Trichoderma species.',
                'image_path': 'Anthracnose.jpg'
            },
            {
                'name': 'Black Spot',
                'affected_plant_part': 'leaf',
                'symptoms': 'Circular black spots with yellow halos on leaves. Spots typically start small (1-2mm) and expand to 5-10mm. Leaves may yellow and drop prematurely. Spots have distinct dark centers with lighter margins.',
                'causes': 'Caused by Diplocarpon rosae or similar fungal pathogens. Thrives in warm, humid conditions with temperatures between 20-25°C. Spreads via water splashes, wind, and contaminated tools.',
                'prevention_methods': '1. Plant in areas with good air circulation. 2. Water at the base of plants, avoiding wetting leaves. 3. Remove fallen leaves and debris regularly. 4. Apply preventive fungicides early in the season. 5. Space plants adequately to reduce humidity. 6. Choose disease-resistant varieties when available.',
                'treatment_recommendations': '1. Apply fungicides such as chlorothalonil, mancozeb, or myclobutanil. 2. Remove and destroy infected leaves. 3. Improve air circulation through pruning. 4. Apply treatments every 10-14 days during active periods. 5. Use copper-based fungicides as an organic option.',
                'image_path': 'blackspot.jpeg'
            },
            {
                'name': 'Brown Spot',
                'affected_plant_part': 'leaf',
                'symptoms': 'Brown, Circular brown to black spots on stems. Spots coalesce causing large necrotic areas. Stem surface becomes rough and cracked.',
                'causes': 'Caused by bacterial pathogens (Pseudomonas, Xanthomonas) or fungal pathogens (Cercospora, Alternaria). Favored by warm, wet conditions and high humidity. Spreads through water splashes and contaminated tools.',
                'prevention_methods': '1. Avoid overhead irrigation; use drip systems. 2. Remove infected leaves promptly. 3. Improve plant spacing for better air circulation. 4. Apply copper-based bactericides preventively. 5. Keep the growing area clean of debris. 6. Avoid working with plants when leaves are wet.',
                'treatment_recommendations': '1. Maintain proper spacing. 2. Prune affected stems. 3. Apply Cholrothalonill 0.2percent or Mancozeb 0.25percent.',
                'image_path': 'brownspot.jpeg'
            },
            {
                'name': 'Root Rot',
                'affected_plant_part': 'root',
                'symptoms': 'Wilting, yellowing leaves, and stunted growth. Roots appear brown, mushy, and decayed. Root system is reduced with few healthy white roots. Plant may collapse suddenly. Above-ground symptoms include leaf drop and dieback.',
                'causes': 'Caused by soil-borne pathogens like Phytophthora, Pythium, or Fusarium species. Favored by waterlogged soil, poor drainage, and overwatering. Can be exacerbated by root damage and compacted soil.',
                'prevention_methods': '1. Ensure proper soil drainage; avoid waterlogged conditions. 2. Use well-draining soil mix. 3. Avoid overwatering; allow soil to dry between waterings. 4. Plant in raised beds if drainage is poor. 5. Use disease-free planting material. 6. Rotate crops to prevent pathogen buildup.',
                'treatment_recommendations': '1. Improve drainage immediately. 2. Reduce watering frequency. 3. Spray Copper oxychloride 0.3percent or Steptocyline.',
                'image_path': 'Root Rot.jpg'
            },
            {
                'name': 'Soft Rot',
                'affected_plant_part': 'stem',
                'symptoms': 'Water-soaked, soft, mushy areas on stems that rapidly expand. Affected tissue becomes slimy and emits a foul odor. The rot spreads quickly, causing plant collapse. Lesions are typically dark and sunken.',
                'causes': 'Caused by bacterial pathogens, primarily Erwinia carotovora or Pectobacterium species. Enters through wounds, cuts, or natural openings. Thrives in warm (25-30°C), humid conditions with high moisture.',
                'prevention_methods': '1. Avoid wounding plants during handling. 2. Disinfect tools between uses. 3. Ensure good air circulation. 4. Avoid overhead watering. 5. Remove infected plant parts immediately. 6. Use disease-free planting material.',
                'treatment_recommendations': '1. Improve filed drainage and reduce excess moisture. 2. Remove infeceted plants immediately . 3. Improve air circulation and reduce humidity. 4. Avoid working with plants when wet. 5. Use antibiotics like streptomycin if legally permitted and available. 6. Sterilize tools and containers to prevent transmission.',
                'image_path': 'Soft Rot.jpg'
            },
            {
                'name': 'Stem Rot',
                'affected_plant_part': 'stem',
                'symptoms': 'Tissue collapses rapidly under humid conditions. Watery, soft, foul-smelling rot on stems. Plant shows sudden wilting',
                'causes': 'Caused by fungal pathogens like Sclerotinia, Botrytis, or Rhizoctonia species. Favored by high humidity, poor air circulation, and wounds. Spreads through spores in air and water.',
                'prevention_methods': '1. Improve air circulation through proper spacing and pruning. 2. Avoid overhead watering. 3. Remove infected stems promptly. 4. Disinfect pruning tools. 5. Apply preventive fungicides during humid periods. 6. Keep the growing area clean and free of debris.',
                'treatment_recommendations': '1. Remove infected stems immediately, cutting below the lesion. 2. Apply fungicides like thiophanate-methyl, iprodione, or azoxystrobin. 3. Improve ventilation and reduce humidity. 4. Apply treatments every 7-14 days. 5. Use biological control agents like Trichoderma. 6. Ensure proper plant nutrition to improve resistance.',
                'image_path': 'Stem Rot.jpeg'
            },
            {
                'name': 'Stem_Canker',
                'affected_plant_part': 'stem',
                'symptoms': 'Sunken, dark cankers on stems with raised margins. Cankers may ooze sap or develop cracks. Affected stems may show dieback above the canker. Bark may split or peel around the canker area.',
                'causes': 'Caused by fungal pathogens like Botryosphaeria, Phomopsis, or Nectria species. Often enters through wounds, pruning cuts, or natural openings. Favored by stress conditions and high humidity.',
                'prevention_methods': '1. Make clean pruning cuts at proper angles. 2. Disinfect pruning tools between cuts. 3. Avoid wounding stems. 4. Apply wound sealants after pruning. 5. Maintain plant health through proper nutrition. 6. Improve air circulation.',
                'treatment_recommendations': '1. Prune out cankers, cutting at least 2-3 inches below the visible canker. 2. Apply fungicides like thiophanate-methyl or propiconazole. 3. Paint large wounds with fungicidal paint. 4. Improve plant vigor through proper fertilization. 5. Apply treatments every 10-14 days during active periods. 6. Remove severely affected stems entirely.',
                'image_path': 'Stem_Canker.jpg'
            },
            {
                'name': 'Twig Blight',
                'affected_plant_part': 'stem',
                'symptoms': 'Rapid browning and death of twigs and small branches. Affected twigs show dieback from tips, with leaves turning brown and remaining attached. Twigs become brittle and may snap easily. Dark lesions may be visible at the base of affected twigs.',
                'causes': 'Caused by fungal pathogens like Phomopsis, Botryosphaeria, or Diplodia species. Often associated with stress conditions, wounds, or previous damage. Spreads through spores and infected plant material.',
                'prevention_methods': '1. Maintain plant health through proper nutrition and watering. 2. Prune out dead or diseased twigs regularly. 3. Avoid stress conditions (drought, overwatering, nutrient deficiencies). 4. Disinfect pruning tools. 5. Improve air circulation. 6. Apply preventive fungicides during high-risk periods.',
                'treatment_recommendations': '1. Prune out all affected twigs, cutting into healthy tissue. 2. Apply fungicides like thiophanate-methyl, propiconazole, or azoxystrobin. 3. Improve plant vigor through proper care. 4. Apply treatments every 10-14 days. 5. Remove and destroy all infected plant material. 6. Consider biological control agents.',
                'image_path': 'Twig Blight.jpg'
            },
            {
                'name': 'White Spot',
                'affected_plant_part': 'leaf',
                'symptoms': 'Small, white or light-colored spots on leaves, often with dark centers. Spots may be circular or irregular. Leaves may yellow around spots. Severe infections can cause leaf drop. Spots may have a powdery appearance.',
                'causes': 'Caused by fungal pathogens like Cercospora, Septoria, or powdery mildew species. Favored by high humidity, moderate temperatures (20-25°C), and poor air circulation. Spreads through spores in air and water.',
                'prevention_methods': '1. Improve air circulation through proper spacing. 2. Avoid overhead watering. 3. Remove infected leaves promptly. 4. Apply preventive fungicides early. 5. Keep the growing area clean. 6. Use resistant varieties when available.',
                'treatment_recommendations': '1. Apply fungicides like chlorothalonil, myclobutanil, or sulfur-based products. 2. Remove severely affected leaves. 3. Improve ventilation and reduce humidity. 4. Apply treatments every 7-10 days during active periods. 5. Use neem oil or baking soda solutions as organic alternatives. 6. Ensure proper plant nutrition.',
                'image_path': 'White Spot.jpeg'
            },
        ]
        
        created_count = 0
        updated_count = 0
        
        for disease_data in diseases_data:
            disease, created = Disease.objects.update_or_create(
                name=disease_data['name'],
                defaults={
                    'affected_plant_part': disease_data['affected_plant_part'],
                    'symptoms': disease_data['symptoms'],
                    'causes': disease_data['causes'],
                    'prevention_methods': disease_data['prevention_methods'],
                    'treatment_recommendations': disease_data['treatment_recommendations'],
                    'image_path': disease_data['image_path']
                }
            )
            
            if created:
                created_count += 1
                self.stdout.write(self.style.SUCCESS(f'Created: {disease.name}'))
            else:
                updated_count += 1
                self.stdout.write(self.style.WARNING(f'Updated: {disease.name}'))
        
        self.stdout.write(self.style.SUCCESS(
            f'\nDisease library populated successfully!\n'
            f'   Created: {created_count} diseases\n'
            f'   Updated: {updated_count} diseases\n'
            f'   Total: {Disease.objects.count()} diseases'
        ))
