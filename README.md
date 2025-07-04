# lldap-request

<img src="images/logo.png" width="150" align="right" alt="lldap-request logo"/>

A simple web tool to request new [lldap](https://github.com/lldap/lldap) accounts with an _optional_ admin page to approve or deny these requests.

When approved, it creates the account in lldap, adds it to a group if one is defined, and triggers a reset password link to email the user to reset (aka. setup) their password.

## Docker Environment Variables

| Name | Required | Default | Description |
| --- | :---: | --- | --- |
| RESET_TYPE | | lldap | What to send the reset password email from. Email must be set up and reset password enabled in the selected application. Options: `lldap`, `authelia` |
| LLDAP_URL | X | | e.g. <https://lldap.domain.com><br />Required if RESET_TYPE is lldap |
| AUTHELIA_URL | X |  | e.g. <https://auth.domain.com><br />Required if RESET_TYPE is authelia |
| LLDAP_USERNAME | X |  | lldap user with account-creation rights |
| LLDAP_PASSWORD | X |  | Password for the above user |
| LLDAP_HTTPURL |  | <http://lldap:17170> | Internal, base address of lldap |
| LLDAP_USER_GROUP |  |  | Group to add new users to (if set) |
| REQUIRE_APPROVAL | | true | If `false`, accounts will automatically be created as soon as they are requested |
| APPRISE_URL | | <http://apprise:8000> | The URL where Apprise is installed |
| APPRISE_NOTIFY_ADMIN_URL | | | The apprise notification URL to send the message to (see [Apprise docs](https://github.com/caronc/apprise/wiki#notification-services)) |
| DEBUG |  | false | Show debug logging if `true` |

### Example docker-compose.yml

* Request account: http://IP:5005
* Admin: http://IP:5005/admin

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
    environment:
      LLDAP_URL: https://lldap.domain.com
      LLDAP_USERNAME: admin
      LLDAP_PASSWORD: changeme
```

This does not handle any kind of security or authentication itself. Instead, it relies on something external to control access. In the example below, it uses Authelia and Traefik. Traefik restricts the new user request to only load from internal IPs. The admin page requires Authelia approval and that address (lldap-request.domain.com) is restricted to the admin group.

### Example docker-compose-traefik.yml

* Request account: https://lldap-request.domain.com
* Admin: https://lldap-request.domain.com/admin

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
    environment:
      RESET_TYPE: authelia
      AUTHELIA_URL: https://auth.domain.com
      LLDAP_USERNAME: admin
      LLDAP_PASSWORD: changeme
      LLDAP_USER_GROUP: authelia_users
      DEBUG: 'true'
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
<img src="images/request_account.png" width="300"/>

<img src="images/admin.png">

#### There are many ways this can be improved/expanded

* Support optional basic authentication for the admin page
* Put new user sign up behind a password or something similar
* Better handling of errors/validations
* Any number of UI improvements
* ~~Sent a notice to an Admin when there is a new user to approve~~
* ~~Option to not require approval but auto-approve all requests~~
* ~~Connect to lldap directly using [GraphQL API calls](https://github.com/lldap/lldap/blob/main/schema.graphql) (not relying on lldap-cli)~~
* ~~Use environment variable for what group(s) to add the new user to~~
* ~~Don't rely on Authelia for the password reset email and/or support other tools (ex. Authentik, Keycloak, etc.)~~

