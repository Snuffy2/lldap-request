# lldap-request

A working, but mostly proof-of-concept example, of a web page to request new LLDAP accounts with an admin page to approve or deny these requests.

When approved, it triggers an Authelia reset password link to send an email to the user to reset (aka. setup) their password.

Example docker-compose.yml:
```yaml
services:
  lldap-request:
    image: ghcr.io/snuffy2/lldap-request:latest
    #image: ghcr.io/snuffy2/lldap-request:edge
    container_name: lldap-request
    hostname: lldap-request
    restart: unless-stopped
    ports:
      - "5005:5000"
    volumes:
      - ./database:/app/database
      - ./lldap_config:/app/lldap_config  # Your local lldap config path
    environment:
      AUTHELIA_URL: https://auth.domain.com
      LLDAP_CONFIG: /app/lldap_config/config.toml
      LLDAP_HTTPURL: http://lldap:17170
      LLDAP_USERNAME: admin
      LLDAP_PASSWORD: changeme
```