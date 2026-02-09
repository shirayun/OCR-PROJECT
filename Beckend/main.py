from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.responses import FileResponse, StreamingResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from uuid import uuid4
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
app.mount("/app", StaticFiles(directory="static", html=True), name="static")

# ===== CORS =====
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

results_by_session: dict[str, list[dict]] = {}

@app.get("/session")
def create_session():
    session_id = str(uuid4())
    results_by_session[session_id] = []
    return {"session_id": session_id}

@app.post("/scan")
async def scan_image(
    session_id: str,
    file: UploadFile = File(...)
):
    if session_id not in results_by_session:
        raise HTTPException(status_code=400, detail="Invalid session")

    contents = await file.read()
    np_img = np.frombuffer(contents, np.uint8)
    img = cv2.imdecode(np_img, cv2.IMREAD_COLOR)

    if img is None:
        raise HTTPException(status_code=400, detail="Invalid image")

    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    text = pytesseract.image_to_string(gray, config="--psm 6")

    match = re.search(r"\b(\d{8,9})\b", text)
    code = match.group(1) if match else "NOT FOUND"

    results_by_session[session_id].append({
        "SR": code,
        "timestamp": datetime.datetime.utcnow().isoformat()
    })

    return {
        "sr": code,
        "rows": len(results_by_session[session_id])
    }

@app.get("/download-results")
def download_results(session_id: str):
    if session_id not in results_by_session:
        raise HTTPException(status_code=400, detail="Invalid session")

    data = results_by_session[session_id]

    if not data:
        raise HTTPException(status_code=404, detail="No scans yet")

    df = pd.DataFrame(data)

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
