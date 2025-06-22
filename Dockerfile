FROM python:3.13-slim

RUN apt-get update && apt-get install -y \
    wget \
    curl \
    jq \
    sqlite3 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install lldap-cli
RUN wget https://raw.githubusercontent.com/Zepmann/lldap-cli/refs/heads/main/lldap-cli -O /usr/local/bin/lldap-cli && \
    chmod +x /usr/local/bin/lldap-cli

WORKDIR /app
COPY . .

RUN chmod +x /app/lldap_cli_wrapper.py

EXPOSE 5000
CMD ["gunicorn", "-b", "0.0.0.0:5000", "app:app"]
