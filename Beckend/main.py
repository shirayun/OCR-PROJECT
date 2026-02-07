from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.responses import FileResponse, StreamingResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
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

# Allow CORS from frontend during development
# For development allow all origins to avoid CORS issues (change in production)
origins = ["*"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-SR"],
)


# הגדרת Tesseract (בשרת אמיתי זה יהיה בלי נתיב קשיח)
pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

OUTPUT_DIR = "output"
os.makedirs(OUTPUT_DIR, exist_ok=True)


# Health Check Endpoint
@app.get("/health")
async def health_check():
    """Check if the API is running and Tesseract is available"""
    return {
        "status": "ok",
        "service": "OCR SR API",
        "version": "1.0.0",
        "platform": platform.system(),
        "timestamp": datetime.datetime.utcnow().isoformat()
    }


# Status Endpoint for PWA
@app.get("/api/status")
async def api_status():
    """Get API status and capabilities"""
    try:
        # Try to use tesseract to check if it's working
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


@app.post("/scan")
async def scan_image(file: UploadFile = File(...)):
    try:
        # קריאת הקובץ שהגיע מהלקוח
        contents = await file.read()
        print(f"[scan] Received file: {file.filename}, size={len(contents)} bytes")
        np_img = np.frombuffer(contents, np.uint8)
        img = cv2.imdecode(np_img, cv2.IMREAD_COLOR)

        if img is None:
            print("[scan] Error: could not decode image")
            raise HTTPException(status_code=400, detail="לא ניתן לטעון תמונה")

        # עיבוד כמו בקוד שלך (שמרתי בדיוק כפי שביקשת)
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        gray = cv2.GaussianBlur(gray, (3, 3), 0)

        text = pytesseract.image_to_string(gray, config="--psm 6")

        match = re.search(r"\b(\d{8})\b", text)

        if match:
            code = match.group(1)
        else:
            candidates = re.findall(r"\d{8,9}", text)
            code = candidates[0] if candidates else "NOT FOUND"

        # הוספת שורה ל־Excel הקיים (או יצירת קובץ חדש אם אין אחד)
        excel_path = os.path.join(OUTPUT_DIR, "results.xlsx")
        timestamp = datetime.datetime.utcnow().isoformat()
        new_row = {"SR": code, "timestamp": timestamp}

        if os.path.exists(excel_path):
            try:
                existing = pd.read_excel(excel_path)
                updated = pd.concat([existing, pd.DataFrame([new_row])], ignore_index=True)
            except Exception:
                # אם יש בעיה בקריאה — נחלץ וניצור קובץ חדש
                updated = pd.DataFrame([new_row])
        else:
            updated = pd.DataFrame([new_row])

        # כתיבה בטוחה: כתיבה לקובץ זמני עם סיומת .xlsx ואז החלפה אטומית
        with tempfile.NamedTemporaryFile(delete=False, suffix='.xlsx') as tf:
            temp_path = tf.name
        updated.to_excel(temp_path, index=False)
        os.replace(temp_path, excel_path)

        print(f"[scan] Done SR={code} rows={len(updated)}")
        return {"sr": code, "rows": len(updated)}

    except HTTPException:
        raise
    except Exception as e:
        print("[scan] Exception:")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/download-results")
def download_results():
    excel_path = os.path.join(OUTPUT_DIR, "results.xlsx")
    if os.path.exists(excel_path):
        return FileResponse(
            excel_path,
            media_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            filename='results.xlsx'
        )
    return JSONResponse(
        status_code=404,
        content={"error": "No results file found"}
    )


@app.get("/api/results-count")
def get_results_count():
    """Get the number of scanned results"""
    excel_path = os.path.join(OUTPUT_DIR, "results.xlsx")
    try:
        if os.path.exists(excel_path):
            df = pd.read_excel(excel_path)
            return {"count": len(df), "last_updated": os.path.getmtime(excel_path)}
        return {"count": 0, "last_updated": None}
    except Exception as e:
        print(f"Error reading results: {e}")
        return {"count": 0, "error": str(e)}


@app.post("/scan")
async def scan_image(file: UploadFile = File(...)):
    try:
        # קריאת הקובץ שהגיע מהלקוח
        contents = await file.read()
        print(f"[scan] Received file: {file.filename}, size={len(contents)} bytes")
        np_img = np.frombuffer(contents, np.uint8)
        img = cv2.imdecode(np_img, cv2.IMREAD_COLOR)

        if img is None:
            print("[scan] Error: could not decode image")
            raise HTTPException(status_code=400, detail="לא ניתן לטעון תמונה")

        # עיבוד כמו בקוד שלך (שמרתי בדיוק כפי שביקשת)
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        gray = cv2.GaussianBlur(gray, (3, 3), 0)

        text = pytesseract.image_to_string(gray, config="--psm 6")

        match = re.search(r"\b(\d{8})\b", text)

        if match:
            code = match.group(1)
        else:
            candidates = re.findall(r"\d{8,9}", text)
            code = candidates[0] if candidates else "NOT FOUND"

        # הוספת שורה ל־Excel הקיים (או יצירת קובץ חדש אם אין אחד)
        excel_path = os.path.join(OUTPUT_DIR, "results.xlsx")
        timestamp = datetime.datetime.utcnow().isoformat()
        new_row = {"SR": code, "timestamp": timestamp}

        if os.path.exists(excel_path):
            try:
                existing = pd.read_excel(excel_path)
                updated = pd.concat([existing, pd.DataFrame([new_row])], ignore_index=True)
            except Exception:
                # אם יש בעיה בקריאה — נחלץ וניצור קובץ חדש
                updated = pd.DataFrame([new_row])
        else:
            updated = pd.DataFrame([new_row])

        # כתיבה בטוחה: כתיבה לקובץ זמני עם סיומת .xlsx ואז החלפה אטומית
        with tempfile.NamedTemporaryFile(delete=False, suffix='.xlsx') as tf:
            temp_path = tf.name
        updated.to_excel(temp_path, index=False)
        os.replace(temp_path, excel_path)

        print(f"[scan] Done SR={code} rows={len(updated)}")
        return {"sr": code, "rows": len(updated)}

    except HTTPException:
        raise
    except Exception as e:
        print("[scan] Exception:")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/download-results")
def download_results():
    excel_path = os.path.join(OUTPUT_DIR, "results.xlsx")
    if os.path.exists(excel_path):
        return FileResponse(
            excel_path,
            media_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            filename='results.xlsx'
        )
    return {"error": "no file"}
