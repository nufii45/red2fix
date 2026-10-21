FROM python:3.11-slim

RUN apt-get update && apt-get install -y --no-install-recommends git \
    && rm -rf /var/lib/apt/lists/*
RUN pip install --no-cache-dir openai==3.35.1 pytest==9.1.1

# No .pyc files, so they never show up in the agent's diffs.
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1

RUN useradd -m agent && mkdir -p /work /out && chown agent /work /out
WORKDIR /app
COPY config.py ./
COPY agent ./agent
USER agent
ENTRYPOINT ["python", "-m", "agent.main"]
