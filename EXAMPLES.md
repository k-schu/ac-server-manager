# AC Server Manager Examples

This document provides practical examples for using AC Server Manager.

## Quick Start Example

### 1. Install with UV

```bash
# Install UV
curl -LsSf https://astral.sh/uv/install.sh | sh

# Clone and install
git clone https://github.com/k-schu/ac-server-manager-1.git
cd ac-server-manager-1
uv venv
source .venv/bin/activate
uv pip install -e .
```

### 2. Configure AWS Credentials

Create or edit `~/.aws/credentials`:

```ini
[default]
aws_access_key_id = YOUR_ACCESS_KEY
aws_secret_access_key = YOUR_SECRET_KEY
region = us-east-1
```

### 3. Create Server Pack in Content Manager

1. Open Assetto Corsa Content Manager
2. Go to Server tab
3. Configure your race settings (track, cars, etc.)
4. Click "Pack" → "Create server package"
5. Save as `my-server.tar.gz`

### 4. Deploy Your Server

```bash
# Deploy with defaults (t3.small in us-east-1)
ac-server-manager deploy my-server.tar.gz

# Deploy with SSH access
ac-server-manager deploy my-server.tar.gz --key-name my-ssh-key

# Deploy in different region
ac-server-manager deploy my-server.tar.gz --region eu-west-1
```

Output:
```
Deploying AC server from my-server.tar.gz...
✓ Deployment successful!

Instance ID: i-0123456789abcdef0
Server will be available at 54.123.45.67:9600 (UDP/TCP)
Note: Server initialization may take a few minutes
```

## Common Usage Patterns

### Weekend Racing Server

Deploy Friday evening, terminate Sunday night:

```bash
# Friday evening
ac-server-manager deploy weekend-race.tar.gz

# Sunday night
ac-server-manager terminate
```

**Monthly cost**: ~$2 (48 hours at $0.0208/hour)

### Cost-Optimized Testing Server

Stop when not in use:

```bash
# Deploy once
ac-server-manager deploy test-server.tar.gz

# Stop when done testing
ac-server-manager stop

# Start when needed again
ac-server-manager start
```

**Monthly cost**: Pay only for runtime hours + ~$0.01 S3 storage

### League Season Server

Run 24/7 for the season:

```bash
# Deploy at season start
ac-server-manager deploy league-season-1.tar.gz

# Update track/config as needed
ac-server-manager redeploy league-season-1-updated.tar.gz

# Terminate at season end
ac-server-manager terminate
```

**Monthly cost**: ~$15 (t3.small 24/7)

## Advanced Examples

### Multi-Region Deployment

```bash
# EU server
ac-server-manager deploy eu-server.tar.gz \
  --region eu-west-1 \
  --instance-name ac-server-eu \
  --bucket ac-servers-eu

# US server
ac-server-manager deploy us-server.tar.gz \
  --region us-east-1 \
  --instance-name ac-server-us \
  --bucket ac-servers-us
```

### Larger Server (8-16 players)

```bash
ac-server-manager deploy large-server.tar.gz \
  --instance-type t3.medium
```

**Cost**: ~$30/month for 24/7 operation

### Automated Deployment Script

Create `deploy.sh`:

```bash
#!/bin/bash
set -e

SERVER_PACK="$1"
REGION="${2:-us-east-1}"

echo "Deploying AC server from $SERVER_PACK in $REGION"

ac-server-manager deploy "$SERVER_PACK" \
  --region "$REGION" \
  --instance-type t3.small \
  --bucket "ac-servers-$(date +%Y%m)" \
  --instance-name "ac-server-$(date +%Y%m%d)" \
  --key-name my-key

echo "Deployment complete!"
```

Usage:
```bash
chmod +x deploy.sh
./deploy.sh my-server.tar.gz us-west-2
```

## Connecting from Content Manager

### Method 1: LAN Tab

1. Open Content Manager
2. Go to **Online** → **LAN**
3. Your server should appear automatically if on the same network/region

### Method 2: Direct Connect

1. Note the IP address from deployment output
2. Open Content Manager
3. Go to **Online** → **Direct Connect**
4. Enter: `<IP_ADDRESS>:9600`
5. Click **Connect**

### Method 3: Bookmarks

1. Connect once using Method 2
2. Add server to favorites
3. Access from **Online** → **Bookmarks**

## Monitoring and Troubleshooting

### Check Server Status

```bash
# Via AWS CLI (if installed)
aws ec2 describe-instances \
  --filters "Name=tag:Name,Values=ac-server-instance" \
  --query 'Reservations[*].Instances[*].[InstanceId,State.Name,PublicIpAddress]' \
  --output table
```

### SSH into Server

```bash
# Get the public IP from deployment output
ssh -i ~/.ssh/my-key.pem ubuntu@<PUBLIC_IP>

# Check server logs
sudo journalctl -u acserver -f

# Check if server is running
sudo systemctl status acserver
```

### View Server Files

```bash
# After SSH'ing in
cd /opt/acserver
ls -la

# View configuration
cat cfg/server_cfg.ini

# View server log
cat log/server.log
```

## Cost Calculation Examples

### Scenario 1: Weekend Warrior (8 hours/week)

- Instance: t3.small
- Usage: 8 hours/week × 4 weeks = 32 hours/month
- Cost: 32 hours × $0.0208 = **$0.67/month**
- S3: ~$0.01/month
- **Total: ~$0.68/month**

### Scenario 2: Active League (24/7 for 3 months)

- Instance: t3.small
- Usage: 24/7 × 3 months
- Cost: 720 hours × 3 × $0.0208 = **$44.93 for 3 months**
- S3: ~$0.03
- **Total: ~$45/season**

### Scenario 3: Large Events (t3.medium for special races)

- Instance: t3.medium
- Usage: 4 hours/week × 4 weeks = 16 hours/month
- Cost: 16 hours × $0.0416 = **$0.67/month**
- **Total: Similar to Scenario 1 but better performance**

## Best Practices

1. **Always use specific instance names** for multiple servers
2. **Stop instances when not in use** to save costs
3. **Use SSH keys** for secure access
4. **Keep server packs organized** with descriptive names
5. **Test configurations locally** before deploying
6. **Monitor AWS costs** using AWS Cost Explorer
7. **Set up billing alerts** in AWS
8. **Use consistent region** for your player base location
9. **Backup important server configurations**
10. **Document your server settings**

## Troubleshooting Common Issues

### "Server not visible in Content Manager"

- Wait 2-3 minutes after deployment
- Check security group allows ports 9600 (UDP/TCP)
- Verify instance is running
- Try direct connect with IP:PORT

### "Deployment failed"

- Check AWS credentials are valid
- Verify IAM permissions are correct
- Check AWS service quotas/limits
- Ensure pack file is valid tar.gz

### "High AWS bills"

- List running instances: `aws ec2 describe-instances`
- Stop unused instances: `ac-server-manager stop`
- Terminate old instances: `ac-server-manager terminate`
- Clean up old S3 packs

### "Can't SSH into instance"

- Verify key-name was specified during deployment
- Check security group allows port 22
- Ensure you're using correct username (ubuntu)
- Verify key file permissions: `chmod 400 ~/.ssh/my-key.pem`

## Additional Resources

- [AWS EC2 Pricing](https://aws.amazon.com/ec2/pricing/on-demand/)
- [Assetto Corsa Content Manager](https://assettocorsa.club/content-manager.html)
- [AWS Free Tier](https://aws.amazon.com/free/) (750 hours/month of t2.micro for 12 months)
- [UV Documentation](https://github.com/astral-sh/uv)
