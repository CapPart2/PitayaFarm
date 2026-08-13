# PitayaFarm System Architecture

**Project:** Dragon Fruit Disease Detection and Management System  
**Generated:** 2026-08-13 12:29:02

## System Overview

PitayaFarm is a comprehensive web-based system for dragon fruit disease detection and farm management. The system integrates machine learning models for automated disease identification and mature fruit detection with a user-friendly web interface.

## High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              USER INTERFACE                                   │
│                   React.js Frontend Application                               │
│                    (Authentication, Dashboard, Upload)                        │
└────────────────────────────┬────────────────────────────────────────────────┘
                             │ HTTP/REST API
                             │ JSON Communication
┌────────────────────────────┴────────────────────────────────────────────────┐
│                           BACKEND SERVER                                      │
│                        Flask Application (app.py)                              │
│  ┌─────────────────────────────────────────────────────────────────────────┐  │
│  │                      API Endpoints                                       │  │
│  │  /predict, /upload, /reports, /alerts, /auth, /dashboard                │  │
│  └─────────────────────────────────────────────────────────────────────────┘  │
│  ┌─────────────────────────────────────────────────────────────────────────┐  │
│  │                    Business Logic Layer                                  │  │
│  │  Image Validation, Disease Detection, User Management, Report Gen       │  │
│  └─────────────────────────────────────────────────────────────────────────┘  │
└────────────────────────────┬────────────────────────────────────────────────┘
                             │
        ┌────────────────────┼────────────────────┐
        │                    │                    │
┌───────┴────────┐  ┌───────┴────────┐  ┌───────┴────────┐
│  ML Model 1     │  │  ML Model 2     │  │   Database      │
│  Disease        │  │  Mature Fruit   │  │   SQLite        │
│  Detection      │  │  Detection      │  │   (User Data,   │
│  (Keras CNN)    │  │  (YOLOv8)       │  │    Reports,     │
│                 │  │  (External)     │  │    Alerts)      │
│  - MobileNetV2  │  │  - YOLOv8n      │  │                 │
│  - 9 Classes    │  │  - 1 Class      │  │  - Users        │
│  - 92.4% Acc    │  │  - Object Det   │  │  - Reports      │
└─────────────────┘  └─────────────────┘  │  - Alerts       │
                                          │  - Translations │
                                          └─────────────────┘
```

## Component Details

### 1. Frontend Layer (React.js)

**Technology Stack:**
- React.js (JavaScript framework)
- Context API for state management
- Axios for API communication
- CSS Modules for styling

**Key Components:**
- **Landing Page**: Public-facing landing page
- **Authentication**: Login/Registration system
- **Dashboard**: Main user interface for farm management
- **Image Upload**: Drag-and-drop image upload interface
- **Results Display**: Disease detection results and recommendations
- **Report Generation**: PDF report generation for detected diseases
- **Alert System**: User-configurable disease alerts

**State Management:**
- `AuthContext`: User authentication state
- `UserContext`: User-specific data and preferences

### 2. Backend Layer (Flask)

**Technology Stack:**
- Flask (Python web framework)
- Flask-CORS (Cross-origin resource sharing)
- TensorFlow/Keras (ML model inference)
- PIL/Pillow (Image processing)
- SQLite (Database)

**Key Modules:**
- `app.py`: Main Flask application with API endpoints
- `improved_disease_detection.py`: Disease detection logic
- `database_models.py`: Database schema and operations
- `disease_database.py`: Disease information management
- `dashboard_api.py`: Dashboard-specific API endpoints

**API Endpoints:**

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/predict` | POST | Image upload and disease prediction |
| `/upload` | POST | File upload for evidence storage |
| `/reports` | GET/POST | Report generation and retrieval |
| `/alerts` | GET/POST/PUT | User alert management |
| `/auth/*` | POST | User authentication endpoints |
| `/dashboard/*` | GET | Dashboard data endpoints |
| `/translations` | GET | Multi-language support |

### 3. Machine Learning Models

#### Model 1: Disease Detection (Primary)

**Framework:** TensorFlow/Keras  
**Architecture:** MobileNetV2-based CNN  
**Input:** 224x224 RGB images  
**Output:** 9 disease classes + confidence scores

**Model Architecture:**
```
Input Layer (224, 224, 3)
    ↓
MobileNetV2 (Pre-trained, Transfer Learning)
    ↓
Global Average Pooling
    ↓
Batch Normalization
    ↓
Dense Layer (512 units, ReLU)
    ↓
Dropout (0.5)
    ↓
Dense Layer (128 units, ReLU)
    ↓
Dropout (0.3)
    ↓
Output Layer (9 units, Softmax)
```

**Disease Classes:**
1. Anthracnose
2. Black Spot
3. Brown Spot
4. Root Rot
5. Soft Rot
6. Stem Rot
7. Stem_Canker
8. Twig Blight
9. White Spot

**Performance:**
- Overall Accuracy: 92.40%
- Macro F1-Score: 0.9284
- Model Size: ~34 MB (leaf_disease_model.keras)
- Parameters: 3,052,617

