from pathlib import Path
from tempfile import TemporaryDirectory

from app.core.settings import settings
from app.services.sandbox_service import SandboxService


temporary_root = TemporaryDirectory()
workspace = Path(temporary_root.name) / "workspace"
workspace.mkdir()

original_mode = settings.sandbox_mode
original_image = settings.sandbox_docker_image
original_executable = settings.sandbox_docker_executable
original_network = settings.sandbox_allow_network
original_docker_executable = SandboxService._docker_executable
original_image_available = SandboxService._image_is_available

try:
    settings.sandbox_mode = "host"
    host = SandboxService.prepare(["pytest", "-q"], workspace, ".", "hosttest")
    assert host.environment == "host"
    assert host.command == ["pytest", "-q"]

    settings.sandbox_mode = "docker"
    settings.sandbox_docker_image = "test-sandbox:latest"
    settings.sandbox_docker_executable = "docker"
    settings.sandbox_allow_network = False
    SandboxService._docker_executable = staticmethod(lambda: "docker")
    SandboxService._image_is_available = staticmethod(lambda executable, image: True)
    docker = SandboxService.prepare(["pytest", "-q"], workspace, "tests", "Run123")
    assert docker.environment == "docker"
    assert docker.container_name == "mycodexai-run123"
    assert "--read-only" in docker.command
    assert "--network" in docker.command
    assert docker.command[docker.command.index("--network") + 1] == "none"
    mount = docker.command[docker.command.index("--mount") + 1]
    assert "type=bind" in mount
    assert ",rw" not in mount
    assert docker.command[-3:] == ["test-sandbox:latest", "pytest", "-q"]

    SandboxService._docker_executable = staticmethod(lambda: None)
    status = SandboxService.status()
    assert status["ready"] is False
    assert status["isolated"] is True
finally:
    settings.sandbox_mode = original_mode
    settings.sandbox_docker_image = original_image
    settings.sandbox_docker_executable = original_executable
    settings.sandbox_allow_network = original_network
    SandboxService._docker_executable = original_docker_executable
    SandboxService._image_is_available = original_image_available
    temporary_root.cleanup()

print("sandbox=ok")
