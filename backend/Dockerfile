FROM python:3.11-slim
WORKDIR /app
COPY backend/requirements.txt backend/requirements-ocr.txt /app/backend/
ARG INSTALL_OCR=false
RUN if [ "$INSTALL_OCR" = "true" ]; then apt-get update && apt-get install -y --no-install-recommends libgomp1 libglib2.0-0 libgl1 && rm -rf /var/lib/apt/lists/*; fi
RUN pip install --no-cache-dir -r backend/requirements.txt && if [ "$INSTALL_OCR" = "true" ]; then pip install --no-cache-dir -r backend/requirements-ocr.txt; fi
COPY backend /app/backend
ENV STORAGE_DIR=/app/storage
RUN mkdir -p /app/storage
EXPOSE 8000
CMD ["uvicorn", "backend.app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
