"""EC2 operations for AC Server Manager."""

import logging
import uuid
from datetime import datetime, timezone
from typing import Optional

import boto3
from botocore.exceptions import ClientError

from .config import AC_SERVER_HTTP_PORT, AC_SERVER_TCP_PORT, AC_SERVER_UDP_PORT

logger = logging.getLogger(__name__)


class EC2Manager:
    """Manages EC2 operations for AC server deployment."""

    def __init__(self, region: str = "us-east-1"):
        """Initialize EC2 manager.

        Args:
            region: AWS region
        """
        self.region = region
        self.ec2_client = boto3.client("ec2", region_name=region)
        self.ec2_resource = boto3.resource("ec2", region_name=region)

    def create_security_group(
        self, group_name: str, description: str, extra_ports: Optional[list[int]] = None
    ) -> Optional[str]:
        """Create security group with rules for AC server.

        Args:
            group_name: Name of the security group
            description: Description of the security group
            extra_ports: Optional list of additional TCP ports to open (e.g., wrapper port)

        Returns:
            Security group ID, or None if creation failed
        """
        try:
            # Check if security group already exists
            response = self.ec2_client.describe_security_groups(
                Filters=[{"Name": "group-name", "Values": [group_name]}]
            )

            if response["SecurityGroups"]:
                group_id = response["SecurityGroups"][0]["GroupId"]
                logger.info(f"Security group {group_name} already exists: {group_id}")
                return group_id

            # Create security group
            create_response = self.ec2_client.create_security_group(
                GroupName=group_name, Description=description
            )
            group_id = create_response["GroupId"]
            logger.info(f"Created security group {group_name}: {group_id}")

            # Add ingress rules for AC server
            ip_permissions = [
                {
                    "IpProtocol": "tcp",
                    "FromPort": 22,
                    "ToPort": 22,
                    "IpRanges": [{"CidrIp": "0.0.0.0/0", "Description": "SSH"}],
                },
                {
                    "IpProtocol": "tcp",
                    "FromPort": AC_SERVER_HTTP_PORT,
                    "ToPort": AC_SERVER_HTTP_PORT,
                    "IpRanges": [{"CidrIp": "0.0.0.0/0", "Description": "AC HTTP"}],
                },
                {
                    "IpProtocol": "tcp",
                    "FromPort": AC_SERVER_TCP_PORT,
                    "ToPort": AC_SERVER_TCP_PORT,
                    "IpRanges": [{"CidrIp": "0.0.0.0/0", "Description": "AC TCP"}],
                },
                {
                    "IpProtocol": "udp",
                    "FromPort": AC_SERVER_UDP_PORT,
                    "ToPort": AC_SERVER_UDP_PORT,
                    "IpRanges": [{"CidrIp": "0.0.0.0/0", "Description": "AC UDP"}],
                },
            ]

            # Add extra ports if specified
            if extra_ports:
                for port in extra_ports:
                    ip_permissions.append(
                        {
                            "IpProtocol": "tcp",
                            "FromPort": port,
                            "ToPort": port,
                            "IpRanges": [
                                {"CidrIp": "0.0.0.0/0", "Description": f"Extra TCP {port}"}
                            ],
                        }
                    )

            self.ec2_client.authorize_security_group_ingress(
                GroupId=group_id,
                IpPermissions=ip_permissions,  # type: ignore[arg-type]
            )
            logger.info(f"Added ingress rules to security group {group_id}")

            return group_id
        except ClientError as e:
            logger.error(f"Error creating security group: {e}")
            return None

    def get_ubuntu_ami(self) -> Optional[str]:
        """Get the latest Ubuntu 22.04 LTS AMI ID.

        Returns:
            AMI ID, or None if not found
        """
        try:
            # Get latest Ubuntu 22.04 LTS AMI
            response = self.ec2_client.describe_images(
                Filters=[
                    {
                        "Name": "name",
                        "Values": ["ubuntu/images/hvm-ssd/ubuntu-jammy-22.04-amd64-server-*"],
                    },
                    {"Name": "state", "Values": ["available"]},
                    {"Name": "architecture", "Values": ["x86_64"]},
                ],
                Owners=["099720109477"],  # Canonical
            )

            if not response["Images"]:
                logger.error("No Ubuntu AMI found")
                return None

            # Sort by creation date and get the latest
            images = sorted(response["Images"], key=lambda x: x["CreationDate"], reverse=True)
            ami_id: str = images[0]["ImageId"]
            logger.info(f"Found Ubuntu AMI: {ami_id}")
            return ami_id
        except ClientError as e:
            logger.error(f"Error getting AMI: {e}")
            return None


    def upload_bootstrap_to_s3(
        self, s3_manager, bootstrap_script: str
    ) -> Optional[tuple[str, str]]:
        """Upload bootstrap script to S3 and return the key and presigned URL.

        Args:
            s3_manager: S3Manager instance for uploading
            bootstrap_script: Bootstrap script content as string

        Returns:
            Tuple of (s3_key, presigned_url) or None if upload failed
        """
        # Generate unique key with timestamp and UUID
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
        unique_id = str(uuid.uuid4())[:8]
        s3_key = f"bootstrap/bootstrap-{timestamp}-{unique_id}.sh"

        # Upload to S3
        bootstrap_bytes = bootstrap_script.encode("utf-8")
        if not s3_manager.upload_bytes(s3_key, bootstrap_bytes):
            logger.error("Failed to upload bootstrap script to S3")
            return None

        # Generate presigned URL (1 hour expiration)
        presigned_url = s3_manager.generate_presigned_url(s3_key, expiration_secs=3600)
        if not presigned_url:
            logger.error("Failed to generate presigned URL for bootstrap script")
            return None

        logger.info(f"Uploaded bootstrap script to s3://{s3_manager.bucket_name}/{s3_key}")
        return s3_key, presigned_url

    def create_minimal_user_data_with_presigned_url(self, presigned_url: str) -> str:
        """Create minimal user data script that downloads and executes bootstrap from S3.

        Args:
            presigned_url: Presigned S3 URL to download bootstrap script

        Returns:
            Minimal user data script as string
        """
        script = f"""#!/bin/bash
set -e

# Download bootstrap script from S3
BOOTSTRAP_PATH="/tmp/bootstrap.sh"
echo "Downloading bootstrap script..."

# Try curl first, then wget
if command -v curl &>/dev/null; then
    curl -fsSL -o "$BOOTSTRAP_PATH" '{presigned_url}'
elif command -v wget &>/dev/null; then
    wget -q -O "$BOOTSTRAP_PATH" '{presigned_url}'
else
    echo "Error: Neither curl nor wget available"
    exit 1
fi

# Verify download
if [ ! -f "$BOOTSTRAP_PATH" ] || [ ! -s "$BOOTSTRAP_PATH" ]; then
    echo "Error: Failed to download bootstrap script"
    exit 1
fi

# Make executable and run
chmod +x "$BOOTSTRAP_PATH"
echo "Executing bootstrap script..."
exec "$BOOTSTRAP_PATH"
"""
        return script

    def launch_instance(
        self,
        ami_id: str,
        instance_type: str,
        security_group_id: str,
        user_data: str,
        instance_name: str,
        key_name: Optional[str] = None,
        iam_instance_profile: Optional[str] = None,
    ) -> Optional[str]:
        """Launch EC2 instance for AC server.

        Args:
            ami_id: AMI ID to use
            instance_type: EC2 instance type
            security_group_id: Security group ID
            user_data: User data script
            instance_name: Name tag for the instance
            key_name: SSH key pair name (optional)
            iam_instance_profile: IAM instance profile name or ARN (optional)

        Returns:
            Instance ID, or None if launch failed
        """
        try:
            from typing import Any, Dict

            launch_params: Dict[str, Any] = {
                "ImageId": ami_id,
                "InstanceType": instance_type,
                "SecurityGroupIds": [security_group_id],
                "UserData": user_data,
                "MinCount": 1,
                "MaxCount": 1,
                "TagSpecifications": [
                    {
                        "ResourceType": "instance",
                        "Tags": [
                            {"Key": "Name", "Value": instance_name},
                            {"Key": "Application", "Value": "ac-server"},
                        ],
                    }
                ],
            }

            if key_name:
                launch_params["KeyName"] = key_name

            if iam_instance_profile:
                # Support both Name and Arn formats
                if iam_instance_profile.startswith("arn:aws:iam::"):
                    launch_params["IamInstanceProfile"] = {"Arn": iam_instance_profile}
                else:
                    launch_params["IamInstanceProfile"] = {"Name": iam_instance_profile}
                logger.debug(f"Using IAM instance profile: {iam_instance_profile}")

            response = self.ec2_client.run_instances(**launch_params)  # type: ignore[arg-type]
            instance_id = response["Instances"][0]["InstanceId"]
            logger.info(f"Launched instance {instance_id}")

            # Wait for instance to be running
            waiter = self.ec2_client.get_waiter("instance_running")
            waiter.wait(InstanceIds=[instance_id])
            logger.info(f"Instance {instance_id} is running")

            return instance_id
        except ClientError as e:
            logger.error(f"Error launching instance: {e}")
            return None

    def get_instance_public_ip(self, instance_id: str) -> Optional[str]:
        """Get public IP address of an instance.

        Args:
            instance_id: Instance ID

        Returns:
            Public IP address, or None if not found
        """
        try:
            response = self.ec2_client.describe_instances(InstanceIds=[instance_id])
            if not response["Reservations"]:
                return None

            instance = response["Reservations"][0]["Instances"][0]
            return instance.get("PublicIpAddress")
        except ClientError as e:
            logger.error(f"Error getting instance IP: {e}")
            return None

    def stop_instance(self, instance_id: str) -> bool:
        """Stop an EC2 instance.

        Args:
            instance_id: Instance ID

        Returns:
            True if stop succeeded, False otherwise
        """
        try:
            self.ec2_client.stop_instances(InstanceIds=[instance_id])
            logger.info(f"Stopped instance {instance_id}")
            return True
        except ClientError as e:
            logger.error(f"Error stopping instance: {e}")
            return False

    def start_instance(self, instance_id: str) -> bool:
        """Start an EC2 instance.

        Args:
            instance_id: Instance ID

        Returns:
            True if start succeeded, False otherwise
        """
        try:
            self.ec2_client.start_instances(InstanceIds=[instance_id])
            logger.info(f"Started instance {instance_id}")
            return True
        except ClientError as e:
            logger.error(f"Error starting instance: {e}")
            return False

    def terminate_instance(self, instance_id: str) -> bool:
        """Terminate an EC2 instance.

        Args:
            instance_id: Instance ID

        Returns:
            True if termination succeeded, False otherwise
        """
        try:
            self.ec2_client.terminate_instances(InstanceIds=[instance_id])
            logger.info(f"Terminated instance {instance_id}")
            return True
        except ClientError as e:
            logger.error(f"Error terminating instance: {e}")
            return False

    def terminate_instance_and_wait(self, instance_id: str, dry_run: bool = False) -> bool:
        """Terminate an EC2 instance and wait for termination to complete.

        Args:
            instance_id: Instance ID to terminate
            dry_run: If True, only log what would be done without actually terminating

        Returns:
            True if termination succeeded, False otherwise
        """
        try:
            # Check if instance exists
            try:
                response = self.ec2_client.describe_instances(InstanceIds=[instance_id])
                if not response["Reservations"]:
                    logger.warning(f"Instance {instance_id} not found")
                    return True  # Already gone

                instance_state = response["Reservations"][0]["Instances"][0]["State"]["Name"]
                if instance_state == "terminated":
                    logger.info(f"Instance {instance_id} is already terminated")
                    return True

            except ClientError as e:
                if e.response["Error"]["Code"] == "InvalidInstanceID.NotFound":
                    logger.info(f"Instance {instance_id} not found, already terminated")
                    return True
                raise

            if dry_run:
                logger.info(f"[DRY RUN] Would terminate instance: {instance_id}")
                return True

            # Terminate the instance
            logger.info(f"Terminating instance {instance_id}...")
            self.ec2_client.terminate_instances(InstanceIds=[instance_id])
            logger.info(f"Termination initiated for instance {instance_id}")

            # Wait for instance to terminate
            logger.info(f"Waiting for instance {instance_id} to terminate...")
            waiter = self.ec2_client.get_waiter("instance_terminated")
            waiter.wait(
                InstanceIds=[instance_id],
                WaiterConfig={
                    "Delay": 15,  # Check every 15 seconds
                    "MaxAttempts": 40,  # Wait up to 10 minutes
                },
            )
            logger.info(f"Instance {instance_id} has been terminated")
            return True

        except ClientError as e:
            logger.error(f"Error terminating instance {instance_id}: {e}")
            return False

    def find_instances_by_name(self, instance_name: str) -> list[str]:
        """Find instances by name tag.

        Args:
            instance_name: Instance name to search for

        Returns:
            List of instance IDs
        """
        try:
            response = self.ec2_client.describe_instances(
                Filters=[
                    {"Name": "tag:Name", "Values": [instance_name]},
                    {
                        "Name": "instance-state-name",
                        "Values": ["pending", "running", "stopping", "stopped"],
                    },
                ]
            )

            instance_ids = []
            for reservation in response["Reservations"]:
                for instance in reservation["Instances"]:
                    instance_ids.append(instance["InstanceId"])

            return instance_ids
        except ClientError as e:
            logger.error(f"Error finding instances: {e}")
            return []

    def get_instance_details(self, instance_id: str) -> Optional[dict]:
        """Get detailed information about an instance.

        Args:
            instance_id: Instance ID

        Returns:
            Dictionary with instance details, or None if not found
        """
        try:
            response = self.ec2_client.describe_instances(InstanceIds=[instance_id])
            if not response["Reservations"]:
                return None

            instance = response["Reservations"][0]["Instances"][0]

            # Extract relevant information
            details = {
                "instance_id": instance["InstanceId"],
                "state": instance["State"]["Name"],
                "instance_type": instance["InstanceType"],
                "public_ip": instance.get("PublicIpAddress"),
                "private_ip": instance.get("PrivateIpAddress"),
                "launch_time": instance["LaunchTime"],
            }

            # Extract name tag
            for tag in instance.get("Tags", []):
                if tag["Key"] == "Name":
                    details["name"] = tag["Value"]
                    break

            return details
        except ClientError as e:
            logger.error(f"Error getting instance details: {e}")
            return None


    def create_assettoserver_native_user_data_script(
        self, s3_bucket: str, s3_key: str, assettoserver_version: str = "v0.0.55-pre31"
    ) -> str:
        """Create user data script for AssettoServer native binary deployment.

        Args:
            s3_bucket: S3 bucket containing the pack file
            s3_key: S3 key of the pack file
            assettoserver_version: AssettoServer release version

        Returns:
            User data script as string
        """
        import re

        pack_id = re.sub(
            r"[^a-zA-Z0-9-_]", "_", s3_key.split("/")[-1].replace(".tar.gz", "").replace(".zip", "")
        )

        script = f"""#!/bin/bash
set -euo pipefail

# Logging setup
DEPLOY_LOG="/var/log/assettoserver-deploy.log"
STATUS_FILE="/opt/assettoserver/deploy-status.json"
exec > >(tee -a "$DEPLOY_LOG") 2>&1

log_message() {{
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1"
}}

write_status() {{
    local status=$1
    local detail=${{2:-""}}
    local timestamp=$(date -u +%Y-%m-%dT%H:%M:%SZ)
    local public_ip=$(curl -s http://169.254.169.254/latest/meta-data/public-ipv4 || echo "unknown")
    
    mkdir -p /opt/assettoserver
    cat > "$STATUS_FILE" << STATUSEOF
{{
  "status": "$status",
  "detail": "$detail",
  "timestamp": "$timestamp",
  "server_ip": "$public_ip",
  "server_port": {AC_SERVER_UDP_PORT},
  "tcp_port": {AC_SERVER_TCP_PORT},
  "http_port": {AC_SERVER_HTTP_PORT},
  "assettoserver_version": "{assettoserver_version}",
  "pack_id": "{pack_id}"
}}
STATUSEOF
}}

log_message "=== AssettoServer Native Binary Deployment Started ==="
log_message "Pack: {s3_key}"
log_message "AssettoServer Version: {assettoserver_version}"

# Install dependencies
log_message "Installing dependencies..."
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get install -y -qq ca-certificates curl awscli python3 wget tar

log_message "✓ Dependencies installed"

# Create AssettoServer directory
ASSETTOSERVER_DIR="/opt/assettoserver"
mkdir -p "$ASSETTOSERVER_DIR"
cd "$ASSETTOSERVER_DIR"

# Download server pack from S3 with retries
log_message "Downloading server pack from S3..."
MAX_RETRIES=3
RETRY_DELAY=5
for attempt in $(seq 1 $MAX_RETRIES); do
    if aws s3 cp s3://{s3_bucket}/{s3_key} ./server-pack.tar.gz; then
        log_message "✓ Download successful"
        break
    else
        if [ $attempt -eq $MAX_RETRIES ]; then
            log_message "ERROR: Failed to download pack from S3 after $MAX_RETRIES attempts"
            write_status "failed" "Failed to download pack from S3"
            exit 1
        fi
        log_message "Download attempt $attempt failed, retrying in $RETRY_DELAY seconds..."
        sleep $RETRY_DELAY
        RETRY_DELAY=$((RETRY_DELAY * 2))
    fi
done

# Download AssettoServer Linux binary
log_message "Downloading AssettoServer binary..."
BINARY_URL="https://github.com/compujuckel/AssettoServer/releases/download/{assettoserver_version}/assetto-server-linux-x64.tar.gz"
if ! wget -q "$BINARY_URL" -O assettoserver-binary.tar.gz; then
    log_message "ERROR: Failed to download AssettoServer binary from $BINARY_URL"
    write_status "failed" "Failed to download AssettoServer binary"
    exit 1
fi
log_message "✓ Binary downloaded"

# Extract AssettoServer binary
log_message "Extracting AssettoServer binary..."
tar -xzf assettoserver-binary.tar.gz
rm assettoserver-binary.tar.gz
log_message "✓ Binary extracted"

# Make AssettoServer executable
chmod +x AssettoServer
log_message "✓ AssettoServer binary is ready"

# Download and run the preparation tool
log_message "Downloading AssettoServer preparation tool..."
if ! aws s3 cp s3://{s3_bucket}/tools/assetto_server_prepare.py ./assetto_server_prepare.py; then
    log_message "ERROR: Failed to download preparation tool"
    write_status "failed" "Failed to download preparation tool"
    exit 1
fi
chmod +x ./assetto_server_prepare.py

# Prepare server data
log_message "Preparing server configuration..."
if ! python3 ./assetto_server_prepare.py ./server-pack.tar.gz "$ASSETTOSERVER_DIR"; then
    log_message "ERROR: Failed to prepare server data"
    write_status "failed" "Failed to prepare server data structure"
    exit 1
fi
log_message "✓ Server data prepared"

# Create systemd service
log_message "Creating systemd service..."
cat > /etc/systemd/system/assettoserver.service << 'EOF'
[Unit]
Description=AssettoServer
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/opt/assettoserver
ExecStart=/opt/assettoserver/AssettoServer
Restart=on-failure
RestartSec=10
StandardOutput=append:/var/log/assettoserver-stdout.log
StandardError=append:/var/log/assettoserver-stderr.log

[Install]
WantedBy=multi-user.target
EOF

log_message "✓ Systemd service created"

# Start AssettoServer
log_message "Starting AssettoServer..."
systemctl daemon-reload
systemctl enable assettoserver
systemctl start assettoserver

# Wait for server to start
log_message "Waiting for server to start..."
sleep 10

# Check if service is running
if systemctl is-active --quiet assettoserver; then
    log_message "✓ AssettoServer is running"
    write_status "started" "AssettoServer deployment successful"
    
    log_message "=== Deployment Complete ==="
    PUBLIC_IP=$(curl -s http://169.254.169.254/latest/meta-data/public-ipv4 || echo "unknown")
    log_message "Server available at $PUBLIC_IP:{AC_SERVER_UDP_PORT} (UDP)"
    log_message "HTTP interface at http://$PUBLIC_IP:{AC_SERVER_HTTP_PORT}"
    log_message "Status file: $STATUS_FILE"
else
    log_message "ERROR: AssettoServer failed to start"
    log_message "Service status:"
    systemctl status assettoserver --no-pager
    log_message "Recent logs:"
    journalctl -u assettoserver -n 50 --no-pager
    write_status "failed" "AssettoServer failed to start"
    exit 1
fi
"""
        return script
