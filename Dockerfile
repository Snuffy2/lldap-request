FROM python:3.13-slim

ARG TARGETARCH
RUN echo "Target architecture is: $TARGETARCH"

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    jq \
    xz-utils \
    tar \
    sqlite3 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install lldap-cli
RUN curl -sL https://raw.githubusercontent.com/Zepmann/lldap-cli/refs/heads/main/lldap-cli -o /usr/local/bin/lldap-cli && \
    chmod +x /usr/local/bin/lldap-cli

# Download and extract lldap_set_password from the latest GitHub release for this arch
RUN ARCHIVE=unknown && \
    case "$TARGETARCH" in \
        amd64) ARCHIVE=amd64-lldap.tar.gz ;; \
        arm64) ARCHIVE=aarch64-lldap.tar.gz ;; \
        arm) ARCHIVE=armhf-lldap.tar.gz ;; \
        *) echo "Unsupported arch: $TARGETARCH" && exit 1 ;; \
    esac && \
    curl -sL "https://github.com/lldap/lldap/releases/latest/download/${ARCHIVE}" -o /tmp/lldap.tar.gz && \
    tar -xzf /tmp/lldap.tar.gz -C /tmp && \
    find /tmp -name lldap_set_password -exec install {} /usr/local/bin/lldap_set_password \; && \
    rm -rf /tmp/*


WORKDIR /app
COPY . .

EXPOSE 5000
CMD ["gunicorn", "-b", "0.0.0.0:5000", "app:app"]
