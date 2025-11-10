"""Unit tests for EC2Manager."""

from unittest.mock import MagicMock, patch
import pytest

from ac_server_manager.ec2_manager import EC2Manager


@pytest.fixture
def ec2_manager() -> EC2Manager:
    """Create EC2Manager instance for testing."""
    with patch("boto3.client"), patch("boto3.resource"):
        return EC2Manager("us-east-1")


def test_ec2_manager_init(ec2_manager: EC2Manager) -> None:
    """Test EC2Manager initialization."""
    assert ec2_manager.region == "us-east-1"


def test_create_security_group_already_exists(ec2_manager: EC2Manager) -> None:
    """Test create_security_group when group already exists."""
    ec2_manager.ec2_client.describe_security_groups = MagicMock(
        return_value={"SecurityGroups": [{"GroupId": "sg-12345"}]}
    )

    result = ec2_manager.create_security_group("test-sg", "Test security group")

    assert result == "sg-12345"


def test_create_security_group_new(ec2_manager: EC2Manager) -> None:
    """Test create_security_group when creating new group."""
    ec2_manager.ec2_client.describe_security_groups = MagicMock(return_value={"SecurityGroups": []})
    ec2_manager.ec2_client.create_security_group = MagicMock(return_value={"GroupId": "sg-67890"})
    ec2_manager.ec2_client.authorize_security_group_ingress = MagicMock()

    result = ec2_manager.create_security_group("test-sg", "Test security group")

    assert result == "sg-67890"
    ec2_manager.ec2_client.create_security_group.assert_called_once()
    ec2_manager.ec2_client.authorize_security_group_ingress.assert_called_once()


def test_get_ubuntu_ami_success(ec2_manager: EC2Manager) -> None:
    """Test getting Ubuntu AMI."""
    ec2_manager.ec2_client.describe_images = MagicMock(
        return_value={
            "Images": [
                {"ImageId": "ami-old", "CreationDate": "2023-01-01T00:00:00.000Z"},
                {"ImageId": "ami-new", "CreationDate": "2023-12-01T00:00:00.000Z"},
            ]
        }
    )

    result = ec2_manager.get_ubuntu_ami()

    assert result == "ami-new"


def test_get_ubuntu_ami_not_found(ec2_manager: EC2Manager) -> None:
    """Test getting Ubuntu AMI when none found."""
    ec2_manager.ec2_client.describe_images = MagicMock(return_value={"Images": []})

    result = ec2_manager.get_ubuntu_ami()

    assert result is None


def test_launch_instance_success(ec2_manager: EC2Manager) -> None:
    """Test successful instance launch."""
    ec2_manager.ec2_client.run_instances = MagicMock(
        return_value={"Instances": [{"InstanceId": "i-12345"}]}
    )
    ec2_manager.ec2_client.get_waiter = MagicMock()

    result = ec2_manager.launch_instance(
        ami_id="ami-12345",
        instance_type="t3.small",
        security_group_id="sg-12345",
        user_data="#!/bin/bash",
        instance_name="test-instance",
    )

    assert result == "i-12345"
    ec2_manager.ec2_client.run_instances.assert_called_once()


def test_launch_instance_with_key(ec2_manager: EC2Manager) -> None:
    """Test instance launch with SSH key."""
    ec2_manager.ec2_client.run_instances = MagicMock(
        return_value={"Instances": [{"InstanceId": "i-12345"}]}
    )
    ec2_manager.ec2_client.get_waiter = MagicMock()

    result = ec2_manager.launch_instance(
        ami_id="ami-12345",
        instance_type="t3.small",
        security_group_id="sg-12345",
        user_data="#!/bin/bash",
        instance_name="test-instance",
        key_name="my-key",
    )

    assert result == "i-12345"
    call_args = ec2_manager.ec2_client.run_instances.call_args[1]
    assert call_args["KeyName"] == "my-key"


def test_get_instance_public_ip(ec2_manager: EC2Manager) -> None:
    """Test getting instance public IP."""
    ec2_manager.ec2_client.describe_instances = MagicMock(
        return_value={"Reservations": [{"Instances": [{"PublicIpAddress": "1.2.3.4"}]}]}
    )

    result = ec2_manager.get_instance_public_ip("i-12345")

    assert result == "1.2.3.4"


def test_get_instance_public_ip_not_found(ec2_manager: EC2Manager) -> None:
    """Test getting instance public IP when not found."""
    ec2_manager.ec2_client.describe_instances = MagicMock(return_value={"Reservations": []})

    result = ec2_manager.get_instance_public_ip("i-12345")

    assert result is None


