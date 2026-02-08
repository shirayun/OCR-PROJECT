# בסיס פייתון
FROM python:3.13-slim

# התקנת tesseract וכלים
RUN apt-get update && \
    apt-get install -y tesseract-ocr libtesseract-dev && \
    rm -rf /var/lib/apt/lists/*

# התקנת node.js
RUN apt-get install -y curl && \
    curl -fsSL https://deb.nodesource.com/setup_22.x | bash - && \
    apt-get install -y nodejs

# העתקת קוד הבקאנד
WORKDIR /app
COPY Beckend/ /app

# התקנת חבילות פייתון
RUN pip install --no-cache-dir -r requirements.txt

# בניית פרונטאנד
COPY Fronted/sr-client /app/sr-client
WORKDIR /app/sr-client
RUN npm install && npm run build

# העתקת הפרונט לסטטיק
RUN cp -r dist/sr-client/browser/* ../static/

# הרצת השרת
WORKDIR /app
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "10000"]
