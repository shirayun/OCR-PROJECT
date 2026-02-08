from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.responses import StreamingResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import cv2
import pytesseract
import re
import numpy as np
import pandas as pd
import io
import datetime
import traceback
import platform

app = FastAPI(title="OCR SR API", version="1.0.0")

# ====== STORAGE IN MEMORY ======
results_buffer = []  # כאן נשמרות כל הסריקות

# ====== TESSERACT ======
try:
    if platform.system() == "Windows":
        pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
except Exception as e:
    print(f"Note: Could not set Tesseract path: {e}")

# ====== CORS ======
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ====== HEALTH ======
@app.get("/health")
async def health_check():
    return {
        "status": "ok",
        "stored_rows": len(results_buffer),
        "platform": platform.system(),
        "timestamp": datetime.datetime.utcnow().isoformat()
    }

# ====== SCAN IMAGE ======
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
        code = match.group(1) if match else "NOT FOUND"

        results_buffer.append({
            "SR": code,
            "timestamp": datetime.datetime.utcnow().isoformat()
        })

        return {
            "sr": code,
            "total_scans": len(results_buffer)
        }

    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

# ====== DOWNLOAD EXCEL ======
@app.get("/download-results")
def download_results():
    if not results_buffer:
        return JSONResponse(
            status_code=404,
            content={"error": "אין נתונים להורדה"}
        )

    df = pd.DataFrame(results_buffer)

    output = io.BytesIO()
    df.to_excel(output, index=False)
    output.seek(0)

    return StreamingResponse(
        output,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={
            "Content-Disposition": "attachment; filename=results.xlsx"
        }
    )

# ====== COUNT ======
@app.get("/api/results-count")
def results_count():
    return {"count": len(results_buffer)}

# ====== STATIC (ANGULAR) ======
app.mount("/", StaticFiles(directory="static", html=True), name="static")