def test_stop_instance(ec2_manager: EC2Manager) -> None:
    """Test stopping instance."""
    ec2_manager.ec2_client.stop_instances = MagicMock()

    result = ec2_manager.stop_instance("i-12345")

    assert result is True
    ec2_manager.ec2_client.stop_instances.assert_called_once_with(InstanceIds=["i-12345"])


def test_start_instance(ec2_manager: EC2Manager) -> None:
    """Test starting instance."""
    ec2_manager.ec2_client.start_instances = MagicMock()

    result = ec2_manager.start_instance("i-12345")

    assert result is True
    ec2_manager.ec2_client.start_instances.assert_called_once_with(InstanceIds=["i-12345"])


def test_terminate_instance(ec2_manager: EC2Manager) -> None:
    """Test terminating instance."""
    ec2_manager.ec2_client.terminate_instances = MagicMock()

    result = ec2_manager.terminate_instance("i-12345")

    assert result is True
    ec2_manager.ec2_client.terminate_instances.assert_called_once_with(InstanceIds=["i-12345"])


def test_terminate_instance_and_wait_success(ec2_manager: EC2Manager) -> None:
    """Test terminating instance with wait."""
    ec2_manager.ec2_client.describe_instances = MagicMock(
        return_value={
            "Reservations": [
                {"Instances": [{"InstanceId": "i-12345", "State": {"Name": "running"}}]}
            ]
        }
    )
    ec2_manager.ec2_client.terminate_instances = MagicMock()
    mock_waiter = MagicMock()
    ec2_manager.ec2_client.get_waiter = MagicMock(return_value=mock_waiter)

    result = ec2_manager.terminate_instance_and_wait("i-12345")

    assert result is True
    ec2_manager.ec2_client.terminate_instances.assert_called_once()
    mock_waiter.wait.assert_called_once()


def test_terminate_instance_and_wait_already_terminated(ec2_manager: EC2Manager) -> None:
    """Test terminating instance that's already terminated."""
    ec2_manager.ec2_client.describe_instances = MagicMock(
        return_value={
            "Reservations": [
                {"Instances": [{"InstanceId": "i-12345", "State": {"Name": "terminated"}}]}
            ]
        }
    )
    ec2_manager.ec2_client.terminate_instances = MagicMock()

    result = ec2_manager.terminate_instance_and_wait("i-12345")

    assert result is True
    ec2_manager.ec2_client.terminate_instances.assert_not_called()


def test_terminate_instance_and_wait_not_found(ec2_manager: EC2Manager) -> None:
    """Test terminating instance that doesn't exist."""
    from botocore.exceptions import ClientError

    ec2_manager.ec2_client.describe_instances = MagicMock(
        side_effect=ClientError(
            {"Error": {"Code": "InvalidInstanceID.NotFound"}}, "describe_instances"
        )
    )

    result = ec2_manager.terminate_instance_and_wait("i-12345")

    assert result is True


def test_terminate_instance_and_wait_dry_run(ec2_manager: EC2Manager) -> None:
    """Test terminating instance in dry-run mode."""
    ec2_manager.ec2_client.describe_instances = MagicMock(
        return_value={
            "Reservations": [
                {"Instances": [{"InstanceId": "i-12345", "State": {"Name": "running"}}]}
            ]
        }
    )
    ec2_manager.ec2_client.terminate_instances = MagicMock()

    result = ec2_manager.terminate_instance_and_wait("i-12345", dry_run=True)

    assert result is True
    ec2_manager.ec2_client.terminate_instances.assert_not_called()


def test_find_instances_by_name(ec2_manager: EC2Manager) -> None:
    """Test finding instances by name."""
    ec2_manager.ec2_client.describe_instances = MagicMock(
        return_value={
            "Reservations": [
                {"Instances": [{"InstanceId": "i-12345"}]},
                {"Instances": [{"InstanceId": "i-67890"}]},
            ]
        }
    )

    result = ec2_manager.find_instances_by_name("test-instance")

    assert len(result) == 2
    assert "i-12345" in result
    assert "i-67890" in result


def test_find_instances_by_name_none_found(ec2_manager: EC2Manager) -> None:
    """Test finding instances by name when none exist."""
    ec2_manager.ec2_client.describe_instances = MagicMock(return_value={"Reservations": []})

    result = ec2_manager.find_instances_by_name("test-instance")

    assert result == []


