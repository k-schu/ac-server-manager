"""Unit tests for CLI commands."""

from datetime import datetime
from unittest.mock import MagicMock, patch
import pytest
from click.testing import CliRunner

from ac_server_manager.cli import status
from ac_server_manager.config import AC_SERVER_HTTP_PORT, AC_SERVER_TCP_PORT


@pytest.fixture
def runner() -> CliRunner:
    """Create CLI test runner."""
    return CliRunner()


def test_status_command_displays_acstuff_url(runner: CliRunner) -> None:
    """Test that status command displays correct acstuff.ru join link format."""
    mock_details = {
        "instance_id": "i-12345",
        "state": "running",
        "instance_type": "t3.small",
        "public_ip": "1.2.3.4",
        "private_ip": "10.0.0.1",
        "launch_time": datetime(2024, 1, 1),
        "name": "test-instance",
    }

    with (
        patch("ac_server_manager.cli.Deployer") as MockDeployer,
        patch("ac_server_manager.cli.check_host_reachable") as mock_ping,
        patch("ac_server_manager.cli.check_tcp_port") as mock_tcp,
        patch("ac_server_manager.cli.check_udp_port") as mock_udp,
        patch("ac_server_manager.cli.check_url_accessible") as mock_url,
    ):

        mock_deployer_instance = MagicMock()
        mock_deployer_instance.get_status.return_value = mock_details
        MockDeployer.return_value = mock_deployer_instance

        # Mock connectivity checks to pass
        mock_ping.return_value = True
        mock_tcp.return_value = True
        mock_udp.return_value = True
        mock_url.return_value = (True, None)

        result = runner.invoke(status)

        assert result.exit_code == 0
        # Check that the new acstuff.ru URL format is displayed with & separators
        expected_url = f"https://acstuff.ru/s/q:race/online/join?ip=1.2.3.4&httpPort={AC_SERVER_HTTP_PORT}&password="
        assert expected_url in result.output
        assert "acstuff.ru link:" in result.output
        # Ensure old format with colon is not present
        assert f"1.2.3.4:{AC_SERVER_TCP_PORT}" not in result.output.split("acstuff.ru link:")[1]


def test_status_command_displays_connection_info(runner: CliRunner) -> None:
    """Test that status command displays all connection information."""
    mock_details = {
        "instance_id": "i-12345",
        "state": "running",
        "instance_type": "t3.small",
        "public_ip": "1.2.3.4",
        "private_ip": "10.0.0.1",
        "launch_time": datetime(2024, 1, 1),
        "name": "test-instance",
    }

    with (
        patch("ac_server_manager.cli.Deployer") as MockDeployer,
        patch("ac_server_manager.cli.check_host_reachable") as mock_ping,
        patch("ac_server_manager.cli.check_tcp_port") as mock_tcp,
        patch("ac_server_manager.cli.check_udp_port") as mock_udp,
        patch("ac_server_manager.cli.check_url_accessible") as mock_url,
    ):

        mock_deployer_instance = MagicMock()
        mock_deployer_instance.get_status.return_value = mock_details
        MockDeployer.return_value = mock_deployer_instance

        # Mock connectivity checks to pass
        mock_ping.return_value = True
        mock_tcp.return_value = True
        mock_udp.return_value = True
        mock_url.return_value = (True, None)

        result = runner.invoke(status)

        assert result.exit_code == 0
        assert "Instance ID: i-12345" in result.output
        assert "State:" in result.output
        assert "running" in result.output
        assert "Public IP: 1.2.3.4" in result.output
        assert f"Direct Connect: 1.2.3.4:{AC_SERVER_TCP_PORT}" in result.output
        assert "Join Server:" in result.output
        assert "Connectivity Checks:" in result.output


def test_status_command_no_instance_found(runner: CliRunner) -> None:
    """Test status command when no instance is found."""
    with patch("ac_server_manager.cli.Deployer") as MockDeployer:
        mock_deployer_instance = MagicMock()
        mock_deployer_instance.get_status.return_value = None
        MockDeployer.return_value = mock_deployer_instance

        result = runner.invoke(status)

        assert result.exit_code == 1
        assert "No instance found" in result.output


def test_status_command_instance_not_running(runner: CliRunner) -> None:
    """Test status command when instance is not in running state."""
    mock_details = {
        "instance_id": "i-12345",
        "state": "stopped",
        "instance_type": "t3.small",
        "public_ip": None,
        "private_ip": "10.0.0.1",
        "launch_time": datetime(2024, 1, 1),
        "name": "test-instance",
    }

    with patch("ac_server_manager.cli.Deployer") as MockDeployer:
        mock_deployer_instance = MagicMock()
        mock_deployer_instance.get_status.return_value = mock_details
        MockDeployer.return_value = mock_deployer_instance

        result = runner.invoke(status)

        assert result.exit_code == 0
        assert "Instance is stopped" in result.output
        # Should not display acstuff.ru link for stopped instance
        assert "acstuff.ru" not in result.output


def test_status_command_connectivity_checks_failing(runner: CliRunner) -> None:
    """Test that status command displays connectivity check failures."""
    mock_details = {
        "instance_id": "i-12345",
        "state": "running",
        "instance_type": "t3.small",
        "public_ip": "1.2.3.4",
        "private_ip": "10.0.0.1",
        "launch_time": datetime(2024, 1, 1),
        "name": "test-instance",
    }

    with (
        patch("ac_server_manager.cli.Deployer") as MockDeployer,
        patch("ac_server_manager.cli.check_host_reachable") as mock_ping,
        patch("ac_server_manager.cli.check_tcp_port") as mock_tcp,
        patch("ac_server_manager.cli.check_udp_port") as mock_udp,
        patch("ac_server_manager.cli.check_url_accessible") as mock_url,
    ):

        mock_deployer_instance = MagicMock()
        mock_deployer_instance.get_status.return_value = mock_details
        MockDeployer.return_value = mock_deployer_instance

        # Mock connectivity checks to fail
        mock_ping.return_value = False
        mock_tcp.return_value = False
        mock_udp.return_value = False
        mock_url.return_value = (False, "HTTP 404")

        result = runner.invoke(status)

        assert result.exit_code == 0
        assert "Connectivity Checks:" in result.output
        assert "is not reachable" in result.output
        assert "is not accessible" in result.output
        assert "failed" in result.output or "not accessible" in result.output
