from django.contrib import admin
from .models import Disease, Prediction, DiseaseImage

@admin.register(Disease)
class DiseaseAdmin(admin.ModelAdmin):
    list_display = ('name', 'affected_plant_part', 'created_at')
    list_filter = ('affected_plant_part', 'created_at')
    search_fields = ('name', 'symptoms', 'causes')
    readonly_fields = ('created_at', 'updated_at')
    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'affected_plant_part', 'image_path')
        }),
        ('Disease Details', {
            'fields': ('symptoms', 'causes', 'prevention_methods', 'treatment_recommendations')
        }),
        ('Metadata', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

@admin.register(DiseaseImage)
class DiseaseImageAdmin(admin.ModelAdmin):
    list_display = ('disease', 'file_name', 'verified', 'file_size', 'created_at')
    list_filter = ('verified', 'disease', 'created_at')
    search_fields = ('disease__name', 'file_name', 'source')
    readonly_fields = ('created_at',)
    fieldsets = (
        ('Image Information', {
            'fields': ('disease', 'image_path', 'file_name', 'file_size', 'image_width', 'image_height')
        }),
        ('Metadata', {
            'fields': ('verified', 'source', 'notes', 'created_at')
        }),
    )

@admin.register(Prediction)
class PredictionAdmin(admin.ModelAdmin):
    list_display = ('disease_name', 'confidence', 'created_at')
    list_filter = ('disease_name', 'created_at')
    search_fields = ('disease_name',)
    readonly_fields = ('created_at', 'all_predictions')
    ordering = ('-created_at',)
