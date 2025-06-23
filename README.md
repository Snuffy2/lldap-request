# lldap-request

A working, but mostly proof-of-concept example, of a web page to request new LLDAP accounts with an admin page to approve or deny these requests.

When approved, it triggers an Authelia reset password link to email the user to reset (aka. setup) their password.

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

Example docker-compose-traefik.yml:

```yaml
services:
  lldap-request:
    image: ghcr.io/snuffy2/lldap-request:latest
    #image: ghcr.io/snuffy2/lldap-request:edge
    container_name: lldap-request
    hostname: lldap-request
    restart: unless-stopped
    volumes:
      - ./database:/app/database
      - ./lldap_config:/app/lldap_config  # Your local lldap config path
    environment:
      AUTHELIA_URL: https://auth.domain.com
      LLDAP_CONFIG: /app/lldap_config/config.toml
      LLDAP_HTTPURL: http://lldap:17170
      LLDAP_USERNAME: admin
      LLDAP_PASSWORD: changeme
    labels:
      - traefik.enable=true
      - 'traefik.http.routers.lldap-request-admin.rule=Host(`lldap-request.domain.com`) && Path(`/admin`)'
      - traefik.http.routers.lldap-request-admin.entrypoints=websecure
      - traefik.http.routers.lldap-request-admin.middlewares=chain-authelia@file
      - traefik.http.routers.lldap-request-admin.service=lldap-request
      - 'traefik.http.routers.lldap-request.rule=Host(`lldap-request.domain.com`)'
      - traefik.http.routers.lldap-request.entrypoints=websecure
      - traefik.http.routers.lldap-request.middlewares=middlewares-local-only-whitelist@file
      - traefik.http.routers.lldap-request.service=lldap-request
      - traefik.http.services.lldap-request.loadbalancer.server.port=5000
```