def test_get_instance_details_success(ec2_manager: EC2Manager) -> None:
    """Test getting instance details successfully."""
    from datetime import datetime

    ec2_manager.ec2_client.describe_instances = MagicMock(
        return_value={
            "Reservations": [
                {
                    "Instances": [
                        {
                            "InstanceId": "i-12345",
                            "State": {"Name": "running"},
                            "InstanceType": "t3.small",
                            "PublicIpAddress": "1.2.3.4",
                            "PrivateIpAddress": "10.0.0.1",
                            "LaunchTime": datetime(2024, 1, 1),
                            "Tags": [
                                {"Key": "Name", "Value": "test-instance"},
                                {"Key": "Application", "Value": "ac-server"},
                            ],
                        }
                    ]
                }
            ]
        }
    )

    result = ec2_manager.get_instance_details("i-12345")

    assert result is not None
    assert result["instance_id"] == "i-12345"
    assert result["state"] == "running"
    assert result["instance_type"] == "t3.small"
    assert result["public_ip"] == "1.2.3.4"
    assert result["private_ip"] == "10.0.0.1"
    assert result["name"] == "test-instance"


def test_get_instance_details_not_found(ec2_manager: EC2Manager) -> None:
    """Test getting instance details when instance not found."""
    ec2_manager.ec2_client.describe_instances = MagicMock(return_value={"Reservations": []})

    result = ec2_manager.get_instance_details("i-99999")

    assert result is None


def test_get_instance_details_no_public_ip(ec2_manager: EC2Manager) -> None:
    """Test getting instance details when no public IP assigned."""
    from datetime import datetime

    ec2_manager.ec2_client.describe_instances = MagicMock(
        return_value={
            "Reservations": [
                {
                    "Instances": [
                        {
                            "InstanceId": "i-12345",
                            "State": {"Name": "stopped"},
                            "InstanceType": "t3.small",
                            "PrivateIpAddress": "10.0.0.1",
                            "LaunchTime": datetime(2024, 1, 1),
                            "Tags": [{"Key": "Name", "Value": "test-instance"}],
                        }
                    ]
                }
            ]
        }
    )

    result = ec2_manager.get_instance_details("i-12345")

    assert result is not None
    assert result["instance_id"] == "i-12345"
    assert result["state"] == "stopped"
    assert result["public_ip"] is None


def test_upload_bootstrap_to_s3_success(ec2_manager: EC2Manager) -> None:
    """Test successful bootstrap script upload to S3."""
    from unittest.mock import MagicMock

    mock_s3_manager = MagicMock()
    mock_s3_manager.bucket_name = "test-bucket"
    mock_s3_manager.upload_bytes = MagicMock(return_value=True)
    mock_s3_manager.generate_presigned_url = MagicMock(
        return_value="https://test-bucket.s3.amazonaws.com/bootstrap/test.sh?signature=..."
    )

    bootstrap_script = "#!/bin/bash\necho 'test'"
    result = ec2_manager.upload_bootstrap_to_s3(mock_s3_manager, bootstrap_script)

    assert result is not None
    s3_key, presigned_url = result
    assert s3_key.startswith("bootstrap/bootstrap-")
    assert s3_key.endswith(".sh")
    assert presigned_url == "https://test-bucket.s3.amazonaws.com/bootstrap/test.sh?signature=..."
    mock_s3_manager.upload_bytes.assert_called_once()
    mock_s3_manager.generate_presigned_url.assert_called_once()


def test_upload_bootstrap_to_s3_upload_fails(ec2_manager: EC2Manager) -> None:
    """Test bootstrap upload when S3 upload fails."""
    from unittest.mock import MagicMock

    mock_s3_manager = MagicMock()
    mock_s3_manager.upload_bytes = MagicMock(return_value=False)

    bootstrap_script = "#!/bin/bash\necho 'test'"
    result = ec2_manager.upload_bootstrap_to_s3(mock_s3_manager, bootstrap_script)

    assert result is None


def test_upload_bootstrap_to_s3_presigned_url_fails(ec2_manager: EC2Manager) -> None:
    """Test bootstrap upload when presigned URL generation fails."""
    from unittest.mock import MagicMock

    mock_s3_manager = MagicMock()
    mock_s3_manager.upload_bytes = MagicMock(return_value=True)
    mock_s3_manager.generate_presigned_url = MagicMock(return_value=None)

    bootstrap_script = "#!/bin/bash\necho 'test'"
    result = ec2_manager.upload_bootstrap_to_s3(mock_s3_manager, bootstrap_script)

    assert result is None


