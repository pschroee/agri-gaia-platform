# SPDX-FileCopyrightText: 2026 Philipp Schröer
#
# SPDX-License-Identifier: MIT

import importlib
import sys
import types
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "config"))


class _Base:
    def __init__(self, **kwargs):
        self.name = kwargs.get("name", "")
        self.environment = {}


@pytest.fixture
def load(monkeypatch):
    stub = types.ModuleType("dockerspawner")
    stub.DockerSpawner = _Base
    monkeypatch.setitem(sys.modules, "dockerspawner", stub)
    monkeypatch.setenv("DOCKER_NETWORK_NAME", "net")
    monkeypatch.setenv("PROJECT_NAME", "proj")
    monkeypatch.setenv("JUPYTERHUB_VERSION", "5.4.5")
    monkeypatch.setenv("NGC_IMAGE_TAG", "23.04")
    monkeypatch.delenv("GPUS", raising=False)
    monkeypatch.delenv("AGW_NOTEBOOK_GPUS", raising=False)

    def _load(built=False, **env):
        for k, v in env.items():
            monkeypatch.setenv(k, v)
        sys.modules.pop("platform_spawner", None)
        mod = importlib.import_module("platform_spawner")
        monkeypatch.setattr(mod, "_image_present", lambda name: built)
        return mod

    return _load


def _agent(mod):
    return mod.PlatformSpawner(name="agw-chat1")


def test_agent_gets_gpu_when_gpus_set(load):
    s = _agent(load(GPUS="0"))
    req = s.extra_host_config["device_requests"][0]
    assert req["DeviceIDs"] == ["0"]
    assert req["Capabilities"] == [["gpu"]]


def test_agent_without_gpu_when_gpus_empty(load):
    s = _agent(load(GPUS=""))
    assert "device_requests" not in s.extra_host_config


def test_agent_gpu_off_with_none(load):
    s = _agent(load(GPUS="0", AGW_NOTEBOOK_GPUS="none"))
    assert "device_requests" not in s.extra_host_config


def test_agent_hardening_unchanged_with_gpu(load):
    mod = load(GPUS="0")
    c = _agent(mod).extra_host_config
    assert c["privileged"] is False
    assert c["cap_drop"] == ["ALL"]
    assert c["security_opt"] == ["no-new-privileges:true"]
    assert c["pids_limit"] == 1024
    assert c["shm_size"] == "1G"
    assert c["network_mode"] == mod.AGENT_NETWORK
    assert _agent(mod).image == mod.AGENT_IMAGE


def test_agent_driver_capabilities(load):
    assert _agent(load(GPUS="0")).environment["NVIDIA_DRIVER_CAPABILITIES"] == "compute,utility"
    assert "NVIDIA_DRIVER_CAPABILITIES" not in _agent(load(GPUS="")).environment


def test_ngc_offered_only_when_built(load):
    human = lambda mod: mod.PlatformSpawner(name="").allowed_images
    assert "pytorch" not in human(load(built=False, GPUS="0"))
    assert {"pytorch", "tf2"} <= set(human(load(built=True, GPUS="0")))


def test_unset_gpus_no_device_request(load):
    mod = load()
    assert mod.gpu_device_requests(mod.GPU_DEVICE_IDS) is None
    assert "device_requests" not in mod.PlatformSpawner(name="").extra_host_config
