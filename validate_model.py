"""
Model Validation Script
Run this script to evaluate the trained model and log validation results.
Usage: python validate_model.py
"""
import os
import sys
import django

# Setup Django
sys.path.append(os.path.join(os.path.dirname(__file__), 'pitaya_project'))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'pitaya_project.settings')
django.setup()

import numpy as np
import tensorflow as tf
from tensorflow.keras.preprocessing.image import ImageDataGenerator
from disease.model_validation import calculate_validation_metrics, log_validation_results

# Model and data paths
MODEL_PATH = 'leaf_disease_model.keras'
TEST_DATA_DIR = 'data_splits/test'
CLASS_NAMES = [
    'Anthracnose',
    'Black Spot',
    'Brown Spot',
    'Root Rot',
    'Soft Rot',
    'Stem Rot',
    'Stem_Canker',
    'Twig Blight',
    'White Spot'
]

def main():
    print("🔍 Model Validation Script")
    print("=" * 50)
    
    # Check if model exists
    if not os.path.exists(MODEL_PATH):
        print(f"❌ Model file not found: {MODEL_PATH}")
        print("   Please train the model first using Disease.ipynb")
        return
    
    # Check if test data exists
    if not os.path.exists(TEST_DATA_DIR):
        print(f"❌ Test data directory not found: {TEST_DATA_DIR}")
        print("   Please run the data splitting in Disease.ipynb first")
        return
    
    print(f"✅ Loading model: {MODEL_PATH}")
    try:
        model = tf.keras.models.load_model(MODEL_PATH)
        print(f"   Model loaded successfully")
        print(f"   Input shape: {model.input_shape}")
        print(f"   Output shape: {model.output_shape}")
    except Exception as e:
        print(f"❌ Error loading model: {str(e)}")
        return
    
    # Load test data
    print(f"\n✅ Loading test data from: {TEST_DATA_DIR}")
    datagen = ImageDataGenerator(rescale=1./255)
    
    try:
        test_data = datagen.flow_from_directory(
            TEST_DATA_DIR,
            target_size=(224, 224),
            batch_size=32,
            class_mode='categorical',
            color_mode='rgb',
            shuffle=False,
            classes=CLASS_NAMES
        )
        print(f"   Found {test_data.samples} test images")
        print(f"   Number of classes: {test_data.num_classes}")
    except Exception as e:
        print(f"❌ Error loading test data: {str(e)}")
        return
    
    # Get predictions
    print("\n🔮 Running predictions on test set...")
    y_pred_probs = model.predict(test_data, verbose=1)
    y_pred = np.argmax(y_pred_probs, axis=1)
    y_true = test_data.classes
    
    # Calculate metrics
    print("\n📊 Calculating validation metrics...")
    metrics = calculate_validation_metrics(y_true, y_pred, CLASS_NAMES)
    
    # Display results
    print("\n" + "=" * 50)
    print("📈 VALIDATION RESULTS")
    print("=" * 50)
    print(f"\nOverall Metrics:")
    print(f"  Accuracy: {metrics['overall']['accuracy']:.4f} ({metrics['overall']['accuracy']*100:.2f}%)")
    print(f"  Precision (Macro): {metrics['overall']['precision_macro']:.4f}")
    print(f"  Recall (Macro): {metrics['overall']['recall_macro']:.4f}")
    print(f"  F1-Score (Macro): {metrics['overall']['f1_macro']:.4f}")
    print(f"  Precision (Weighted): {metrics['overall']['precision_weighted']:.4f}")
    print(f"  Recall (Weighted): {metrics['overall']['recall_weighted']:.4f}")
    print(f"  F1-Score (Weighted): {metrics['overall']['f1_weighted']:.4f}")
    
    print(f"\nPer-Class Metrics:")
    for class_name, class_metrics in metrics['per_class'].items():
        print(f"  {class_name}:")
        print(f"    Precision: {class_metrics['precision']:.4f}")
        print(f"    Recall: {class_metrics['recall']:.4f}")
        print(f"    F1-Score: {class_metrics['f1_score']:.4f}")
        print(f"    Support: {class_metrics['support']}")
    
    # Log results
    print("\n💾 Logging validation results...")
    log_path = log_validation_results(metrics, model_name='leaf_disease_model', test_set_name='test')
    print(f"✅ Results logged to: {log_path}")
    
    print("\n" + "=" * 50)
    print("✅ Validation complete!")
    print("=" * 50)

if __name__ == '__main__':
    main()
