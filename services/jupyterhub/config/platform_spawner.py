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
GPU_DEVICE_IDS = os.environ.get("GPUS") or ""
# GPUs of the hardened agent servers (agw-*); follows GPUS unless AGW_NOTEBOOK_GPUS says otherwise,
# "none" switches the GPU off for agent servers only.
AGENT_GPU_IDS = os.environ.get("AGW_NOTEBOOK_GPUS", GPU_DEVICE_IDS) or ""
if AGENT_GPU_IDS == "none":
    AGENT_GPU_IDS = ""
NGC_IMAGE_TAG = os.environ.get("NGC_IMAGE_TAG")
JUPYTERHUB_VERSION = os.environ.get("JUPYTERHUB_VERSION")
NETWORK_NAME = os.environ["DOCKER_NETWORK_NAME"]
PROJECT_NAME = os.environ["PROJECT_NAME"]

# Named servers starting with this prefix are started by the agent gateway for its chats and are
# hardened below. Servers of human users (including all unnamed ones) stay untouched.
AGENT_PREFIX = "agw-"
AGENT_NETWORK = os.environ.get("AGW_NOTEBOOK_NETWORK", f"{PROJECT_NAME}_agent_notebooks")
AGENT_IMAGE = f"agri-gaia/agent-notebook:hub-{JUPYTERHUB_VERSION}"


def gpu_device_requests(ids):
    """DeviceRequests for the GPUs in ids ("0", "0,1", "all"); None for "" or "none"."""
    if not ids or ids == "none":
        return None
    return [docker.types.DeviceRequest(
        count=-1 if ids == "all" else None,
        device_ids=None if ids == "all" else [ids],
        capabilities=[["gpu"]],
    )]


def _image_present(name):
    """True if the image exists locally (the NGC images are optional and big)."""
    try:
        docker.from_env(timeout=5).images.get(name)
        return True
    except Exception:
        return False


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

        requests = gpu_device_requests(GPU_DEVICE_IDS)
        if requests is not None:
            self.extra_host_config["device_requests"] = requests
            # Offer the NGC images only if they were built (AG_JUPYTERHUB_NGC_IMAGES=false skips them)
            for key, repo in (("pytorch", "jupyterhub-notebook-pytorch"), ("tf2", "jupyterhub-notebook-tf2")):
                name = f"agri-gaia/{repo}:{NGC_IMAGE_TAG}"
                if _image_present(name):
                    self.allowed_images[key] = name

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
        # The GPU is shared with platform trainings; only CUDA and nvidia-smi, no graphics or video.
        requests = gpu_device_requests(AGENT_GPU_IDS)
        if requests is not None:
            self.extra_host_config["device_requests"] = requests
            self.environment = {
                **(self.environment or {}),
                "NVIDIA_DRIVER_CAPABILITIES": "compute,utility",
            }
