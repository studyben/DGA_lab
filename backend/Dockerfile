FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY requirements.txt ./
RUN pip install --no-cache-dir --require-hashes -r requirements.txt && useradd --uid 10001 --create-home app
COPY . .
USER app
CMD ["uvicorn", "dga.main:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000"]
