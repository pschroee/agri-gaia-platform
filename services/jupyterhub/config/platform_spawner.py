# SPDX-FileCopyrightText: 2024 Osnabrück University of Applied Sciences
# SPDX-FileContributor: Andreas Schliebitz
# SPDX-FileContributor: Henri Graf
# SPDX-FileContributor: Jonas Tüpker
# SPDX-FileContributor: Lukas Hesse
# SPDX-FileContributor: Maik Fruhner
# SPDX-FileContributor: Prof. Dr.-Ing. Heiko Tapken
# SPDX-FileContributor: Tobias Wamhof
# SPDX-FileContributor: Philipp Schröer
#
# SPDX-License-Identifier: MIT

import os
from dockerspawner import DockerSpawner
import docker

BASE_DIR = "/srv/jupyterhub/config"
GPU_DEVICE_IDS = os.environ.get("GPUS")
NGC_IMAGE_TAG = os.environ.get("NGC_IMAGE_TAG")
JUPYTERHUB_VERSION = os.environ.get("JUPYTERHUB_VERSION")
NETWORK_NAME = os.environ["DOCKER_NETWORK_NAME"]
PROJECT_NAME = os.environ["PROJECT_NAME"]

# Named servers starting with this prefix are started by the agent gateway for its chats and are
# hardened below. Servers of human users (including all unnamed ones) stay untouched.
AGENT_PREFIX = "agw-"
AGENT_NETWORK = os.environ.get("AGW_NOTEBOOK_NETWORK", f"{PROJECT_NAME}_agent_notebooks")
AGENT_IMAGE = f"agri-gaia/agent-notebook:hub-{JUPYTERHUB_VERSION}"


# First, define a custom spawner class to make the worker node selectable
class PlatformSpawner(DockerSpawner):
    def __init__(self, **kwargs) -> None:
        self.prefix = f"{PROJECT_NAME}-jupyter"
        super(PlatformSpawner, self).__init__(**kwargs)

        # Connect containers to this Docker network
        self.use_internal_ip = True
        self.network_name = NETWORK_NAME
        # self.name_template = "{prefix}-{username}-{servername}"

        # Spawn containers from one of these images
        self.allowed_images = {
            "data-science": f"agri-gaia/datascience-notebook:hub-{JUPYTERHUB_VERSION}",
            "base": f"agri-gaia/minimal-notebook:hub-{JUPYTERHUB_VERSION}",
        }

        # Set the spawned container config
        self.extra_host_config = {
            "network_mode": NETWORK_NAME,
            "shm_size": "8G",
            "cap_add": ["SYS_ADMIN"],
            "devices": ["/dev/fuse:/dev/fuse"],
            "privileged": True,
        }

        if GPU_DEVICE_IDS != "":
            self.extra_host_config["device_requests"] = [
                docker.types.DeviceRequest(
                    count=-1 if GPU_DEVICE_IDS == "all" else None,
                    device_ids=[GPU_DEVICE_IDS] if GPU_DEVICE_IDS != "all" else None,
                    capabilities=[["gpu"]],
                ),
            ]
            self.allowed_images["pytorch"] = (
                f"agri-gaia/jupyterhub-notebook-pytorch:{NGC_IMAGE_TAG}"
            )
            self.allowed_images["tf2"] = (
                f"agri-gaia/jupyterhub-notebook-tf2:{NGC_IMAGE_TAG}"
            )

        notebook_container_dir = "/home/jovyan/work"
        notebook_volume_name = PROJECT_NAME + "-jupyterhub-user-{username}"
        self.notebook_dir = "/home/jovyan"
        self.cmd = ["jupyterhub-singleuser", "--ip=0.0.0.0"]

        # Mount the real user's Docker volume on the host to the notebook user's
        # notebook directory in the container
        self.volumes = {
            notebook_volume_name: {"bind": notebook_container_dir, "mode": "rw"}
        }

        self.default_url = "/lab"

        # Remove containers once they are stopped
        self.remove = True

        # For debugging arguments passed to spawned containers
        self.debug = False

        # Last, so that the hardening overrides everything set above: server names are known in
        # the constructor (the hub passes them), all other servers keep the settings unchanged.
        if (self.name or "").startswith(AGENT_PREFIX):
            self._harden_for_agent()

    def _harden_for_agent(self) -> None:
        # Named servers agw-* are started by the agent gateway and run code written by the agent.
        # No privileges, no capabilities, limits, an internal network that reaches only the hub,
        # and a server token without access to the user's Keycloak tokens (auth_state).
        self.allowed_images = {"agent": AGENT_IMAGE}
        self.image = AGENT_IMAGE
        self.network_name = AGENT_NETWORK
        self.use_internal_ip = True
        self.extra_host_config = {
            "network_mode": AGENT_NETWORK,
            "privileged": False,
            "cap_drop": ["ALL"],
            "security_opt": ["no-new-privileges:true"],
            "pids_limit": 1024,
            "shm_size": "1G",
        }
        self.extra_create_kwargs = {
            "labels": {
                "agw.notebook": "1",
                "agw.user": "{raw_username}",
                "agw.server": "{raw_servername}",
            }
        }
        self.mem_limit = os.environ.get("AGW_NOTEBOOK_MEM", "8G")
        self.cpu_limit = float(os.environ.get("AGW_NOTEBOOK_CPUS", "2"))
        self.volumes = {
            PROJECT_NAME + "-jupyterhub-agent-{username}--{servername}": {
                "bind": "/home/jovyan/work",
                "mode": "rw",
            }
        }
        self.server_token_scopes = ["users:activity!user", "access:servers!server"]
        self.remove = True
