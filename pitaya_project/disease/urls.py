from django.urls import path, re_path
from django.views.decorators.csrf import csrf_exempt
from . import views

urlpatterns = [
    # Template views
    path('', views.home, name='home'),
    path('identify/', views.identify, name='identify'),
    path('library/', views.library, name='library'),
    path('library/<str:disease_name>/', views.library_detail, name='library_detail'),
    path('alerts/', views.alerts, name='alerts'),
    path('overview/', views.overview, name='overview'),
    path('report/', views.report, name='report'),
    path('profile/', views.profile, name='profile'),
    
    # API endpoints
    path('api/csrf/', csrf_exempt(views.get_csrf), name='get_csrf_token'),
    path('api/predict/', csrf_exempt(views.predict), name='predict'),
    path('api/dashboard/', views.api_dashboard, name='api_dashboard'),
    path('api/yield/', views.api_yield, name='api_yield'),
    path('api/dataset_image/<str:filename>/', views.serve_dataset_image, name='dataset_image'),
    
    # Library API endpoints
    path('api/library/', views.library_list, name='api_library_list'),
    path('api/library/<str:disease_name>/', views.library_detail_api, name='api_library_detail'),
    
    # Report API endpoints
    path('api/report/', views.api_report, name='api_report'),
    
    # Alerts API endpoints
    path('api/alerts/', views.api_alerts, name='api_alerts'),
    path('api/alerts/<int:alert_id>/', views.api_alert_detail, name='api_alert_detail'),
]
