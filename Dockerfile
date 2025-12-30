FROM python:3.12-slim

WORKDIR /app

# Install system dependencies
# Install system dependencies
# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    build-essential \
    libpq-dev \
    ffmpeg \
    wget \
    libasound2 \
    libssl-dev \
    && wget http://security.debian.org/debian-security/pool/updates/main/o/openssl/libssl1.1_1.1.1n-0+deb11u5_amd64.deb \
    || wget https://packages.microsoft.com/debian/11/prod/pool/main/o/openssl/libssl1.1_1.1.1n-0+deb11u5_amd64.deb \
    && dpkg -i libssl1.1_1.1.1n-0+deb11u5_amd64.deb \
    && rm libssl1.1_1.1.1n-0+deb11u5_amd64.deb \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY . .

# Expose port
EXPOSE 8000

# Run with uvicorn
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]
