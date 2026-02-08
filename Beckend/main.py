from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import cv2
import pytesseract
import re
import numpy as np
import pandas as pd
import os
import io
import datetime
import traceback
import tempfile
import platform

app = FastAPI(title="OCR SR API", version="1.0.0")

# תיקיית output
OUTPUT_DIR = "output"
os.makedirs(OUTPUT_DIR, exist_ok=True)

# הגדרת Tesseract
pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

# CORS
origins = ["*"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-SR", "Content-Disposition"],
)

# Health check
@app.get("/health")
async def health_check():
    return {
        "status": "ok",
        "service": "OCR SR API",
        "version": "1.0.0",
        "platform": platform.system(),
        "timestamp": datetime.datetime.utcnow().isoformat()
    }

# API Status
@app.get("/api/status")
async def api_status():
    try:
        test_img = np.zeros((10, 10), dtype=np.uint8)
        pytesseract.image_to_string(test_img)
        tesseract_ok = True
    except Exception as e:
        tesseract_ok = False
        print(f"Tesseract check error: {e}")

    return {
        "backend_running": True,
        "tesseract_available": tesseract_ok,
        "output_dir": OUTPUT_DIR,
        "platform": platform.system()
    }

# Scan Image
@app.post("/scan")
async def scan_image(file: UploadFile = File(...)):
    try:
        contents = await file.read()
        np_img = np.frombuffer(contents, np.uint8)
        img = cv2.imdecode(np_img, cv2.IMREAD_COLOR)

        if img is None:
            raise HTTPException(status_code=400, detail="לא ניתן לטעון תמונה")

        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        gray = cv2.GaussianBlur(gray, (3, 3), 0)
        text = pytesseract.image_to_string(gray, config="--psm 6")

        match = re.search(r"\b(\d{8})\b", text)
        code = match.group(1) if match else (re.findall(r"\d{8,9}", text)[0] if re.findall(r"\d{8,9}", text) else "NOT FOUND")

        excel_path = os.path.join(OUTPUT_DIR, "results.xlsx")
        timestamp = datetime.datetime.utcnow().isoformat()
        new_row = {"SR": code, "timestamp": timestamp}

        if os.path.exists(excel_path):
            try:
                existing = pd.read_excel(excel_path)
                updated = pd.concat([existing, pd.DataFrame([new_row])], ignore_index=True)
            except Exception:
                updated = pd.DataFrame([new_row])
        else:
            updated = pd.DataFrame([new_row])

        with tempfile.NamedTemporaryFile(delete=False, suffix='.xlsx') as tf:
            temp_path = tf.name
        updated.to_excel(temp_path, index=False)
        os.replace(temp_path, excel_path)

        return {"sr": code, "rows": len(updated)}

    except HTTPException:
        raise
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

# Download results
@app.get("/download-results")
def download_results():
    excel_path = os.path.join(OUTPUT_DIR, "results.xlsx")
    if os.path.exists(excel_path):
        return FileResponse(
            excel_path,
            media_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            filename='results.xlsx',
            headers={"Content-Disposition": "attachment; filename=results.xlsx"}
        )
    return JSONResponse(status_code=404, content={"error": "No results file found"})

# Count results
@app.get("/api/results-count")
def get_results_count():
    excel_path = os.path.join(OUTPUT_DIR, "results.xlsx")
    try:
        if os.path.exists(excel_path):
            df = pd.read_excel(excel_path)
            return {"count": len(df), "last_updated": os.path.getmtime(excel_path)}
        return {"count": 0, "last_updated": None}
    except Exception as e:
        return {"count": 0, "error": str(e)}

# Serve Angular build properly - MUST BE LAST!
# FastAPI יראה את כל הקבצים ב־static כמו ש־Angular מצפה להם
app.mount("/", StaticFiles(directory="static", html=True), name="static")
