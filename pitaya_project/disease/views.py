from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods, require_GET
from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse, HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.db.models import Count, Q, F, Sum, Avg, Max, Min
from django.utils import timezone
from datetime import datetime, timedelta
import json
import os
import requests
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from django.core.serializers import serialize

from .models import Disease, Prediction, DiseaseImage

# Flask API URL for predictions
FLASK_API_URL = 'http://localhost:5000/predict'


def get_request_user_id(request, default='default_user'):
    user_id = request.headers.get('X-Pitaya-User') or request.GET.get('user_id')
    if user_id:
        user_id = str(user_id).strip()
        if user_id:
            return user_id
    return default if default is not None else 'default_user'

def home(request):
    """Dashboard: summary cards, disease distribution, yield trend, recent alerts"""
    user_id = get_request_user_id(request, None)
    all_predictions = Prediction.objects.filter(all_predictions__user_id=user_id) if user_id else Prediction.objects.all()
    total_scans = all_predictions.count()
    disease_counts = {}
    for p in all_predictions:
        disease_counts[p.disease_name] = disease_counts.get(p.disease_name, 0) + 1
    # Dashboard stats: total plants (simulated from scans), diseased = scans with high confidence
    high_conf = 70.0
    diseased_count = sum(1 for p in all_predictions if p.confidence >= high_conf)
    total_plants = max(total_scans + 8, 12)  # Demo: total plants in farm
    healthy_plants = max(0, total_plants - diseased_count)
    # Predicted yield (simplified: lower disease impact = higher yield)
    avg_conf = sum(p.confidence for p in all_predictions) / total_scans if total_scans else 0
    predicted_yield = round(85 + (100 - avg_conf) * 0.15, 1) if total_scans else 85.0
    predicted_yield = min(100, max(0, predicted_yield))
    # Yield trend (last 6 periods - by week or by count)
    yield_trend = []
    if total_scans >= 1:
        step = max(1, total_scans // 6)
        for i in range(6):
            idx = min(i * step, total_scans - 1)
            preds_slice = list(all_predictions)[: idx + 1]
            n = len(preds_slice)
            avg = sum(p.confidence for p in preds_slice) / n if n else 0
            yield_trend.append(round(80 + (100 - avg) * 0.2, 1))
    else:
        yield_trend = [85, 86, 85.5, 87, 86.5, 85]
    recent_alerts = list(Prediction.objects.all()[:5])
    context = {
        'total_plants': total_plants,
        'diseased_plants': diseased_count,
        'healthy_plants': healthy_plants,
        'predicted_yield': predicted_yield,
        'disease_counts': disease_counts,
        'disease_labels_json': json.dumps(list(disease_counts.keys())),
        'disease_values_json': json.dumps(list(disease_counts.values())),
        'yield_trend_json': json.dumps(yield_trend),
        'recent_alerts': recent_alerts,
        'total_scans': total_scans,
    }
    return render(request, 'home.html', context)

# API Endpoints
@api_view(['GET'])
@permission_classes([AllowAny])
def library_list(request):
    """API endpoint to list all diseases with search and filter"""
    diseases = Disease.objects.all()
    
    # Search functionality
    search_query = request.query_params.get('search', '')
    if search_query:
        diseases = diseases.filter(
            Q(name__icontains=search_query) |
            Q(symptoms__icontains=search_query) |
            Q(causes__icontains=search_query)
        )
    
    # Filter by plant part
    plant_part = request.query_params.get('plant_part', '')
    if plant_part:
        diseases = diseases.filter(affected_plant_part=plant_part)
    
    # Prepare response data
    data = []
    for disease in diseases:
        image_url = None
        if disease.image_path:
            image_url = request.build_absolute_uri(f'/static/{disease.image_path}')
        
        data.append({
            'id': disease.id,
            'name': disease.name,
            'affected_part': disease.get_affected_plant_part_display(),
            'symptoms': disease.symptoms,
            'causes': disease.causes,
            'prevention': disease.prevention_methods,
            'treatment': disease.treatment_recommendations,
            'image_url': image_url,
            'created_at': disease.created_at,
            'updated_at': disease.updated_at
        })
    
    return Response(data)

@api_view(['GET'])
@permission_classes([AllowAny])
def library_detail_api(request, disease_name):
    """API endpoint to get details of a specific disease"""
    try:
        disease = Disease.objects.get(name__iexact=disease_name)
        
        # Get related images
        images = DiseaseImage.objects.filter(disease=disease)
        image_urls = [request.build_absolute_uri(img.image.url) for img in images if img.image]
        
        data = {
            'id': disease.id,
            'name': disease.name,
            'affected_part': disease.get_affected_plant_part_display(),
            'symptoms': disease.symptoms,
            'causes': disease.causes,
            'prevention': disease.prevention_methods,
            'treatment': disease.treatment_recommendations,
            'images': image_urls,
            'created_at': disease.created_at,
            'updated_at': disease.updated_at
        }
        return Response(data)
    except Disease.DoesNotExist:
        return Response({'error': 'Disease not found'}, status=404)

@api_view(['GET'])
@permission_classes([AllowAny])
def api_dashboard(request):
    """API endpoint for dashboard data"""
    # Recent predictions (alerts)
    user_id = get_request_user_id(request, None)
    recent_scope = Prediction.objects.filter(all_predictions__user_id=user_id) if user_id else Prediction.objects.all()
    recent_predictions = recent_scope.order_by('-created_at')[:10]
    
    # Disease statistics
    total_predictions = Prediction.objects.filter(all_predictions__user_id=user_id).count() if user_id else Prediction.objects.count()
    diseases_count = Disease.objects.count()
    
    # Disease distribution
    prediction_scope = Prediction.objects.filter(all_predictions__user_id=user_id) if user_id else Prediction.objects.all()
    disease_distribution = prediction_scope.values('disease_name').annotate(
        count=Count('id'),
        avg_confidence=Avg('confidence')
    ).order_by('-count')
    
    # Weekly predictions
    today = timezone.now().date()
    week_ago = today - timedelta(days=7)
    weekly_scope = Prediction.objects.filter(created_at__date__range=[week_ago, today])
    if user_id:
        weekly_scope = weekly_scope.filter(all_predictions__user_id=user_id)
    weekly_predictions = weekly_scope.values('created_at__date').annotate(
        count=Count('id'),
        date=F('created_at__date')
    ).order_by('date')
    
    data = {
        'recent_predictions': [{
            'id': p.id,
            'disease_name': p.disease_name,
            'confidence': p.confidence,
            'created_at': p.created_at,
            'image_url': p.image.url if p.image else None
        } for p in recent_predictions],
        'stats': {
            'total_predictions': total_predictions,
            'diseases_count': diseases_count,
            'disease_distribution': list(disease_distribution),
            'weekly_predictions': list(weekly_predictions)
        }
    }
    
    return Response(data)

@api_view(['GET'])
@permission_classes([AllowAny])
def api_report(request):
    """API endpoint for report data"""
    # Date range (last 30 days by default)
    end_date = timezone.now().date()
    start_date = end_date - timedelta(days=30)
    
    # Get date range from query params if provided
    start_date_param = request.query_params.get('start_date')
    end_date_param = request.query_params.get('end_date')
    
    if start_date_param:
        try:
            start_date = datetime.strptime(start_date_param, '%Y-%m-%d').date()
        except (ValueError, TypeError):
            pass
    
    if end_date_param:
        try:
            end_date = datetime.strptime(end_date_param, '%Y-%m-%d').date()
        except (ValueError, TypeError):
            pass
    
    user_id = get_request_user_id(request, None)

    # Filter predictions by date range and active user
    predictions = Prediction.objects.filter(created_at__date__range=[start_date, end_date])
    if user_id:
        predictions = predictions.filter(all_predictions__user_id=user_id)
    
    # Total predictions
    total_predictions = predictions.count()
    
    # Disease distribution
    disease_distribution = predictions.values('disease_name').annotate(
        count=Count('id'),
        avg_confidence=Avg('confidence'),
        min_confidence=Min('confidence'),
        max_confidence=Max('confidence')
    ).order_by('-count')
    
    # Daily predictions
    daily_predictions = predictions.values('created_at__date').annotate(
        date=F('created_at__date'),
        count=Count('id'),
        diseases=Count('disease_name', distinct=True)
    ).order_by('date')
    
    # Confidence distribution
    confidence_distribution = {
        '0-20': predictions.filter(confidence__lte=20).count(),
        '21-40': predictions.filter(confidence__gt=20, confidence__lte=40).count(),
        '41-60': predictions.filter(confidence__gt=40, confidence__lte=60).count(),
        '61-80': predictions.filter(confidence__gt=60, confidence__lte=80).count(),
        '81-100': predictions.filter(confidence__gt=80).count()
    }
    
    data = {
        'date_range': {
            'start_date': start_date,
            'end_date': end_date
        },
        'total_predictions': total_predictions,
        'disease_distribution': list(disease_distribution),
        'daily_predictions': list(daily_predictions),
        'confidence_distribution': confidence_distribution
    }
    
    return Response(data)

def _get_recommendation(disease_name):
    """Helper function to get recommendations for a disease"""
    try:
        disease = Disease.objects.get(name__iexact=disease_name)
        return {
            'prevention': disease.prevention_methods,
            'treatment': disease.treatment_recommendations,
            'symptoms': disease.symptoms,
            'causes': disease.causes
        }
    except Disease.DoesNotExist:
        return {
            'prevention': 'General prevention methods include proper plant spacing, good air circulation, and avoiding overhead watering.',
            'treatment': 'Consult with a local agricultural expert for specific treatment recommendations.',
            'symptoms': 'Symptoms may vary. Please consult a plant disease specialist.',
            'causes': 'Causes may include fungal, bacterial, or environmental factors.'
        }

def identify(request):
    """Disease identification page"""
    return render(request, 'identify.html')

def library(request):
    """Disease library page with search and filter"""
    diseases = Disease.objects.all()
    
    # Search functionality
    search_query = request.GET.get('search', '')
    if search_query:
        diseases = diseases.filter(
            Q(name__icontains=search_query) |
            Q(symptoms__icontains=search_query) |
            Q(causes__icontains=search_query)
        )
    
    # Filter by plant part
    plant_part_filter = request.GET.get('plant_part', '')
    if plant_part_filter:
        diseases = diseases.filter(affected_plant_part=plant_part_filter)
    
    # Get unique plant parts for filter dropdown
    plant_parts = Disease.objects.values_list('affected_plant_part', flat=True).distinct()
    
    # Prepare diseases with image URLs
    diseases_list = []
    for disease in diseases:
        image_url = None
        if disease.image_path:
            # Image is in "All Disease" folder, served as static file
            image_url = f"/static/{disease.image_path}"
        diseases_list.append({
            'disease': disease,
            'image_url': image_url
        })
    
    context = {
        'diseases_list': diseases_list,
        'search_query': search_query,
        'plant_part_filter': plant_part_filter,
        'plant_parts': plant_parts,
        'plant_part_choices': Disease.AFFECTED_PART_CHOICES,
    }
    return render(request, 'library.html', context)

def library_detail(request, disease_name):
    """Disease detail page"""
    disease = get_object_or_404(Disease, name=disease_name)
    
    # Get main image path if available
    image_url = None
    if disease.image_path:
        # Image is in "All Disease" folder, served as static file
        image_url = f"/static/{disease.image_path}"
    
    # Get multiple images from oversample/Leaf folder (5+ different images)
    additional_images = []
    
    # Map disease names to folder names in dataset
    disease_folder_map = {
        'Anthracnose': 'Anthracnose',
        'Black Spot': 'Black Spot',
        'Brown Spot': 'Brown Spot',
        'Root Rot': 'Root Rot',
        'Soft Rot': 'Soft Rot',
        'Stem Rot': 'Stem Rot',
        'Stem_Canker': 'Stem_Canker',
        'Twig Blight': 'Twig Blight',
        'White Spot': 'White Spot',
    }
    
    folder_name = disease_folder_map.get(disease_name, disease_name)
    
    # Get base directory (Activity-AppDev folder)
    # views.py is in: pitaya_project/disease/views.py
    # So we need to go up 3 levels: disease -> pitaya_project -> Activity-AppDev
    current_file = Path(__file__).resolve()
    # Go up: disease -> pitaya_project -> Activity-AppDev (3 levels)
    base_dir = current_file.parent.parent.parent
    
    # Verify the path is correct by checking if oversample exists
    if not (base_dir / 'oversample').exists():
        # Fallback: use absolute path
        base_dir = Path('E:/Activity-AppDev')
    
    # Prioritize oversample/Leaf folder where all images are
    oversample_path = base_dir / 'oversample' / 'Leaf' / folder_name
    
    all_image_files = []
    
    # First, try oversample/Leaf folder (main source)
    if oversample_path.exists() and oversample_path.is_dir():
        # Use listdir and filter instead of glob for better reliability
        try:
            for file in oversample_path.iterdir():
                if file.is_file():
                    ext = file.suffix.lower()
                    if ext in ['.jpg', '.jpeg', '.png', '.webp']:
                        all_image_files.append(str(file))
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Error reading oversample folder {oversample_path}: {e}")
    else:
        import logging
        logger = logging.getLogger(__name__)
        logger.warning(f"Oversample path does not exist: {oversample_path}")
    
    # If not enough images, also check other locations
    if len(all_image_files) < 5:
        dataset_locations = [
            base_dir / 'data_splits' / 'train' / folder_name,
            base_dir / 'data_splits' / 'test' / folder_name,
            base_dir / 'data_splits' / 'validation' / folder_name,
        ]
        
        for dataset_path in dataset_locations:
            if dataset_path.exists() and dataset_path.is_dir():
                try:
                    for file in dataset_path.iterdir():
                        if file.is_file():
                            ext = file.suffix.lower()
                            if ext in ['.jpg', '.jpeg', '.png']:
                                all_image_files.append(str(file))
                except Exception as e:
                    print(f"Error reading dataset folder {dataset_path}: {e}")
    
    # Remove duplicates and get unique images (by filename)
    seen_files = set()
    unique_images = []
    for img_path in all_image_files:
        filename = os.path.basename(img_path)
        if filename not in seen_files:
            seen_files.add(filename)
            unique_images.append(img_path)
    
    # Randomly select 5-10 different images (or all if less than 5)
    if len(unique_images) > 0:
        num_images = min(max(5, len(unique_images)), 10)  # At least 5, max 10
        selected_images = random.sample(unique_images, min(num_images, len(unique_images)))
        
        for img_path in selected_images:
            # Convert to relative path for serving
            try:
                # Ensure img_path is a Path object
                img_path_obj = Path(img_path)
                rel_path = os.path.relpath(str(img_path_obj), str(base_dir))
                # Use forward slashes for URL
                url_path = rel_path.replace('\\', '/')
                # URL encode the path properly (encode each segment)
                from urllib.parse import quote
                url_parts = url_path.split('/')
                url_path_encoded = '/'.join(quote(part, safe='') for part in url_parts)
                additional_images.append({
                    'url': f"/dataset_image/{url_path_encoded}",
                    'filename': os.path.basename(img_path)
                })
            except (ValueError, Exception) as e:
                # If path is not relative, skip this image
                import logging
                logger = logging.getLogger(__name__)
                logger.error(f"Error processing image path {img_path}: {e}")
                continue
    
    context = {
        'disease': disease,
        'image_url': image_url,
        'additional_images': additional_images,
    }
    return render(request, 'library_detail.html', context)

def alerts(request):
    """Alerts page - recent disease alerts and notifications"""
    predictions = list(Prediction.objects.all()[:15])
    context = {
        'predictions': predictions,
        'total_alerts': Prediction.objects.count(),
    }
    return render(request, 'alerts.html', context)

def overview(request):
    """Yield Prediction page: drone preview, yield charts, historical comparison"""
    all_predictions = Prediction.objects.all()
    disease_counts = {}
    for prediction in all_predictions:
        disease_counts[prediction.disease_name] = disease_counts.get(prediction.disease_name, 0) + 1
    total_scans = all_predictions.count()
    unique_diseases = len(disease_counts)
    avg_confidence = sum(p.confidence for p in all_predictions) / total_scans if all_predictions.exists() else 0
    # Predicted yield and historical (simulated last 6 periods)
    predicted_yield = round(85 + (100 - avg_confidence) * 0.15, 1) if total_scans else 85.0
    predicted_yield = min(100, max(0, predicted_yield))
    yield_historical = []
    if total_scans >= 1:
        step = max(1, total_scans // 6)
        for i in range(6):
            idx = min(i * step, total_scans - 1)
            preds_slice = list(all_predictions)[: idx + 1]
            n = len(preds_slice)
            avg = sum(p.confidence for p in preds_slice) / n if n else 0
            yield_historical.append(round(80 + (100 - avg) * 0.2, 1))
    else:
        yield_historical = [82, 84, 83, 86, 85, 85]
    context = {
        'total_scans': total_scans,
        'unique_diseases': unique_diseases,
        'avg_confidence': avg_confidence,
        'disease_counts': disease_counts,
        'top_disease': max(disease_counts.items(), key=lambda x: x[1])[0] if disease_counts else 'None',
        'predicted_yield': predicted_yield,
        'yield_historical': yield_historical,
        'yield_labels_json': mark_safe(json.dumps(['Week 1', 'Week 2', 'Week 3', 'Week 4', 'Week 5', 'Current'])),
        'yield_historical_json': mark_safe(json.dumps(yield_historical)),
    }
    return render(request, 'overview.html', context)

def report(request):
    """Reports page: downloadable PDF, summary charts and tables"""
    all_predictions = Prediction.objects.all()
    disease_counts = {}
    for prediction in all_predictions:
        disease_counts[prediction.disease_name] = disease_counts.get(prediction.disease_name, 0) + 1
    total_scans = all_predictions.count()
    infected_count = total_scans
    healthy_count = 0
    avg_confidence = sum(p.confidence for p in all_predictions) / total_scans if all_predictions.exists() else 0
    estimated_yield = round(85 + (100 - avg_confidence) * 0.15, 1) if total_scans else 85.0
    estimated_yield = min(100, max(0, estimated_yield))
    context = {
        'total_scans': total_scans,
        'healthy_scans': healthy_count,
        'infected_scans': infected_count,
        'active_diseases': len(disease_counts),
        'disease_counts': disease_counts,
        'avg_confidence': avg_confidence,
        'estimated_yield': estimated_yield,
        'top_disease': max(disease_counts.items(), key=lambda x: x[1])[0] if disease_counts else 'None',
        'disease_labels_json': mark_safe(json.dumps(list(disease_counts.keys()))),
        'disease_values_json': mark_safe(json.dumps(list(disease_counts.values()))),
    }
    return render(request, 'report.html', context)

def profile(request):
    """Profile page with prediction history"""
    predictions = Prediction.objects.all()[:20]  # Get last 20 predictions
    context = {
        'predictions': predictions
    }
    return render(request, 'profile.html', context)

@require_http_methods(["POST"])
def predict(request):
    """Handle image upload and predict disease using Flask API"""
    try:
        # Get image file from request
        if 'file' not in request.FILES:
            return JsonResponse({'error': 'No file provided'}, status=400)
        
        image_file = request.FILES['file']
        file_content = image_file.read()
        
        # Send to Flask API with original filename to preserve extension
        response = requests.post(FLASK_API_URL, files={'file': (image_file.name, file_content)})
        
        if response.status_code != 200:
            return JsonResponse({'error': 'Prediction failed: ' + response.text}, status=500)
        
        # Parse Flask response
        predictions = response.json()
        
        if not predictions or len(predictions) == 0:
            return JsonResponse({'error': 'No prediction returned'}, status=500)
        
        result = predictions[0]
        confidence = result['predicted_class_acuracy']
        
        # Determine confidence level
        CONFIDENCE_THRESHOLD_LOW = 70.0
        CONFIDENCE_THRESHOLD_MEDIUM = 85.0
        
        if confidence < CONFIDENCE_THRESHOLD_LOW:
            result['confidence_level'] = 'low'
            result['confidence_warning'] = True
            result['confidence_message'] = 'Low confidence prediction. Please verify manually or upload a clearer image.'
        elif confidence < CONFIDENCE_THRESHOLD_MEDIUM:
            result['confidence_level'] = 'medium'
            result['confidence_warning'] = False
            result['confidence_message'] = 'Moderate confidence. Consider verifying the result.'
        else:
            result['confidence_level'] = 'high'
            result['confidence_warning'] = False
            result['confidence_message'] = 'High confidence prediction.'
        
        # Get disease information from database
        try:
            disease = Disease.objects.get(name=result['predicted_class_name'])
            result['disease_info'] = {
                'symptoms': disease.symptoms,
                'causes': disease.causes,
                'prevention': disease.prevention_methods,
                'treatment': disease.treatment_recommendations,
                'affected_part': disease.get_affected_plant_part_display(),
            }
        except Disease.DoesNotExist:
            result['disease_info'] = {
                'symptoms': 'Information not available',
                'causes': 'Information not available',
                'prevention': 'Information not available',
                'treatment': 'Information not available',
                'affected_part': 'Unknown',
            }
        
        # Get top 3 predictions for low-confidence cases
        if result.get('rounded_predictions'):
            predictions_list = [
                {'name': class_name, 'confidence': conf}
                for class_name, conf in zip(
                    ['Anthracnose', 'Black Spot', 'Brown Spot', 'Root Rot', 
                     'Soft Rot', 'Stem Rot', 'Stem_Canker', 'Twig Blight', 'White Spot'],
                    result['rounded_predictions']
                )
            ]
            predictions_list.sort(key=lambda x: x['confidence'], reverse=True)
            result['top_predictions'] = predictions_list[:3]
        
        # Save prediction to database
        try:
            user_id = get_request_user_id(request, 'default_user')
            Prediction.objects.create(
                disease_name=result['predicted_class_name'],
                confidence=confidence,
                all_predictions={
                    'rounded_predictions': result.get('rounded_predictions', []),
                    'predictions': result.get('predictions', []),
                    'confidence_level': result['confidence_level'],
                    'top_predictions': result.get('top_predictions', []),
                    'user_id': user_id,
                }
            )
        except Exception as e:
            # Log error but don't fail the prediction
            print(f"Warning: Could not save prediction to database: {str(e)}")
        
        return JsonResponse(result)
    
    except Exception as e:
        return JsonResponse({'error': 'Server error: ' + str(e)}, status=500)

from django.views.decorators.csrf import ensure_csrf_cookie
from django.http import JsonResponse

@ensure_csrf_cookie
def get_csrf(request):
    """Return CSRF token for API clients (e.g. React frontend)."""
    from django.middleware.csrf import get_token
    return JsonResponse({'csrfToken': get_token(request)})


@require_GET
def api_dashboard(request):
    """JSON API: dashboard KPIs, charts, recent alerts for React frontend."""
    all_predictions = Prediction.objects.all()
    total_scans = all_predictions.count()
    disease_counts = {}
    for p in all_predictions:
        disease_counts[p.disease_name] = disease_counts.get(p.disease_name, 0) + 1
    high_conf = 70.0
    diseased_count = sum(1 for p in all_predictions if p.confidence >= high_conf)
    total_plants = max(total_scans + 8, 12)
    healthy_plants = max(0, total_plants - diseased_count)
    avg_conf = sum(p.confidence for p in all_predictions) / total_scans if total_scans else 0
    predicted_yield_pct = round(85 + (100 - avg_conf) * 0.15, 1) if total_scans else 85.0
    predicted_yield_pct = min(100, max(0, predicted_yield_pct))
    predicted_yield_kg = int(2800 + (total_plants - diseased_count) * 2.5)  # example formula
    yield_trend = []
    if total_scans >= 1:
        step = max(1, total_scans // 6)
        for i in range(6):
            idx = min(i * step, total_scans - 1)
            preds_slice = list(all_predictions)[: idx + 1]
            n = len(preds_slice)
            avg = sum(p.confidence for p in preds_slice) / n if n else 0
            yield_trend.append(round(80 + (100 - avg) * 0.2, 1))
    else:
        yield_trend = [85, 86, 85.5, 87, 86.5, 85]
    labels = list(disease_counts.keys())
    values = list(disease_counts.values())
    colors = ['#2f6a21', '#3c7b2b', '#4d9c3d', '#6bb854', '#8b7355', '#b8860b', '#c0392b', '#2980b9', '#6c5ce7']
    disease_distribution = [{'name': n, 'value': v, 'fill': colors[i % len(colors)]} for i, (n, v) in enumerate(disease_counts.items())]
    if not disease_distribution:
        disease_distribution = [{'name': 'No data', 'value': 1, 'fill': '#e5e7eb'}]
    recent = list(Prediction.objects.all()[:5])
    alerts = [
        {
            'id': p.id,
            'disease': p.disease_name,
            'confidence': round(p.confidence, 1),
            'severity': 'high' if p.confidence >= 85 else ('medium' if p.confidence >= 70 else 'low'),
            'date': p.created_at.isoformat(),
        }
        for p in recent
    ]
    return JsonResponse({
        'kpis': {
            'totalPlants': total_plants,
            'healthyPlants': healthy_plants,
            'diseasedPlants': diseased_count,
            'predictedYieldKg': predicted_yield_kg,
        },
        'monthlyYield': [{'month': f'P{i+1}', 'yield': int(2800 + yield_trend[i] * 6)} for i in range(6)],
        'diseaseOccurrence': [{'name': n, 'count': v} for n, v in disease_counts.items()],
        'diseaseDistribution': disease_distribution,
        'yieldTrend': yield_trend,
        'alerts': alerts,
    })


@require_GET
def api_yield(request):
    """JSON API: yield estimation and historical data for React frontend."""
    all_predictions = Prediction.objects.all()
    total_scans = all_predictions.count()
    disease_counts = {}
    for p in all_predictions:
        disease_counts[p.disease_name] = disease_counts.get(p.disease_name, 0) + 1
    avg_confidence = sum(p.confidence for p in all_predictions) / total_scans if all_predictions.exists() else 0
    predicted_yield = round(85 + (100 - avg_confidence) * 0.15, 1) if total_scans else 85.0
    predicted_yield = min(100, max(0, predicted_yield))
    yield_historical = []
    if total_scans >= 1:
        step = max(1, total_scans // 6)
        for i in range(6):
            idx = min(i * step, total_scans - 1)
            preds_slice = list(all_predictions)[: idx + 1]
            n = len(preds_slice)
            avg = sum(p.confidence for p in preds_slice) / n if n else 0
            yield_historical.append(round(80 + (100 - avg) * 0.2, 1))
    else:
        yield_historical = [82, 84, 83, 86, 85, 85]
    labels = ['Week 1', 'Week 2', 'Week 3', 'Week 4', 'Week 5', 'Current']
    estimation = [{'period': labels[i], 'yieldKg': int(800 + yield_historical[i] * 2)} for i in range(6)]
    by_block = [{'block': f'Block {c}', 'yieldKg': int(900 + (yield_historical[i % 6] * 3))} for i, c in enumerate('ABCD')]
    historical = [
        {'season': '2022 Q4', 'yieldKg': 2850},
        {'season': '2023 Q1', 'yieldKg': 2920},
        {'season': '2023 Q2', 'yieldKg': 3100},
        {'season': '2023 Q3', 'yieldKg': 2980},
        {'season': '2023 Q4', 'yieldKg': 3200},
        {'season': '2024 Q1', 'yieldKg': 3350},
        {'season': '2024 Q2 (est.)', 'yieldKg': int(3200 + predicted_yield * 0.5)},
    ]
    return JsonResponse({
        'predictedYield': predicted_yield,
        'yieldEstimation': estimation,
        'yieldByBlock': by_block,
        'historicalYield': historical,
    })


def dataset_image(request, image_path):
    """Serve images from dataset folders"""
    from django.http import FileResponse, Http404
    from urllib.parse import unquote
    import mimetypes
    import logging
    
    logger = logging.getLogger(__name__)
    
    # Get base directory (Activity-AppDev folder) - same as library_detail
    current_file = Path(__file__).resolve()
    base_dir = current_file.parent.parent.parent  # 3 levels up
    
    # Verify the path is correct
    if not (base_dir / 'oversample').exists():
        # Fallback: use absolute path
        base_dir = Path('E:/Activity-AppDev')
    
    logger.info(f"Base dir: {base_dir}, Requested path: {image_path}")
    
    # Decode URL-encoded paths (handles spaces and special characters)
    try:
        # Decode the entire path - handle multiple levels of encoding
        decoded_path = unquote(image_path, encoding='utf-8')
        # Sometimes paths are double-encoded, decode again if needed
        if '%' in decoded_path:
            decoded_path = unquote(decoded_path, encoding='utf-8')
        
        logger.info(f"Decoded path: {decoded_path}")
        
        # Split by / and handle each part
        path_parts = decoded_path.split('/')
        # Remove empty parts
        path_parts = [p for p in path_parts if p]
        
        # Build the full path using Path for proper handling
        full_path = base_dir
        for part in path_parts:
            full_path = full_path / part
        
        logger.info(f"Constructed full path: {full_path}")
        
        # Security: ensure path is within base_dir
        try:
            resolved_base = base_dir.resolve()
            resolved_path = full_path.resolve()
            # Check if resolved path is within base directory
            resolved_path.relative_to(resolved_base)
        except (ValueError, OSError) as e:
            logger.error(f"Security check failed: {e}, Base: {resolved_base}, Path: {resolved_path}")
            raise Http404(f"Image not found (security check failed): {str(e)}")
        
        # Check if file exists
        if not full_path.exists():
            # Try alternative path construction (handle Windows path issues)
            alt_path = base_dir / decoded_path.replace('/', os.sep)
            logger.info(f"Trying alternative path: {alt_path}")
            if alt_path.exists() and alt_path.is_file():
                full_path = alt_path
            else:
                logger.error(f"File not found. Tried: {full_path} and {alt_path}")
                raise Http404(f"Image file not found. Tried: {full_path} and {alt_path}")
        
        if full_path.is_file():
            # Determine content type
            content_type, _ = mimetypes.guess_type(str(full_path))
            if not content_type:
                # Default based on extension
                if full_path.suffix.lower() in ['.jpg', '.jpeg']:
                    content_type = 'image/jpeg'
                elif full_path.suffix.lower() == '.png':
                    content_type = 'image/png'
                elif full_path.suffix.lower() == '.webp':
                    content_type = 'image/webp'
                else:
                    content_type = 'image/jpeg'
            
            logger.info(f"Serving image: {full_path} as {content_type}")
            return FileResponse(open(full_path, 'rb'), content_type=content_type)
        else:
            logger.error(f"Path exists but is not a file: {full_path}")
            raise Http404(f"Path exists but is not a file: {full_path}")
    except Http404:
        raise
    except Exception as e:
        logger.error(f"Error serving image {image_path}: {e}", exc_info=True)
        raise Http404(f"Error serving image: {str(e)}")
