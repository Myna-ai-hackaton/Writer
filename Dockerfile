FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source code
COPY . .

# Set the entrypoint to our action script
ENTRYPOINT ["python", "/app/scripts/agent_action.py"]
