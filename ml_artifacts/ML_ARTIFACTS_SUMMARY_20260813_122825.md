# Dragon Fruit Disease Detection - ML Artifacts Summary

**Generated:** 2026-08-13 12:29:02

## Model Architecture

- **Framework:** Keras/TensorFlow CNN
- **Input Shape:** (None, 224, 224, 3)
- **Output Shape:** (None, 9)
- **Total Parameters:** 3,052,617
- **Number of Layers:** 9

### Layer Details

| Layer | Type | Input Shape | Output Shape | Parameters |
|-------|------|-------------|--------------|------------|
| input_layer_1 | InputLayer | N/A | N/A | 0 |
| mobilenetv2_1.00_224 | Functional | (None, 224, 224, 3) | (None, 7, 7, 1280) | 2,257,984 |
| global_average_pooling2d | GlobalAveragePooling2D | N/A | N/A | 0 |
| batch_normalization | BatchNormalization | N/A | N/A | 5,120 |
| dense | Dense | N/A | N/A | 655,872 |
| dropout | Dropout | N/A | N/A | 0 |
| dense_1 | Dense | N/A | N/A | 131,328 |
| dropout_1 | Dropout | N/A | N/A | 0 |
| dense_2 | Dense | N/A | N/A | 2,313 |

## Training Information

- **Training Notebook:** Disease.ipynb
- **Framework:** TensorFlow/Keras
- **Model Type:** Convolutional Neural Network (CNN)
- **Image Size:** (224, 224)
- **Color Mode:** RGB
- **Preprocessing:** Pixel value rescaling (1/255)
- **Data Augmentation:** ImageDataGenerator with rescale=1./255

## Dataset Information

- **Test Directory:** oversample\Leaf_clean\test
- **Number of Classes:** 9
- **Total Test Samples:** 329
- **Classes:** Anthracnose, Black Spot, Brown Spot, Root Rot, Soft Rot, Stem Rot, Stem_Canker, Twig Blight, White Spot

## Validation Results

- **Overall Accuracy:** 0.9240 (92.40%)
- **Precision (Macro):** 0.9284
- **Recall (Macro):** 0.9355
- **F1-Score (Macro):** 0.9284
- **Precision (Weighted):** 0.9332
- **Recall (Weighted):** 0.9240
- **F1-Score (Weighted):** 0.9259

### Per-Class Performance

| Disease | Precision | Recall | F1-Score | Support |
|---------|-----------|--------|----------|---------|
| Anthracnose | 0.8182 | 0.8710 | 0.8438 | 31 |
| Black Spot | 0.7308 | 1.0000 | 0.8444 | 19 |
| Brown Spot | 1.0000 | 0.8958 | 0.9451 | 48 |
| Root Rot | 1.0000 | 0.9333 | 0.9655 | 30 |
| Soft Rot | 1.0000 | 0.8913 | 0.9425 | 46 |
| Stem Rot | 0.9796 | 0.9231 | 0.9505 | 52 |
| Stem_Canker | 0.8611 | 0.9394 | 0.8986 | 66 |
| Twig Blight | 1.0000 | 1.0000 | 1.0000 | 8 |
| White Spot | 0.9655 | 0.9655 | 0.9655 | 29 |

## Classification Report

```
              precision    recall  f1-score   support

 Anthracnose       0.82      0.87      0.84        31
  Black Spot       0.73      1.00      0.84        19
  Brown Spot       1.00      0.90      0.95        48
    Root Rot       1.00      0.93      0.97        30
    Soft Rot       1.00      0.89      0.94        46
    Stem Rot       0.98      0.92      0.95        52
 Stem_Canker       0.86      0.94      0.90        66
 Twig Blight       1.00      1.00      1.00         8
  White Spot       0.97      0.97      0.97        29

    accuracy                           0.92       329
   macro avg       0.93      0.94      0.93       329
weighted avg       0.93      0.92      0.93       329
```

## Confusion Matrix

```
Predicted Classes ->
Actual Classes v
----------------------------------------------------------------------
                | Anthracnose Black Spot Brown Spot Root Rot Soft Rot Stem Rot Stem_Canker Twig Blight White Spot
----------------------------------------------------------------------
Anthracnose     |       27        1        0        0        0        0        3        0        0
Black Spot      |        0       19        0        0        0        0        0        0        0
Brown Spot      |        0        2       43        0        0        0        2        0        1
Root Rot        |        0        1        0       28        0        1        0        0        0
Soft Rot        |        3        0        0        0       41        0        2        0        0
Stem Rot        |        0        2        0        0        0       48        2        0        0
Stem_Canker     |        3        1        0        0        0        0       62        0        0
Twig Blight     |        0        0        0        0        0        0        0        8        0
White Spot      |        0        0        0        0        0        0        1        0       28
```

## Generated Files

- `model_architecture_20260813_122825.json` - Model architecture details (JSON)
- `training_history_20260813_122825.json` - Training history summary (JSON)
- `validation_metrics_20260813_122825.json` - Complete validation metrics (JSON)
- `classification_report_20260813_122825.txt` - Classification report (TXT)
- `confusion_matrix_20260813_122825.txt` - Confusion matrix (TXT)
