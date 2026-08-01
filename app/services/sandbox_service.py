"""Fail-closed Docker command isolation for project execution surfaces."""

from dataclasses import dataclass
from pathlib import Path, PurePosixPath
import os
import shutil
import subprocess
from typing import Literal

from app.core.settings import settings


SandboxMode = Literal["host", "docker"]


class SandboxError(ValueError):
    """A safe configuration or runtime error for isolated execution."""


@dataclass(frozen=True)
class SandboxLaunch:
    command: list[str]
    environment: str
    container_name: str | None = None


class SandboxService:
    """Create direct Docker invocations without silently falling back to host."""

    @classmethod
    def mode(cls) -> SandboxMode:
        mode = settings.sandbox_mode.strip().casefold()
        if mode not in {"host", "docker"}:
            raise SandboxError("SANDBOX_MODE must be either 'host' or 'docker'.")
        return mode  # type: ignore[return-value]

    @classmethod
    def is_docker_mode(cls) -> bool:
        return cls.mode() == "docker"

    @classmethod
    def status(cls) -> dict[str, object]:
        try:
            mode = cls.mode()
        except SandboxError as error:
            return {"mode": settings.sandbox_mode, "ready": False, "isolated": False, "reason": str(error)}
        if mode == "host":
            return {
                "mode": "host",
                "ready": True,
                "isolated": False,
                "reason": "Commands run with the existing workspace policy on the API host.",
            }

        executable = cls._docker_executable()
        if executable is None:
            return {
                "mode": "docker",
                "ready": False,
                "isolated": True,
                "reason": "Docker CLI is not available. Install and start Docker Desktop, then build the configured sandbox image.",
            }
        if not cls._image_is_available(executable, settings.sandbox_docker_image):
            return {
                "mode": "docker",
                "ready": False,
                "isolated": True,
                "reason": f"Docker image '{settings.sandbox_docker_image}' is not available. Build the sandbox image before running commands.",
            }
        return {
            "mode": "docker",
            "ready": True,
            "isolated": True,
            "reason": "Docker sandbox is ready: network disabled by default, read-only container root, limited CPU/memory/PIDs.",
        }

    @classmethod
    def prepare(
        cls,
        command: list[str],
        workspace_path: Path,
        working_directory: str,
        container_suffix: str,
    ) -> SandboxLaunch:
        if cls.mode() == "host":
            return SandboxLaunch(command=list(command), environment="host")
        if not command:
            raise SandboxError("Sandbox command must not be empty.")
        if not container_suffix or not all(character.isalnum() or character == "-" for character in container_suffix):
            raise SandboxError("Sandbox container identifier is invalid.")

        executable = cls._docker_executable()
        if executable is None:
            raise SandboxError("Docker sandbox is selected but Docker CLI is not available. No host fallback was used.")
        if not cls._image_is_available(executable, settings.sandbox_docker_image):
            raise SandboxError(
                f"Docker sandbox image '{settings.sandbox_docker_image}' is unavailable. No host fallback was used."
            )

        workspace = workspace_path.resolve()
        if not workspace.is_dir():
            raise SandboxError("Sandbox workspace directory is not available.")
        path = PurePosixPath(working_directory.replace("\\", "/"))
        if path.is_absolute() or any(part in {"", ".", ".."} for part in path.parts if part != "."):
            raise SandboxError("Sandbox working directory must stay inside the project workspace.")
        container_workdir = "/workspace" if str(path) in {"", "."} else "/workspace/" + path.as_posix()
        container_name = f"mycodexai-{container_suffix.casefold()[:48]}"

        docker_command = [
            executable,
            "run",
            "--rm",
            "--init",
            "--name",
            container_name,
            "--workdir",
            container_workdir,
            "--mount",
            f"type=bind,src={workspace},dst=/workspace",
            "--read-only",
            "--tmpfs",
            "/tmp:rw,noexec,nosuid,size=256m",
            "--cap-drop=ALL",
            "--security-opt=no-new-privileges:true",
            "--pids-limit",
            str(settings.sandbox_pids_limit),
            "--memory",
            f"{settings.sandbox_memory_mb}m",
            "--cpus",
            str(settings.sandbox_cpus),
            "--user",
            settings.sandbox_container_user,
            "--env",
            "HOME=/tmp",
        ]
        if settings.sandbox_allow_network:
            docker_command.extend(["--network", "bridge"])
        else:
            docker_command.extend(["--network", "none"])
        docker_command.extend([settings.sandbox_docker_image, *command])
        return SandboxLaunch(command=docker_command, environment="docker", container_name=container_name)

    @classmethod
    def stop(cls, container_name: str | None) -> None:
        if not container_name or cls.mode() != "docker":
            return
        executable = cls._docker_executable()
        if executable is None:
            return
        try:
            subprocess.run(
                [executable, "stop", "--time", "2", container_name],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=8,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired):
            return

    @staticmethod
    def _docker_executable() -> str | None:
        configured = settings.sandbox_docker_executable.strip()
        if configured:
            path = Path(configured)
            return str(path) if path.is_file() else None
        discovered = shutil.which("docker")
        if discovered:
            return discovered
        local_app_data = os.environ.get("LOCALAPPDATA", "")
        per_user_desktop = Path(local_app_data) / "Programs" / "DockerDesktop" / "resources" / "bin" / "docker.exe"
        system_desktop = Path(os.environ.get("PROGRAMFILES", "")) / "Docker" / "Docker" / "resources" / "bin" / "docker.exe"
        for candidate in (per_user_desktop, system_desktop):
            if candidate.is_file():
                return str(candidate)
        return None

    @staticmethod
    def _image_is_available(executable: str, image: str) -> bool:
        try:
            completed = subprocess.run(
                [executable, "image", "inspect", image],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=8,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired):
            return False
        return completed.returncode == 0
