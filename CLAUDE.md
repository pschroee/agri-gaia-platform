<!--
SPDX-FileCopyrightText: 2026 Philipp Schröer
SPDX-FileContributor: Philipp Schröer

SPDX-License-Identifier: MIT
-->

# Agri-Gaia Platform — fork `pschroee/agri-gaia-platform`

This is a fork of [hsos-ai-lab/agri-gaia-platform](https://github.com/hsos-ai-lab/agri-gaia-platform),
maintained for the master's thesis *Extending a federated AI development environment with AI agents*
(Philipp Schröer, Osnabrück University of Applied Sciences). It adds an **agent gateway** as a platform service
and a chat panel in the frontend. Everything else follows the upstream platform.

## Repositories and branches

The platform consists of three repositories, all forked under `pschroee`, plus one new repository:

| Repository | Path in this repo | Upstream | Changed in the fork |
|---|---|---|---|
| `pschroee/agri-gaia-platform` | — | `hsos-ai-lab/agri-gaia-platform` | compose service, Traefik route, Keycloak realm |
| `pschroee/agri-gaia-frontend` | `services/frontend` | `hsos-ai-lab/agri-gaia-frontend` | agent chat panel |
| `pschroee/agri-gaia-backend` | `services/backend` | `hsos-ai-lab/agri-gaia-backend` | nothing so far |
| `pschroee/agri-gaia-agent-gateway` | `services/agent-gateway` | — (new) | the gateway itself |

The backend fork exists although it is unchanged: the deployment scripts
([agri-gaia-platform-deployment](https://github.com/hsos-ai-lab/agri-gaia-platform-deployment)) take one GitHub
organisation (`AG_GIT_ORGANIZATION`) for platform, backend and frontend. Forks of public repositories are always
public on GitHub.

Branch model, identical in all three forks:

- **`main`** mirrors upstream `main` and is never committed to directly. Update it with
  `git fetch upstream && git checkout main && git merge --ff-only upstream/main && git push`.
- **`ki-agents`** is the integration branch and the default branch of each fork. It was branched from `main`
  on 2026-10-05. The deployed instance runs this branch.
- **Feature branches** (`feat/…`, `fix/…`) are branched from `ki-agents` and come back through a pull request
  **within the fork**: `gh pr create --repo pschroee/agri-gaia-<repo> --base ki-agents`.
- Upstream changes reach `ki-agents` through `git merge main` after `main` has been updated.

Remotes in every clone: `origin` = `pschroee/…`, `upstream` = `hsos-ai-lab/…`.

Clone with submodules from the fork:

```bash
git clone git@github.com:pschroee/agri-gaia-platform.git
cd agri-gaia-platform
git config submodule.services/backend.url git@github.com:pschroee/agri-gaia-backend.git
git config submodule.services/frontend.url git@github.com:pschroee/agri-gaia-frontend.git
git submodule update --init
git -C services/frontend checkout ki-agents
git -C services/backend checkout ki-agents
```

`.gitmodules` keeps the upstream URLs for backend and frontend; the deployment rewrites them anyway. When a
submodule moves on `ki-agents`, commit the new submodule pointer in this repository as well.

## Conventions (as upstream)

- **Commit messages in English**, short, one line, describing the change (`added agent gateway service`,
  `fixed …`, `bumped …`). Body only when the reason is not obvious.
- **Upstream code and own changes stay apart:** never rewrite upstream history; every own change is a separate
  commit on top. Do not reformat upstream files (the frontend had one repository-wide `prettier --write`;
  do not repeat it).
- **REUSE/SPDX:** every file carries an SPDX header. Files written in this fork use
  `SPDX-FileCopyrightText: 2026 Philipp Schröer`; when changing an upstream file, keep its header and add
  `SPDX-FileContributor: Philipp Schröer`. License is MIT, as upstream.
- **No secrets and no instance data in the repository** — no passwords, tokens, API keys, host names of private
  instances or test credentials. Secrets of the agent gateway live in `secrets/agent-gateway.env`, which is not
  committed (see below).
- Do not commit files changed by the deployment itself (`.env` with a real `PROJECT_BASE_URL`,
  `realm-export.json` after `customize-keycloak-realm.sh`, the patched frontend files), see the warning in
  `README.md`.

## Development

See `README.md`: `start.sh`, `start-no-monitoring.sh`, `stop.sh`, `run_tests.sh`; configuration in `.env`.
The agent gateway has its own development setup (`services/agent-gateway/dev.sh`) and its own `CLAUDE.md`.

## Agent gateway service

- Services `agent_gateway` (orchestrator, `https://agent.<PROJECT_BASE_URL>`), `agent_postgres`, `agent_s3`,
  `agent_npm_cache`, `agent_pip_cache`, `agent_searxng` and the build-only `agent_pi_image`/`agent_exec_image`,
  all under the compose profile **`agents`**. The orchestrator mounts the Docker socket and starts the agent
  sandboxes itself; they are not part of the compose project.
- Its networks are fixed in `10.231.0.0/16` (`agent_intern` .18, `agent_pkg` .21, `agent_search` .22; the
  orchestrator creates egress .20 and slot networks in `10.231.128.0/17`). Never move them into Docker's
  default 172.x range: a stray network there once covered the address of the platform API inside the VM.
- The orchestrator reaches Keycloak and the API through the public names, which resolve to Traefik inside the
  compose network (`reverse_proxy` aliases).
- Secrets: `secrets/agent-gateway.env` (orchestrator) and `secrets/agent-gateway-services.env` (database,
  object store, search), templates as `*.env.example` next to them. The deployment copies
  `/opt/agri-gaia/secrets/` into `platform/secrets/`, so the files live there on the host.
- Login: the gateway logs the platform user in itself (authorization code flow with PKCE at the Keycloak client
  `agw-agent`, `prompt=none` reuses the platform's Keycloak session inside the iframe) and exchanges that user's
  token per chat (RFC 8693). The client `frontend` is unchanged.
- Keycloak: `agw-agent` is in `realm-export.json`, which Keycloak imports only when the realm does not exist yet
  (`--override false`). A running instance needs the client created or updated through the admin API; the
  script for that lives in the gateway repository (`dev/keycloak-agw-agent.sh`). Keycloak generates the client
  secret; copy it into `secrets/agent-gateway.env`.
- Frontend panel: build flag `VITE_AGENT_ENABLED` from `AGENT_ENABLED` in `.env` (true on `ki-agents`). The
  panel only makes sense when the `agents` profile runs.

## Deployment and how to switch back

Production deployment runs through `deploy.sh` of the deployment repository. It deletes and re-clones
`/opt/agri-gaia/platform`, checks out the configured branches and keeps Docker volumes unless
`AG_COMPOSE_DOWN_FLAGS` contains `-v`.

Switching an instance to this fork (in `deploy/scripts/.env`, after a backup copy of that file):

```bash
AG_GIT_ORGANIZATION=pschroee
AG_GIT_BRANCH_PLATFORM=ki-agents
AG_GIT_BRANCH_BACKEND=ki-agents
AG_GIT_BRANCH_FRONTEND=ki-agents
AG_COMPOSE_PROFILES=<existing profiles>,agents
```

and put `agent-gateway.env` and `agent-gateway-services.env` into `/opt/agri-gaia/secrets/`.

then `sudo ./deploy.sh`. To switch back, restore the backup copy (`hsos-ai-lab`, `main`) and run
`sudo ./deploy.sh` again.
