"""
Management command to scan directories for disease images and create metadata records
Run: python manage.py scan_dataset <directory_path> [--disease-name DISEASE_NAME]
"""
from django.core.management.base import BaseCommand, CommandError
from disease.dataset_utils import scan_directory_for_images, get_dataset_statistics
from pathlib import Path

class Command(BaseCommand):
    help = 'Scan directory for disease images and create metadata records'

    def add_arguments(self, parser):
        parser.add_argument('directory_path', type=str, help='Path to directory containing images')
        parser.add_argument(
            '--disease-name',
            type=str,
            help='Disease name if all images in directory are for one disease',
            default=None
        )
        parser.add_argument(
            '--stats',
            action='store_true',
            help='Show dataset statistics after scanning'
        )

    def handle(self, *args, **options):
        directory_path = options['directory_path']
        disease_name = options['disease_name']
        
        if not Path(directory_path).exists():
            raise CommandError(f"Directory does not exist: {directory_path}")
        
        self.stdout.write(f"Scanning directory: {directory_path}")
        if disease_name:
            self.stdout.write(f"Filtering for disease: {disease_name}")
        
        try:
            created_images = scan_directory_for_images(directory_path, disease_name)
            
            self.stdout.write(self.style.SUCCESS(
                f'\n✅ Scan complete!\n'
                f'   Created metadata records: {len(created_images)} images'
            ))
            
            if options['stats']:
                stats = get_dataset_statistics()
                self.stdout.write('\n📊 Dataset Statistics:')
                self.stdout.write(f'   Total images: {stats["total_images"]}')
                self.stdout.write(f'   Verified images: {stats["verified_images"]}')
                self.stdout.write(f'   Unverified images: {stats["unverified_images"]}')
                self.stdout.write(f'   Total diseases: {stats["total_diseases"]}')
                self.stdout.write('\n   Images per disease:')
                for disease_name, counts in stats['diseases'].items():
                    self.stdout.write(f'     {disease_name}: {counts["total"]} (verified: {counts["verified"]})')
        
        except Exception as e:
            raise CommandError(f"Error scanning directory: {str(e)}")
