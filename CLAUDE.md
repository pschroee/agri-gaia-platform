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

- Services `agent_gateway` (orchestrator, `https://app.<PROJECT_BASE_URL>/agent/`), `agent_postgres`, `agent_s3`,
  `agent_npm_cache`, `agent_pip_cache`, `agent_searxng` and the build-only `agent_pi_image`/`agent_exec_image`,
  all under the compose profile **`agents`**. The orchestrator mounts the Docker socket and starts the agent
  sandboxes itself; they are not part of the compose project.
- Its networks are fixed in `10.231.0.0/16` (`agent_intern` .18, `agent_pkg` .21, `agent_search` .22; the
  orchestrator creates egress .20 and slot networks in `10.231.128.0/17`). Never move them into Docker's
  default 172.x range: a stray network there once covered the address of the platform API inside the VM.
- **Served under `https://app.<PROJECT_BASE_URL>/agent/`, not on a subdomain of its own.** The router matches
  `Host(app.…) && PathPrefix(/agent)` and strips the prefix. Reason (2026-10-05): HARICA, the ACME CA of the
  instance, did not issue a certificate for the new name `agent.…` within Traefik 2.11's fixed wait of about
  30 s (`certificate: time limit exceeded`, no retry afterwards). Under the app host the existing certificate
  applies, and panel and frontend share one origin.
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
- Bindings of new chats: `AGW_TOOLSETS` (default `cli`; any combination of `cli`, `mcp`, `api`, e.g. `cli,api`) and
  `AGW_POOL_SIZE` (default 4 warm slots for that combination) on `agent_gateway`, overridable from the platform `.env`.
  An unknown or empty value stops the gateway at start. Rules in the gateway's `API.md`, *Bindings of new chats*.
- Frontend panel: build flag `VITE_AGENT_ENABLED` from `AGENT_ENABLED` in `.env` (true on `ki-agents`). The
  panel only makes sense when the `agents` profile runs.

## Simulated edge device

For the deployment tests of the thesis (issues E0–E3 of the thesis repository) the stack carries a
simulated edge device, `sim-edge-01`, in the compose profile **`edge-sim`**. It is two services:

- `edge_sim_docker` — a Docker daemon of the device itself, image `docker:27.5.1-dind-rootless`.
  Because the daemon is rootless, a deployment on the device never becomes a sibling container of
  the host, and whoever controls the Portainer edge agent is not root on the host. The outer
  container is still `privileged` (rootless Docker-in-Docker requires it); its limits are 2 CPUs,
  6 GB memory and 2048 processes. Data and socket live in the volumes `edge-sim-docker` and
  `edge-sim-run`, so they survive a redeploy.
- `edge_sim_agent` — the Portainer edge agent `portainer/agent:2.19.5`, matching the Portainer
  version of this stack. It talks to the daemon over the shared Unix socket, with certificate
  verification on (`EDGE_INSECURE_POLL=0`).

Both carry the label `agri-gaia.simulated=true`, publish **no** ports (a deployment opens its ports
inside the device, not on the host) and live only in the **internal** network `edge_sim`
(`10.231.30.0/24`, `internal: true`). Traefik joins that network with the aliases `portainer.`,
`edge.` and `registry.`, so the device reaches Portainer, the edge tunnel and the registry — but
neither the internet nor any other platform service directly. The subnet is also listed in
`AGW_BLOCKED_SUBNETS` of the gateway.

Registration is not part of this repository: the device needs `EDGE_ID` and `EDGE_KEY` in
`secrets/edge-sim.env` (template `secrets/edge-sim.env.example`). The script
`poc/dev/edge-sim-register.sh` of the thesis repository creates the device through the platform API
and writes that file on the host.

Check it with:

```bash
docker exec agri_gaia-edge_sim_docker-1 docker ps      # containers deployed on the device
docker logs agri_gaia-edge_sim_agent-1                 # heartbeat of the edge agent
```

Enable the profile by adding `edge-sim` to `AG_COMPOSE_PROFILES` in the deployment `.env`.

## Agent notebooks

A chat runs its own Python code as a **named JupyterHub server whose name starts with `agw-`**; the gateway
starts and stops it over the hub API. Such a server is deliberately much narrower than a user's notebook:

- **Hardening** lives in `services/jupyterhub/config/platform_spawner.py` (`_harden_for_agent`, triggered by the
  `agw-` prefix in the constructor). An agent server is **not privileged**, drops all capabilities, runs with
  `no-new-privileges`, and is limited to 2 CPUs, 8 GB memory, 1024 processes and 1 GB `/dev/shm`
  (`AGW_NOTEBOOK_CPUS`, `AGW_NOTEBOOK_MEM` on the hub override the first two). Servers of human users —
  including all unnamed ones — are untouched: they stay privileged and keep `SYS_ADMIN` and `/dev/fuse`.
- **No way out.** An agent notebook is attached to the **internal network `agent_notebooks`**
  (`10.231.23.0/24`, `internal: true`) and to nothing else. It can reach the hub (API and its own proxy path),
  because the hub is a member of that network too, but it has neither internet nor a route into the platform
  network or the object store. In addition `10.231.23.0/24` is listed in `AGW_BLOCKED_SUBNETS` of the gateway.
  Notebook files live in the volume `<project>-jupyterhub-agent-<username>--<servername>` at `/home/jovyan/work`,
  so chats do not see each other's files.
- **No Keycloak tokens.** The server token of an agent notebook carries only
  `users:activity!user` and `access:servers!server` (`server_token_scopes` in the spawner). It cannot read the
  user's `auth_state`, so running code inside an agent notebook cannot impersonate the user. This is what the
  default `server` role would have handed out, see `config.py`, `load_roles`.
- **Service token.** The gateway acts on the hub as the service `agent-gateway`, defined in
  `services/jupyterhub/config/config.py` with the scopes `servers` and `read:users:name`. Its token comes from
  `AGW_JUPYTERHUB_TOKEN`, which both the hub and the gateway read from the same secret file
  `secrets/jupyterhub-agent.env` (example next to it; in production `/opt/agri-gaia/secrets/`). **Without that
  file the hub starts exactly as before**, no service and no role are added.
- **Image.** `agri-gaia/agent-notebook:hub-<JUPYTERHUB_VERSION>`, built from
  `services/jupyterhub/images/Dockerfile.agent` by `build-cpu-images.sh` (after the data science notebook it is
  based on). It adds torch and torchvision (CPU wheels, same versions as the EfficientNet template) plus onnx,
  onnxruntime and skl2onnx. The spawner allows exactly this one image for `agw-*` servers, so the image cannot
  be chosen from the spawn form.
- **Labels** on an agent notebook container: `agw.notebook=1`, `agw.user=<username>`, `agw.server=<servername>`.
- Checking a running server: `docker inspect agri_gaia-jupyter-<user>--<servername>` must show
  `Privileged=false`, `CapDrop=[ALL]`, `SecurityOpt=[no-new-privileges:true]`, `Memory=8589934592`,
  `NanoCpus=2000000000`, `PidsLimit=1024` and `NetworkMode=agri_gaia_agent_notebooks`.

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
