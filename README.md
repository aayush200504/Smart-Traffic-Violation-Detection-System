# 🚦 Smart Traffic Violation Detection System

<p align="center">
  <b>An AI-powered system for automated traffic enforcement using Computer Vision</b>
</p>

---

## 📌 Project Overview

**Smart Traffic Violation Detection System** is a computer vision-based project designed to automate traffic law enforcement. It detects violations such as **red light jumping and wrong lane driving**, extracts vehicle number plates using **ANPR**, and generates official **e-Challans (digital fines)**.

The system reduces manual effort, increases accuracy, and improves traffic monitoring efficiency by using intelligent image processing techniques.

---

## 🧠 Core Domain — Computer Vision

This project is based on **Computer Vision (CV)** — a field of AI that enables machines to understand and interpret images and videos similar to human vision.

---

## 🔍 ANPR Pipeline (How It Works)
Input Image
↓
Plate Detection
↓
Image Preprocessing
↓
OCR (Text Recognition)
↓
Output: Vehicle Number

---

## ⚙️ Stage 1 — Plate Detection

Multiple techniques are used to ensure accurate detection:

- HSV Color Segmentation  
- Morphological Blackhat Operation  
- Canny Edge Detection + Contours  

**Why multiple methods?**  
Because real-world conditions (lighting, angle, plate color) vary, and a single method is not reliable.

---

## 🧪 Stage 2 — Image Preprocessing

| Technique | Purpose |
|----------|--------|
| CLAHE | Improve contrast |
| Otsu Thresholding | Automatic binarization |
| Adaptive Threshold | Handle uneven lighting |
| Bilateral Filter | Reduce noise while preserving edges |

---

## 🔡 Stage 3 — OCR (Text Recognition)

### 🥇 EasyOCR (Primary)
- Deep learning-based (CRNN)
- High accuracy in real-world conditions

### 🥈 Tesseract (Fallback)
- Rule-based OCR
- Used when needed

---

## 🎯 Smart Plate Selection

The system uses a scoring mechanism based on:
- Valid Indian plate format  
- Confidence scores  
- Frequency of detection  

This ensures the most accurate number plate is selected.

---

## 🚨 Violation Detection

| Violation | Technique |
|----------|----------|
| Red Light | HSV Color Detection |
| Wrong Lane | Canny Edge + Hough Transform |
| Helmet / Seatbelt | Rule-based detection |

---

## 🧱 System Architecture
```text
User (Frontend)
        ↓
Flask Backend (Python)
        ↓
+---------------------------+
| ANPR Module               |
| Violation Detection       |
| PDF Generator (e-Challan) |
| Email Notifier            |
+---------------------------+
        ↓
SQLite Database
```


---

## 🛠️ Tech Stack

- **Python**
- **OpenCV**
- **EasyOCR**
- **Tesseract OCR**
- **Flask**
- **SQLite**
- **ReportLab**

---

## 📂 Project Structure
```text
Traffic-Violation-System/
├── database/            # SQLite database files for violations and owners
├── modules/             # Core logic (ANPR, Violation Detection, PDF Generation)
├── static/              # CSS, JavaScript, and UI assets
├── templates/           # HTML templates for the Flask web interface
├── venv/                # Python virtual environment
├── app.py               # Main Flask application entry point
├── presentation_notes.md # Technical documentation and project theory
├── requirements.txt     # List of Python dependencies
└── run.txt              # Execution instructions or scripts
```

---

## 🔄 System Flow

1. User uploads vehicle image  
2. System detects number plate (ANPR)  
3. Violation is identified  
4. e-Challan is generated  
5. Data stored in database  
6. Notification sent to user  
7. Payment tracked via dashboard  

---

## 🚀 Future Enhancements

- Live CCTV Integration  
- RTO Database Integration  
- Online Payment Gateway  
- Mobile Application Support  

---

## 🌍 Domain

- Computer Vision (CV)  
- Intelligent Transportation Systems (ITS)  

---

<p align="center">
  <b>Built to transform traffic enforcement using AI 🚀</b>
</p>
