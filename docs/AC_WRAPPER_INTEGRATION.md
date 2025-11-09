# AC Server Wrapper Integration

This document describes how ac-server-manager integrates with [ac-server-wrapper](https://github.com/gro-ove/ac-server-wrapper) to enable Content Manager-compatible car pack downloads directly from your deployed server.

## Overview

When you deploy an Assetto Corsa server using ac-server-manager with the `--create-iam` flag, the deployment automatically:

1. Installs and configures ac-server-wrapper
2. Creates a systemd service to run the wrapper
3. Opens the necessary firewall port (default: 8082)
4. Serves car packs from the `cm_content` directory

This allows Content Manager clients to download car packs directly from your server without visiting external links.

## How It Works

### Deployment Flow

When you run `ac-server-manager deploy /path/to/preset.tar.gz --create-iam`, the system:

1. Uploads the preset pack to S3 (existing behavior)
2. Creates an IAM instance profile for S3 access (existing behavior)
3. Launches an EC2 instance with a user-data script that:
   - Downloads and extracts the preset pack to `/opt/acserver`
   - Installs Node.js (required for the wrapper)
   - Checks if ac-server-wrapper is included in the preset
   - If not included, downloads ac-server-wrapper from GitHub
   - Installs wrapper dependencies via `npm ci`
   - Creates a systemd service for the wrapper
   - Starts both acServer and ac-server-wrapper services
4. Configures the security group to allow traffic on the wrapper port (default: 8082)

### Directory Structure

After deployment, your server will have this structure:

```
/opt/acserver/
├── acServer                    # The AC server binary
├── cfg/                        # Server configuration files
├── content/                    # Server content (tracks, cars, etc.)
├── preset/                     # Preset directory for wrapper
│   ├── cfg/                   # Configuration files
│   ├── cm_content/            # Content Manager downloadable packs
│   │   ├── cars/              # Car pack zip files
│   │   └── content.json       # Manifest for Content Manager
│   └── ...
└── wrapper/                    # AC server wrapper installation
    ├── ac-server-wrapper.js   # Wrapper application
    ├── package.json           # Node.js dependencies
    └── node_modules/          # Installed dependencies
```

## Configuration

### Wrapper Port

The wrapper listens on port 8082 by default. You can customize this in your server configuration:

```python
from ac_server_manager.config import ServerConfig

config = ServerConfig(
    wrapper_port=8082,  # Custom wrapper port
    # ... other configuration options
)
```

### Wrapper User

The wrapper runs as the `root` user by default (same as acServer). This is configured in the systemd service.

## Creating Content Manager Packs

Use the included `generate_cm_pack.py` script to create Content Manager-compatible car packs:

### Single Car Pack

```bash
python scripts/generate_cm_pack.py /path/to/cars/ks_audi_r8_lms \
    --output ./cm_content/cars
```

### Multiple Car Packs (Batch Mode)

```bash
python scripts/generate_cm_pack.py /path/to/cars \
    --batch \
    --output ./cm_content/cars \
    --content-json ./cm_content/content.json
```

This will:
1. Create a zip file for each car in the `cm_content/cars` directory
2. Generate a `content.json` manifest that lists all available packs
3. Use relative URLs like `/cm_content/cars/car_name.zip` (served by the wrapper)

### Content JSON Format

The generated `content.json` has this structure:

```json
{
  "version": "1.0",
  "content": [
    {
      "id": "ks_audi_r8_lms",
      "name": "Audi R8 LMS",
      "brand": "Audi",
      "description": "GT3 race car",
      "url": "/cm_content/cars/ks_audi_r8_lms.zip",
      "size": 45823491,
      "type": "car"
    }
  ]
}
```

## Packaging Your Preset

To include car packs in your server preset:

1. Create car packs using `generate_cm_pack.py`
2. Ensure your preset has this structure:

```
preset/
├── cfg/
│   ├── server_cfg.ini
│   └── ...
├── cm_content/
│   ├── cars/
│   │   ├── car1.zip
│   │   ├── car2.zip
│   │   └── ...
│   └── content.json
└── content/
    ├── cars/
    ├── tracks/
    └── ...
```

3. Package as a tarball:

```bash
cd /path/to/preset
tar -czf ../my-preset.tar.gz .
```

4. Deploy with ac-server-manager:

```bash
ac-server-manager deploy my-preset.tar.gz --create-iam
```

## Including Wrapper in Your Preset

You can include ac-server-wrapper directly in your preset to use a specific version:

### Option 1: Include as a Subdirectory

```
preset/
├── ac-server-wrapper/
│   ├── ac-server-wrapper.js
│   ├── package.json
│   └── ...
└── ...
```

### Option 2: Include as Root Files

```
preset/
├── ac-server-wrapper.js
├── package.json
└── ...
```

The deployment script will automatically detect and use the included wrapper.

## Verification

After deployment, you can verify the wrapper is running:

### SSH to the Instance

```bash
ssh -i <key>.pem ubuntu@<instance-ip>
```

### Check Service Status

```bash
# Check acServer status
sudo systemctl status acserver

# Check wrapper status
sudo systemctl status acserver-wrapper

# View wrapper logs
sudo journalctl -u acserver-wrapper -n 50 --no-pager
```

### Check Deployment Status

```bash
# View deployment status JSON
cat /opt/acserver/deploy-status.json

# View deployment logs
cat /var/log/acserver-deploy.log
```

### Test Wrapper Endpoint

From your local machine:

```bash
# Check if wrapper is responding
curl http://<instance-ip>:8082/cm_content/content.json

# Should return the content.json manifest
```

## Troubleshooting

### Wrapper Not Starting

1. Check the wrapper service status:
   ```bash
   sudo systemctl status acserver-wrapper
   ```

2. Check wrapper logs:
   ```bash
   sudo journalctl -u acserver-wrapper -n 100
   ```

3. Verify Node.js is installed:
   ```bash
   node --version
   ```

4. Check if the wrapper directory exists:
   ```bash
   ls -la /opt/acserver/wrapper
   ```

### Port Not Open

1. Verify security group includes wrapper port:
   ```bash
   # From AWS Console: EC2 > Security Groups > Your SG > Inbound rules
   ```

2. Check if wrapper is listening on the port:
   ```bash
   sudo ss -tlnp | grep 8082
   ```

### Content Not Loading in Content Manager

1. Verify content.json is accessible:
   ```bash
   curl http://<instance-ip>:8082/cm_content/content.json
   ```

2. Check that car zip files exist:
   ```bash
   ls -la /opt/acserver/preset/cm_content/cars/
   ```

3. Ensure URLs in content.json use relative paths (not absolute URLs with IPs)

## Server Configuration

### server_cfg.ini

Ensure your `server_cfg.ini` has the `DOWNLOAD_URL` set for in-game content streaming:

```ini
[SERVER]
NAME=My AC Server
HTTP_PORT=8081
...

[CONTENT]
DOWNLOAD_URL=http://<your-cdn-or-s3-url>
```

Note: The wrapper serves Content Manager downloads via HTTP on the wrapper port. The `DOWNLOAD_URL` is still used by the in-game client for streaming game content.

### cm_wrapper_params.json (Optional)

You can optionally include a `cm_wrapper_params.json` file in your preset to configure wrapper behavior:

```json
{
  "port": 8082,
  "contentPath": "/opt/acserver/preset/cm_content"
}
```

## Security Considerations

- The wrapper port (8082) is opened to `0.0.0.0/0` by default
- Consider restricting the security group to specific IP ranges if needed
- The wrapper runs as root to match acServer permissions
- All files are served read-only via HTTP

## References

- [ac-server-wrapper GitHub](https://github.com/gro-ove/ac-server-wrapper)
- [Content Manager](https://assettocorsa.club/content-manager.html)
- [Assetto Corsa Dedicated Server Guide](https://support.assettocorsa.net/solution/articles/16000066760-setting-up-a-dedicated-server)
