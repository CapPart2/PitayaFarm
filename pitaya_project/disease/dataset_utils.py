"""
Dataset Management Utilities
Functions for managing disease image datasets, including verification and metadata storage
"""
import os
from pathlib import Path
from PIL import Image
from django.core.files.uploadedfile import UploadedFile
from .models import Disease, DiseaseImage

def verify_image_accuracy(image_path, expected_disease_name):
    """
    Verify if an image accurately represents the disease.
    This is a placeholder for future ML-based verification.
    
    Args:
        image_path: Path to the image file
        expected_disease_name: Name of the disease the image should represent
    
    Returns:
        dict: Verification result with 'is_accurate' boolean and 'confidence' float
    """
    # Placeholder: In production, this could use a separate verification model
    # For now, we assume images are accurate if they exist and are valid
    try:
        img = Image.open(image_path)
        img.verify()
        return {
            'is_accurate': True,
            'confidence': 1.0,
            'message': 'Image verified successfully'
        }
    except Exception as e:
        return {
            'is_accurate': False,
            'confidence': 0.0,
            'message': f'Image verification failed: {str(e)}'
        }

def get_image_metadata(image_path):
    """
    Extract metadata from an image file.
    
    Args:
        image_path: Path to the image file
    
    Returns:
        dict: Metadata including size, dimensions, format
    """
    try:
        img = Image.open(image_path)
        file_stat = os.stat(image_path)
        
        return {
            'file_size': file_stat.st_size,
            'image_width': img.width,
            'image_height': img.height,
            'format': img.format,
            'mode': img.mode,
        }
    except Exception as e:
        return {
            'file_size': 0,
            'image_width': None,
            'image_height': None,
            'format': None,
            'mode': None,
            'error': str(e)
        }

def label_image_by_disease(image_path, disease_name, source='', notes='', verified=False):
    """
    Label an image with disease category and store metadata.
    
    Args:
        image_path: Path to the image file
        disease_name: Name of the disease
        source: Source of the image (optional)
        notes: Additional notes (optional)
        verified: Whether the image has been verified (default: False)
    
    Returns:
        DiseaseImage: Created DiseaseImage object
    """
    try:
        disease = Disease.objects.get(name=disease_name)
    except Disease.DoesNotExist:
        raise ValueError(f"Disease '{disease_name}' not found in database")
    
    # Get image metadata
    metadata = get_image_metadata(image_path)
    
    # Verify image accuracy
    verification = verify_image_accuracy(image_path, disease_name)
    
    # Create DiseaseImage record
    disease_image = DiseaseImage.objects.create(
        disease=disease,
        image_path=str(image_path),
        file_name=os.path.basename(image_path),
        file_size=metadata['file_size'],
        image_width=metadata['image_width'],
        image_height=metadata['image_height'],
        verified=verified and verification['is_accurate'],
        source=source,
        notes=notes or verification.get('message', '')
    )
    
    return disease_image

def scan_directory_for_images(directory_path, disease_name=None):
    """
    Scan a directory for disease images and create metadata records.
    
    Args:
        directory_path: Path to directory containing images
        disease_name: Optional disease name if all images in directory are for one disease
    
    Returns:
        list: List of created DiseaseImage objects
    """
    directory = Path(directory_path)
    if not directory.exists():
        raise ValueError(f"Directory does not exist: {directory_path}")
    
    created_images = []
    image_extensions = {'.jpg', '.jpeg', '.png', '.gif', '.bmp'}
    
    for file_path in directory.rglob('*'):
        if file_path.suffix.lower() in image_extensions:
            # Try to infer disease name from directory structure
            if not disease_name:
                # Check if parent directory matches a disease name
                parent_dir = file_path.parent.name
                try:
                    Disease.objects.get(name=parent_dir)
                    disease_name = parent_dir
                except Disease.DoesNotExist:
                    continue
            
            if disease_name:
                try:
                    disease_image = label_image_by_disease(
                        str(file_path),
                        disease_name,
                        source=f'Scanned from {directory_path}',
                        verified=False
                    )
                    created_images.append(disease_image)
                except Exception as e:
                    print(f"Error processing {file_path}: {str(e)}")
    
    return created_images

def get_dataset_statistics():
    """
    Get statistics about the disease image dataset.
    
    Returns:
        dict: Statistics including total images, images per disease, verified count
    """
    total_images = DiseaseImage.objects.count()
    verified_images = DiseaseImage.objects.filter(verified=True).count()
    
    disease_stats = {}
    for disease in Disease.objects.all():
        count = DiseaseImage.objects.filter(disease=disease).count()
        verified_count = DiseaseImage.objects.filter(disease=disease, verified=True).count()
        disease_stats[disease.name] = {
            'total': count,
            'verified': verified_count
        }
    
    return {
        'total_images': total_images,
        'verified_images': verified_images,
        'unverified_images': total_images - verified_images,
        'diseases': disease_stats,
        'total_diseases': Disease.objects.count()
    }
