"""
Model Validation Utilities
Functions for evaluating model performance and logging validation results
"""
import json
import os
from datetime import datetime
from pathlib import Path
import numpy as np
from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score, classification_report, confusion_matrix

def calculate_validation_metrics(y_true, y_pred, class_names):
    """
    Calculate comprehensive validation metrics for the disease detection model.
    
    Args:
        y_true: True labels (ground truth)
        y_pred: Predicted labels
        class_names: List of class names
    
    Returns:
        dict: Dictionary containing all validation metrics
    """
    # Overall metrics
    accuracy = accuracy_score(y_true, y_pred)
    precision_macro = precision_score(y_true, y_pred, average='macro', zero_division=0)
    recall_macro = recall_score(y_true, y_pred, average='macro', zero_division=0)
    f1_macro = f1_score(y_true, y_pred, average='macro', zero_division=0)
    
    precision_weighted = precision_score(y_true, y_pred, average='weighted', zero_division=0)
    recall_weighted = recall_score(y_true, y_pred, average='weighted', zero_division=0)
    f1_weighted = f1_score(y_true, y_pred, average='weighted', zero_division=0)
    
    # Per-class metrics
    precision_per_class = precision_score(y_true, y_pred, average=None, zero_division=0)
    recall_per_class = recall_score(y_true, y_pred, average=None, zero_division=0)
    f1_per_class = f1_score(y_true, y_pred, average=None, zero_division=0)
    
    # Confusion matrix
    cm = confusion_matrix(y_true, y_pred)
    
    # Per-class details
    per_class_metrics = {}
    for i, class_name in enumerate(class_names):
        per_class_metrics[class_name] = {
            'precision': float(precision_per_class[i]),
            'recall': float(recall_per_class[i]),
            'f1_score': float(f1_per_class[i]),
            'support': int(np.sum(y_true == i))
        }
    
    # Classification report as string
    report = classification_report(y_true, y_pred, target_names=class_names, zero_division=0)
    
    metrics = {
        'overall': {
            'accuracy': float(accuracy),
            'precision_macro': float(precision_macro),
            'recall_macro': float(recall_macro),
            'f1_macro': float(f1_macro),
            'precision_weighted': float(precision_weighted),
            'recall_weighted': float(recall_weighted),
            'f1_weighted': float(f1_weighted),
        },
        'per_class': per_class_metrics,
        'confusion_matrix': cm.tolist(),
        'classification_report': report,
        'num_classes': len(class_names),
        'total_samples': len(y_true),
    }
    
    return metrics

def log_validation_results(metrics, model_name='leaf_disease_model', test_set_name='test'):
    """
    Log validation results to a JSON file.
    
    Args:
        metrics: Dictionary of validation metrics from calculate_validation_metrics
        model_name: Name of the model being validated
        test_set_name: Name of the test set (e.g., 'test', 'validation')
    
    Returns:
        str: Path to the saved log file
    """
    # Create logs directory if it doesn't exist
    logs_dir = Path(__file__).resolve().parent.parent.parent / 'model_validation_logs'
    logs_dir.mkdir(exist_ok=True)
    
    # Create filename with timestamp
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    log_filename = f"{model_name}_{test_set_name}_{timestamp}.json"
    log_path = logs_dir / log_filename
    
    # Prepare log data
    log_data = {
        'timestamp': datetime.now().isoformat(),
        'model_name': model_name,
        'test_set_name': test_set_name,
        'metrics': metrics
    }
    
    # Save to JSON
    with open(log_path, 'w') as f:
        json.dump(log_data, f, indent=2)
    
    # Also save a summary text file
    summary_path = logs_dir / f"{model_name}_{test_set_name}_{timestamp}_summary.txt"
    with open(summary_path, 'w') as f:
        f.write(f"Model Validation Report\n")
        f.write(f"{'='*50}\n\n")
        f.write(f"Model: {model_name}\n")
        f.write(f"Test Set: {test_set_name}\n")
        f.write(f"Timestamp: {log_data['timestamp']}\n\n")
        f.write(f"Overall Metrics:\n")
        f.write(f"  Accuracy: {metrics['overall']['accuracy']:.4f} ({metrics['overall']['accuracy']*100:.2f}%)\n")
        f.write(f"  Precision (Macro): {metrics['overall']['precision_macro']:.4f}\n")
        f.write(f"  Recall (Macro): {metrics['overall']['recall_macro']:.4f}\n")
        f.write(f"  F1-Score (Macro): {metrics['overall']['f1_macro']:.4f}\n")
        f.write(f"  Precision (Weighted): {metrics['overall']['precision_weighted']:.4f}\n")
        f.write(f"  Recall (Weighted): {metrics['overall']['recall_weighted']:.4f}\n")
        f.write(f"  F1-Score (Weighted): {metrics['overall']['f1_weighted']:.4f}\n\n")
        f.write(f"Per-Class Metrics:\n")
        for class_name, class_metrics in metrics['per_class'].items():
            f.write(f"  {class_name}:\n")
            f.write(f"    Precision: {class_metrics['precision']:.4f}\n")
            f.write(f"    Recall: {class_metrics['recall']:.4f}\n")
            f.write(f"    F1-Score: {class_metrics['f1_score']:.4f}\n")
            f.write(f"    Support: {class_metrics['support']}\n\n")
        f.write(f"\nClassification Report:\n")
        f.write(metrics['classification_report'])
    
    return str(log_path)

def get_latest_validation_results(model_name='leaf_disease_model'):
    """
    Get the most recent validation results for a model.
    
    Args:
        model_name: Name of the model
    
    Returns:
        dict: Latest validation metrics or None if not found
    """
    logs_dir = Path(__file__).resolve().parent.parent.parent / 'model_validation_logs'
    
    if not logs_dir.exists():
        return None
    
    # Find all log files for this model
    log_files = list(logs_dir.glob(f"{model_name}_*.json"))
    
    if not log_files:
        return None
    
    # Get the most recent file
    latest_file = max(log_files, key=os.path.getctime)
    
    with open(latest_file, 'r') as f:
        return json.load(f)
