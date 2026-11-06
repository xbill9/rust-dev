# Agent Framework coordinator for Azure Container Apps (linux/amd64). Build
# context: rig root. Container Apps runs amd64, so pip installs in the image.
FROM python:3.14-slim-trixie
COPY coordinator/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir --disable-pip-version-check -r /app/requirements.txt
COPY coordinator/main.py /app/main.py
ENV PYTHONUNBUFFERED=1 PORT=8080
WORKDIR /app
EXPOSE 8080
CMD ["python", "main.py"]
