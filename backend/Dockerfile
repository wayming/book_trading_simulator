FROM python:3.12-slim
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends gcc && rm -rf /var/lib/apt/lists/*
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY *.py .
COPY grpc_stubs/ ./grpc_stubs/
RUN mkdir -p /app/data /app/logs
EXPOSE 8000 50051
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
