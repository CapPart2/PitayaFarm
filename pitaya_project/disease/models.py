from django.db import models

class Disease(models.Model):
    """Disease library entry with comprehensive information"""
    AFFECTED_PART_CHOICES = [
        ('leaf', 'Leaf'),
        ('stem', 'Stem'),
        ('root', 'Root'),
        ('fruit', 'Fruit'),
        ('all', 'All Parts'),
    ]
    
    name = models.CharField(max_length=100, unique=True)
    affected_plant_part = models.CharField(max_length=20, choices=AFFECTED_PART_CHOICES)
    symptoms = models.TextField(help_text="Detailed description of disease symptoms")
    causes = models.TextField(help_text="Causes and contributing factors")
    prevention_methods = models.TextField(help_text="Prevention strategies")
    treatment_recommendations = models.TextField(help_text="Treatment and management recommendations")
    image_path = models.CharField(max_length=255, blank=True, help_text="Path to disease image")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['name']
        verbose_name = 'Disease'
        verbose_name_plural = 'Diseases'
    
    def __str__(self):
        return self.name

class Prediction(models.Model):
    """Store disease prediction history"""
    disease_name = models.CharField(max_length=100)
    confidence = models.FloatField()  # Store as percentage (0-100)
    all_predictions = models.JSONField(default=dict)  # Store all class predictions
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Prediction'
        verbose_name_plural = 'Predictions'
    
    def __str__(self):
        return f"{self.disease_name} ({self.confidence}%) - {self.created_at}"


class DiseaseImage(models.Model):
    """Store metadata for disease images in dataset"""
    disease = models.ForeignKey(Disease, on_delete=models.CASCADE, related_name='images')
    image_path = models.CharField(max_length=500)
    file_name = models.CharField(max_length=255)
    file_size = models.IntegerField(help_text="File size in bytes")
    image_width = models.IntegerField(null=True, blank=True)
    image_height = models.IntegerField(null=True, blank=True)
    verified = models.BooleanField(default=False, help_text="Whether image has been verified as accurate")
    source = models.CharField(max_length=255, blank=True, help_text="Source of the image")
    notes = models.TextField(blank=True, help_text="Additional notes about the image")
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Disease Image'
        verbose_name_plural = 'Disease Images'
    
    def __str__(self):
        return f"{self.disease.name} - {self.file_name}"
