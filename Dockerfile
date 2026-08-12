# This Dockerfile is for LOCAL practice only — to understand what a container is.
# The actual AWS deployment uses SAM/Lambda (see template.yaml), not this image.

FROM python:3.12-slim

WORKDIR /code

COPY app/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt uvicorn

COPY app/ ./app/

EXPOSE 8000

# Run the app with uvicorn locally. TABLE_NAME points at a local/dummy table.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