**Preprocessing Pipeline:**
1. Image validation (stem subject detection)
2. Resize to 224x224 pixels
3. RGB normalization (1/255)
4. Batch processing for inference

#### Model 2: Mature Fruit Detection (Secondary)

**Framework:** YOLOv8 (Ultralytics)  
**Architecture:** YOLOv8 Nano  
**Input:** 640x640 RGB images  
**Output:** Bounding boxes + confidence scores

**Location:** Separate project (`e:\Immature and Mature DF\`)  
**Purpose:** Detect fully red/mature dragon fruit in images  
**Class:** Single class (fully_red_dragon_fruit)

### 4. Database Layer

**Database:** SQLite  
**Schema:** Multiple tables for different data types

**Key Tables:**
- `users`: User authentication and profile data
- `reports`: Disease detection reports
- `alerts`: User-configured disease alerts
- `translations`: Multi-language support
- `disease_info`: Disease reference information

**Database Management:**
- `database_models.py`: Database models and ORM-like operations
- Migration scripts for schema updates
- Backup functionality

### 5. Image Processing Pipeline

**Input Validation:**
- File type validation (PNG, JPG, JPEG, GIF)
- File size limits
- Stem subject validation (color-based filtering)
- Image quality assessment

**Preprocessing:**
- Resize to model input dimensions
- Color space conversion (RGB)
- Normalization (pixel value scaling)
- Batch processing for efficiency

**Post-Processing:**
- Confidence threshold application
- Non-maximum suppression (for YOLO)
- Result formatting
- Recommendation generation

## Data Flow

### Disease Detection Flow:

```
User Upload Image
    ↓
Frontend Validation
    ↓
Send to /predict Endpoint
    ↓
Backend Image Validation
    ↓
Preprocessing (Resize, Normalize)
    ↓
ML Model Inference
    ↓
Post-Processing (Thresholds)
    ↓
Database Storage
    ↓
Return Results to Frontend
    ↓
Display Results + Recommendations
```

### Authentication Flow:

```
User Login
    ↓
Frontend: AuthContext
    ↓
POST /auth/login
    ↓
Backend: Verify Credentials
    ↓
Generate Session Token
    ↓
Return User Data + Token
    ↓
Frontend: Store in Context
    ↓
Subsequent Requests: Include Token
```

## Deployment Architecture

**Development Environment:**
- Local Flask server
- React development server
- Local SQLite database

**Production Deployment:**
- **Backend:** Railway (PaaS)
- **Frontend:** Vercel or Railway
- **Database:** Railway PostgreSQL (production)
- **File Storage:** Railway Volumes (uploaded images)
- **Environment Variables:** Secure configuration management

**Configuration Files:**
- `Dockerfile`: Container configuration
- `requirements.txt`: Python dependencies
- `Procfile`: Process management
- `render.yaml`: Deployment configuration

## Security Considerations

**Authentication:**
- Session-based authentication
- User ID scoping (X-Pitaya-User header)
- Password hashing (secure storage)

**Data Validation:**
- Input validation on all endpoints
- File type restrictions
- Image content validation
- SQL injection prevention (parameterized queries)

**API Security:**
- CORS configuration
- Rate limiting (potential implementation)
- Error handling without information leakage

## Performance Optimization

**ML Model:**
- Transfer learning (MobileNetV2 pre-trained)
- Batch processing
- Confidence thresholds to reduce false positives
- Image quality preprocessing

**API:**
- Efficient database queries
- Image compression for storage
- Caching strategies (potential implementation)
- Lazy loading for large datasets

**Frontend:**
- Code splitting
- Lazy loading components
- Image optimization
- State management optimization

## Technology Stack Summary

| Layer | Technology | Purpose |
|-------|-----------|---------|
| Frontend | React.js | User interface |
| Backend | Flask | API server |
| ML/DL | TensorFlow/Keras | Disease detection |
| ML/DL | YOLOv8 | Fruit detection |
| Database | SQLite/PostgreSQL | Data persistence |
| Image Processing | PIL/Pillow | Image manipulation |
| Deployment | Railway/Vercel | Cloud hosting |

## Integration Points

**External Services:**
- Email service (for alerts - potential)
- Cloud storage (for images - Railway Volumes)
- Database hosting (Railway PostgreSQL)

**Third-Party Libraries:**
- TensorFlow/Keras (ML framework)
- Ultralytics (YOLO implementation)
- Flask (Web framework)
- React (Frontend framework)

## Monitoring and Logging

**Logging:**
- Python logging module
- Error tracking
- Request logging
- Model inference logging

**Potential Monitoring:**
- API response times
- Model inference latency
- User activity tracking
- Error rate monitoring

## Future Enhancements

**Potential Improvements:**
- Real-time camera integration
- Mobile application
- Additional disease classes
- Weather data integration
- IoT sensor integration
- Advanced analytics dashboard
- Multi-tenant support

---

**Document Version:** 1.0  
**Last Updated:** 2026-08-13  
**System Status:** Production Ready