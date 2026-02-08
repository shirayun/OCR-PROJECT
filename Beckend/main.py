from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.responses import FileResponse, StreamingResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import cv2
import pytesseract
import re
import numpy as np
import pandas as pd
import io
import datetime
import platform
import traceback

app = FastAPI(title="OCR SR API", version="1.0.0")

# ===== Serve Angular frontend =====
# כל הקבצים בתוך תיקיית 'static' יוגשו כ־frontend
app.mount("/", StaticFiles(directory="static", html=True), name="static")

# ===== CORS =====
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ===== OCR Results Buffer =====
results_buffer: list[dict] = []

# ===== Health Endpoint =====
@app.get("/health")
def health():
    return {
        "status": "ok",
        "stored_rows": len(results_buffer),
        "platform": platform.system(),
        "timestamp": datetime.datetime.utcnow().isoformat()
    }

# ===== Scan Endpoint =====
@app.post("/scan")
async def scan_image(file: UploadFile = File(...)):
    try:
        contents = await file.read()
        np_img = np.frombuffer(contents, np.uint8)
        img = cv2.imdecode(np_img, cv2.IMREAD_COLOR)

        if img is None:
            raise HTTPException(status_code=400, detail="Invalid image")

        # עיבוד OCR
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        gray = cv2.GaussianBlur(gray, (3, 3), 0)
        text = pytesseract.image_to_string(gray, config="--psm 6")

        # חיפוש קוד SR
        match = re.search(r"\b(\d{8,9})\b", text)
        code = match.group(1) if match else "NOT FOUND"

        # הוספת שורה ל־buffer
        results_buffer.append({
            "SR": code,
            "timestamp": datetime.datetime.utcnow().isoformat()
        })

        return {"sr": code, "stored_rows": len(results_buffer)}

    except Exception:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail="Error processing image")

# ===== Download Excel =====
@app.get("/download-results")
def download_results():
    if not results_buffer:
        return JSONResponse(status_code=404, content={"error": "No scans yet"})

    df = pd.DataFrame(results_buffer)
    stream = io.BytesIO()
    df.to_excel(stream, index=False)
    stream.seek(0)

    return StreamingResponse(
        stream,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=results.xlsx"}
    )
