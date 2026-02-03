"""Tests for contree_mcp.prompts module."""

from contree_mcp.prompts import (
    build_project,
    install_packages,
    parallel_tasks,
    run_python,
    run_shell,
    sync_and_run,
)


class TestRunPython:
    """Tests for run_python prompt."""

    def test_generates_python_prompt(self) -> None:
        """Test run_python generates proper prompt."""
        code = "print('hello')"
        result = run_python(code)

        assert "print('hello')" in result
        assert "python" in result.lower()
        assert "run" in result


class TestRunShell:
    """Tests for run_shell prompt."""

    def test_generates_shell_prompt(self) -> None:
        """Test run_shell generates proper prompt."""
        result = run_shell("ls -la")

        assert "ls -la" in result
        assert "ubuntu:noble" in result

    def test_custom_image(self) -> None:
        """Test run_shell with custom image."""
        result = run_shell("ls", image="alpine:latest")

        assert "alpine:latest" in result


class TestSyncAndRun:
    """Tests for sync_and_run prompt."""

    def test_generates_sync_prompt(self) -> None:
        """Test sync_and_run generates proper prompt."""
        result = sync_and_run("/local/project", "python main.py")

        assert "/local/project" in result
        assert "python main.py" in result
        assert "rsync" in result

    def test_custom_image(self) -> None:
        """Test sync_and_run with custom image."""
        result = sync_and_run("/project", "npm test", image="node:18")

        assert "node:18" in result


class TestInstallPackages:
    """Tests for install_packages prompt."""

    def test_generates_install_prompt(self) -> None:
        """Test install_packages generates proper prompt."""
        result = install_packages("requests pytest")

        assert "requests pytest" in result
        assert "pip install" in result
        assert "disposable=false" in result

    def test_custom_image(self) -> None:
        """Test install_packages with custom image."""
        result = install_packages("numpy", image="python:3.12")

        assert "python:3.12" in result


class TestParallelTasks:
    """Tests for parallel_tasks prompt."""

    def test_generates_parallel_prompt(self) -> None:
        """Test parallel_tasks generates proper prompt."""
        tasks = "task1\ntask2\ntask3"
        result = parallel_tasks(tasks)

        assert "task1" in result
        assert "wait=false" in result
        assert "wait_operations" in result

    def test_custom_image(self) -> None:
        """Test parallel_tasks with custom image."""
        result = parallel_tasks("task1", image="custom:latest")

        assert "custom:latest" in result


class TestBuildProject:
    """Tests for build_project prompt."""

    def test_generates_build_prompt(self) -> None:
        """Test build_project generates proper prompt."""
        result = build_project("/my/project")

        assert "/my/project" in result
        assert "pip install" in result
        assert "pytest" in result

    def test_custom_commands(self) -> None:
        """Test build_project with custom commands."""
        result = build_project(
            "/project",
            install_cmd="npm install",
            test_cmd="npm test",
        )

        assert "npm install" in result
        assert "npm test" in result
