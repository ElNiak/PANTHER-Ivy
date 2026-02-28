"""Docker-aware executor for Ivy commands.

Provides hybrid execution: Docker container (preferred) or native subprocess.

Execution priority:
  1. docker exec <running_container> — instant if PANTHER experiment running
  2. docker run --rm -v ... <image> — works anytime image exists locally
  3. native subprocess — fallback for environments with Ivy deps installed
"""
import logging
import os
import shlex
import subprocess
from typing import List, Optional

from .types import CommandResult as ApiCommandResult, ExecutionResult

logger = logging.getLogger(__name__)


class IvyExecutor:
    """Execute Ivy commands with hybrid Docker/native support.

    Uses Docker SDK when available, falls back to subprocess docker CLI,
    then to native execution.
    """

    def __init__(
        self,
        docker_image: Optional[str] = None,
        container_name_prefix: str = "panther_ivy",
    ):
        self.docker_image = docker_image
        self.container_name_prefix = container_name_prefix
        self._docker_client = None
        self._docker_available: Optional[bool] = None

    @property
    def docker_available(self) -> bool:
        if self._docker_available is not None:
            return self._docker_available
        self._docker_available = self._check_docker()
        return self._docker_available

    def _check_docker(self) -> bool:
        """Check if Docker daemon is accessible."""
        # Try Docker SDK first
        try:
            import docker

            client = docker.from_env()
            client.ping()
            self._docker_client = client
            return True
        except Exception:
            pass

        # Fall back to CLI check
        try:
            result = subprocess.run(
                ["docker", "info"],
                capture_output=True,
                timeout=5,
            )
            return result.returncode == 0
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return False

    def execute(
        self,
        api_cmd: ApiCommandResult,
        workspace_root: Optional[str] = None,
        timeout: int = 300,
    ) -> ExecutionResult:
        """Execute an API CommandResult via Docker or native fallback.

        Args:
            api_cmd: CommandResult from compiler/runner API.
            workspace_root: Host path to mount into container.
            timeout: Execution timeout in seconds.
        """
        # 1. Try docker exec into running container
        if self.docker_image and self.docker_available:
            container_id = self._find_running_container()
            if container_id:
                logger.info("Using running container %s", container_id[:12])
                return self._exec_in_container(
                    container_id, api_cmd, timeout
                )

        # 2. Try docker run with volume mount
        if self.docker_image and self.docker_available and self._image_available():
            logger.info("Using docker run with image %s", self.docker_image)
            return self._run_in_new_container(
                api_cmd, workspace_root or os.getcwd(), timeout
            )

        # 3. Native fallback
        logger.info("Using native subprocess execution")
        return self._run_native(api_cmd, timeout)

    def _find_running_container(self) -> Optional[str]:
        """Find a running container matching the image or name prefix."""
        image = self.docker_image or self.container_name_prefix

        # Try Docker SDK
        if self._docker_client:
            try:
                containers = self._docker_client.containers.list(
                    filters={"ancestor": image}, limit=1
                )
                if containers:
                    return containers[0].id
            except Exception:
                logger.debug("SDK container lookup failed", exc_info=True)

        # Fallback: CLI
        try:
            filter_arg = f"ancestor={image}"
            result = subprocess.run(
                ["docker", "ps", "-q", "--filter", filter_arg, "--no-trunc"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result.returncode == 0 and result.stdout.strip():
                return result.stdout.strip().splitlines()[0]
        except (FileNotFoundError, subprocess.TimeoutExpired):
            pass

        return None

    def _image_available(self) -> bool:
        """Check if the Docker image exists locally."""
        if not self.docker_image:
            return False

        if self._docker_client:
            try:
                self._docker_client.images.get(self.docker_image)
                return True
            except Exception:
                return False

        try:
            result = subprocess.run(
                ["docker", "image", "inspect", self.docker_image],
                capture_output=True,
                timeout=5,
            )
            return result.returncode == 0
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return False

    def _exec_in_container(
        self,
        container_id: str,
        api_cmd: ApiCommandResult,
        timeout: int,
    ) -> ExecutionResult:
        """Execute commands inside a running container via docker exec."""
        last_result = _empty_result("docker")

        for cmd_str in api_cmd.commands:
            docker_cmd = ["docker", "exec"]
            if api_cmd.working_dir:
                docker_cmd.extend(["-w", api_cmd.working_dir])
            for key, val in (api_cmd.environment or {}).items():
                docker_cmd.extend(["-e", f"{key}={val}"])
            docker_cmd.extend([container_id, "sh", "-c", cmd_str])

            last_result = self._run_subprocess(docker_cmd, timeout)
            if last_result.exit_code != 0:
                break

        return ExecutionResult(
            exit_code=last_result.exit_code,
            stdout=last_result.stdout,
            stderr=last_result.stderr,
            target="docker",
        )

    def _run_in_new_container(
        self,
        api_cmd: ApiCommandResult,
        workspace_root: str,
        timeout: int,
    ) -> ExecutionResult:
        """Execute commands in a new docker run --rm container."""
        assert self.docker_image is not None
        last_result = _empty_result("docker")

        for cmd_str in api_cmd.commands:
            docker_cmd = ["docker", "run", "--rm"]
            docker_cmd.extend(["-v", f"{workspace_root}:/workspace"])
            for key, val in (api_cmd.environment or {}).items():
                docker_cmd.extend(["-e", f"{key}={val}"])
            if api_cmd.working_dir:
                docker_cmd.extend(["-w", api_cmd.working_dir])
            docker_cmd.extend([self.docker_image, "sh", "-c", cmd_str])

            last_result = self._run_subprocess(docker_cmd, timeout)
            if last_result.exit_code != 0:
                break

        return ExecutionResult(
            exit_code=last_result.exit_code,
            stdout=last_result.stdout,
            stderr=last_result.stderr,
            target="docker",
        )

    def _run_native(
        self,
        api_cmd: ApiCommandResult,
        timeout: int,
    ) -> ExecutionResult:
        """Execute commands natively as subprocess."""
        last_result = _empty_result("host")

        env = None
        if api_cmd.environment:
            env = {**os.environ, **api_cmd.environment}

        for cmd_str in api_cmd.commands:
            cmd_parts = shlex.split(cmd_str)
            try:
                result = subprocess.run(
                    cmd_parts,
                    capture_output=True,
                    text=True,
                    timeout=timeout,
                    cwd=api_cmd.working_dir if api_cmd.working_dir else None,
                    env=env,
                )
                last_result = ExecutionResult(
                    exit_code=result.returncode,
                    stdout=result.stdout,
                    stderr=result.stderr,
                    target="host",
                )
            except FileNotFoundError:
                last_result = ExecutionResult(
                    exit_code=127,
                    stdout="",
                    stderr=f"Command not found: {cmd_parts[0]}",
                    target="host",
                )
            except subprocess.TimeoutExpired:
                last_result = ExecutionResult(
                    exit_code=124,
                    stdout="",
                    stderr=f"Timed out after {timeout}s",
                    target="host",
                )

            if last_result.exit_code != 0:
                break

        return last_result

    def _run_subprocess(
        self, cmd: List[str], timeout: int
    ) -> ExecutionResult:
        """Run a subprocess command and return ExecutionResult."""
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout,
            )
            return ExecutionResult(
                exit_code=result.returncode,
                stdout=result.stdout,
                stderr=result.stderr,
                target="docker",
            )
        except FileNotFoundError:
            return ExecutionResult(
                exit_code=127,
                stdout="",
                stderr=f"Command not found: {cmd[0]}",
                target="docker",
            )
        except subprocess.TimeoutExpired:
            return ExecutionResult(
                exit_code=124,
                stdout="",
                stderr=f"Timed out after {timeout}s",
                target="docker",
            )


def _empty_result(target: str) -> ExecutionResult:
    return ExecutionResult(exit_code=0, stdout="", stderr="", target=target)
