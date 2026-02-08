from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.responses import StreamingResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import cv2
import pytesseract
import re
import numpy as np
import pandas as pd
import io
import datetime
import platform

app = FastAPI(title="OCR SR API", version="1.0.0")

# ===== מאגר בזיכרון =====
results_buffer: list[dict] = []

# ===== CORS =====
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ===== ROOT (חשוב!) =====
@app.get("/")
def root():
    return {
        "status": "ok",
        "message": "OCR SR API is running",
        "stored_rows": len(results_buffer),
        "platform": platform.system()
    }

# ===== Health =====
@app.get("/health")
def health():
    return {
        "status": "ok",
        "stored_rows": len(results_buffer),
        "platform": platform.system(),
        "timestamp": datetime.datetime.utcnow().isoformat()
    }

# ===== Scan =====
@app.post("/scan")
async def scan_image(file: UploadFile = File(...)):
    contents = await file.read()
    np_img = np.frombuffer(contents, np.uint8)
    img = cv2.imdecode(np_img, cv2.IMREAD_COLOR)

    if img is None:
        raise HTTPException(status_code=400, detail="Invalid image")

    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    text = pytesseract.image_to_string(gray, config="--psm 6")

    match = re.search(r"\b(\d{8,9})\b", text)
    code = match.group(1) if match else "NOT FOUND"

    results_buffer.append({
        "SR": code,
        "timestamp": datetime.datetime.utcnow().isoformat()
    })

    return {
        "sr": code,
        "stored_rows": len(results_buffer)
    }

# ===== Download Excel =====
@app.get("/download-results")
def download_results():
    if not results_buffer:
        return JSONResponse(
            status_code=404,
            content={"error": "No scans yet"}
        )

    df = pd.DataFrame(results_buffer)
    stream = io.BytesIO()
    df.to_excel(stream, index=False)
    stream.seek(0)

    return StreamingResponse(
        stream,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={
            "Content-Disposition": "attachment; filename=results.xlsx"
        }
    )