def test_create_minimal_user_data_with_presigned_url(ec2_manager: EC2Manager) -> None:
    """Test minimal user data script creation with presigned URL."""
    presigned_url = "https://test-bucket.s3.amazonaws.com/bootstrap/test.sh?X-Amz-Signature=..."

    user_data = ec2_manager.create_minimal_user_data_with_presigned_url(presigned_url)

    # Check script structure
    assert "#!/bin/bash" in user_data
    assert "set -e" in user_data

    # Check download logic with both curl and wget
    assert "curl" in user_data
    assert "wget" in user_data
    assert presigned_url in user_data

    # Check bootstrap path
    assert "/tmp/bootstrap.sh" in user_data
    assert "BOOTSTRAP_PATH" in user_data

    # Check execution
    assert "chmod +x" in user_data
    assert 'exec "$BOOTSTRAP_PATH"' in user_data

    # Verify size is small
    size = len(user_data.encode("utf-8"))
    assert size < 2000, f"Minimal user data should be < 2KB, got {size} bytes"


def test_create_minimal_user_data_size_is_under_16kb(ec2_manager: EC2Manager) -> None:
    """Test that minimal user data stays well under 16KB limit."""
    # Even with a very long presigned URL (AWS URLs can be quite long)
    long_presigned_url = (
        "https://test-bucket.s3.us-east-1.amazonaws.com/"
        "bootstrap/bootstrap-20231201-123456-abcd1234.sh?"
        "X-Amz-Algorithm=AWS4-HMAC-SHA256&"
        "X-Amz-Credential=AKIAIOSFODNN7EXAMPLE%2F20231201%2Fus-east-1%2Fs3%2Faws4_request&"
        "X-Amz-Date=20231201T120000Z&"
        "X-Amz-Expires=3600&"
        "X-Amz-SignedHeaders=host&"
        "X-Amz-Signature=abcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890"
    )

    user_data = ec2_manager.create_minimal_user_data_with_presigned_url(long_presigned_url)

    size = len(user_data.encode("utf-8"))
    assert size < 16384, f"User data must be under 16KB, got {size} bytes"
    assert size < 2000, f"Minimal user data should be well under 16KB, got {size} bytes"




def test_create_assettoserver_native_user_data_script(ec2_manager: EC2Manager) -> None:
    """Test AssettoServer native binary user data script creation."""
    script = ec2_manager.create_assettoserver_native_user_data_script(
        "test-bucket", "packs/test.tar.gz", "v0.0.55-pre31"
    )

    # Basic script structure
    assert "#!/bin/bash" in script
    assert "set -euo pipefail" in script
    
    # Deployment logging
    assert "DEPLOY_LOG=\"/var/log/assettoserver-deploy.log\"" in script
    assert "STATUS_FILE=\"/opt/assettoserver/deploy-status.json\"" in script
    
    # Dependencies (no Docker!)
    assert "apt-get install" in script
    assert "awscli" in script
    assert "python3" in script
    assert "wget" in script
    assert "tar" in script
    assert "docker" not in script.lower() or "docker" not in script  # Should not install Docker
    
    # S3 download
    assert "aws s3 cp s3://test-bucket/packs/test.tar.gz" in script
    assert "MAX_RETRIES" in script
    
    # AssettoServer binary download from GitHub
    assert "https://github.com/compujuckel/AssettoServer/releases/download/v0.0.55-pre31/assetto-server-linux-x64.tar.gz" in script
    assert "wget" in script
    
    # Binary extraction and setup
    assert "tar -xzf assettoserver-binary.tar.gz" in script
    assert "chmod +x AssettoServer" in script
    
    # Preparation tool
    assert "assetto_server_prepare.py" in script
    assert "python3 ./assetto_server_prepare.py" in script
    
    # Systemd service (not Docker)
    assert "/etc/systemd/system/assettoserver.service" in script
    assert "systemctl daemon-reload" in script
    assert "systemctl enable assettoserver" in script
    assert "systemctl start assettoserver" in script
    assert "WorkingDirectory=/opt/assettoserver" in script
    assert "ExecStart=/opt/assettoserver/AssettoServer" in script
    
    # No Docker Compose
    assert "docker-compose" not in script
    assert "docker compose" not in script
    
    # Status checks
    assert "systemctl is-active" in script
    assert "write_status" in script
