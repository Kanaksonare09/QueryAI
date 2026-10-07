FROM python:3.11-slim

WORKDIR /app

# System dependencies for PyMuPDF and other packages
RUN apt-get update && apt-get install -y \
    gcc g++ curl libffi-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN mkdir -p storage/documents storage/temp

EXPOSE 8080

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]
