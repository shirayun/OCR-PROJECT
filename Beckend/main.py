from fastapi import FastAPI, UploadFile, File, HTTPException, Request
from fastapi.responses import FileResponse, StreamingResponse, JSONResponse, RedirectResponse
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

# ===== CORS =====
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

results_by_session: dict[str, list[dict]] = {}

@app.get("/api/session")
def create_session():
    session_id = str(uuid4())
    results_by_session[session_id] = []
    return {"session_id": session_id}

@app.post("/api/scan")
async def scan_image(session_id: str, file: UploadFile = File(...)):

    # Auto-create session if invalid
    if session_id not in results_by_session:
        results_by_session[session_id] = []

    try:
        contents = await file.read()
        np_img = np.frombuffer(contents, np.uint8)
        img = cv2.imdecode(np_img, cv2.IMREAD_COLOR)

        if img is None:
            raise HTTPException(status_code=400, detail="Invalid image")

        # Try multiple preprocessing methods
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        
        # Method 1: OTSU threshold
        _, thresh1 = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        
        # Method 2: Adaptive threshold
        thresh2 = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 11, 2)
        
        # Method 3: Simple threshold
        _, thresh3 = cv2.threshold(gray, 127, 255, cv2.THRESH_BINARY)

        all_codes = []
        
        # Try OCR on all methods
        for idx, img_processed in enumerate([gray, thresh1, thresh2, thresh3]):
            text = pytesseract.image_to_string(
                img_processed,
                lang="eng",
                config="--oem 3 --psm 6"
            )
            
            print(f"===== OCR Method {idx+1} =====")
            print(text)
            print("====================")
            
            # Find all 8-digit sequences
            matches = re.findall(r"\d{8}", text)
            all_codes.extend(matches)
        
        # Get first valid code or NOT FOUND
        code = all_codes[0] if all_codes else "NOT FOUND"
        
        print(f"===== FINAL CODE: {code} =====")

        results_by_session[session_id].append({
            "SR": code,
            "timestamp": datetime.datetime.utcnow().isoformat()
        })

        return {
            "sr": code,
            "rows": len(results_by_session[session_id])
        }

    except Exception as e:
        print("===== ERROR in scan_image =====")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail="Internal server error")


@app.get("/api/download-results")
def download_results(session_id: str):
    # Auto-create session if invalid
    if session_id not in results_by_session:
        results_by_session[session_id] = []

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

# ===== Serve Angular frontend - MUST BE LAST! =====
app.mount("/", StaticFiles(directory="static", html=True), name="static")

@app.exception_handler(404)
async def custom_404_handler(request: Request, __exc):
    # For Angular routes - return index.html
    if not request.url.path.startswith("/api/"):
        return FileResponse("static/index.html")
    raise __exc

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)