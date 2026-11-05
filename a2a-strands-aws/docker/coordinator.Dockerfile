# Strands coordinator for AgentCore Runtime (linux/$ARCH). Build context: rig
# root, after scripts/build-coordinator.sh has filled build/coordinator/ with
# aarch64 wheels and a cross-compiled a2a CLI. No RUN steps, so the image
# builds on an amd64 machine without an arm64 emulator.
FROM python:3.13-slim-trixie
COPY build/coordinator/site /opt/site
COPY build/coordinator/a2a /usr/local/bin/a2a
COPY coordinator/main.py /app/main.py
ENV PYTHONPATH=/opt/site PYTHONUNBUFFERED=1 DOCKER_CONTAINER=1 A2A_PORT=9000
WORKDIR /app
EXPOSE 9000
CMD ["python", "main.py"]
