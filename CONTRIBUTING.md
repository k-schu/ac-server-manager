# Contributing to AC Server Manager

Thank you for your interest in contributing to AC Server Manager! This document provides guidelines and instructions for contributing.

## Development Setup

### Prerequisites

- Python 3.9 or higher
- [UV](https://github.com/astral-sh/uv) (recommended) or pip
- Git
- AWS account for testing (optional but recommended)

### Setting Up Development Environment with UV

1. **Install UV**:
   ```bash
   curl -LsSf https://astral.sh/uv/install.sh | sh
   ```

2. **Clone the repository**:
   ```bash
   git clone https://github.com/k-schu/ac-server-manager-1.git
   cd ac-server-manager-1
   ```

3. **Create virtual environment and install dependencies**:
   ```bash
   uv venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   uv pip install -e ".[dev]"
   ```

### Setting Up with pip

```bash
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
pip install -e ".[dev]"
```

## Development Workflow

### 1. Create a Branch

```bash
git checkout -b feature/your-feature-name
```

### 2. Make Your Changes

Follow the code style and structure of the existing codebase:

- Use type hints for all functions
- Add docstrings to all public functions and classes
- Follow PEP 8 style guidelines
- Keep functions focused and single-purpose

### 3. Write Tests

Add tests for any new functionality in the `tests/` directory:

```python
def test_your_new_feature() -> None:
    """Test description."""
    # Arrange
    # Act
    # Assert
```

### 4. Run Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=ac_server_manager --cov-report=html

# Run specific test file
pytest tests/test_deployer.py

# Run specific test
pytest tests/test_deployer.py::test_deploy_success
```

### 5. Format and Lint Code

```bash
# Format with black
black src/ tests/

# Lint with ruff
ruff check src/ tests/

# Auto-fix linting issues
ruff check src/ tests/ --fix

# Type check with mypy
mypy src/ac_server_manager
```

### 6. Run All Quality Checks

```bash
# All-in-one check script
./scripts/check.sh  # If available, or run individually:

black src/ tests/
ruff check src/ tests/ --fix
mypy src/ac_server_manager
pytest --cov
```

### 7. Commit Your Changes

Use descriptive commit messages:

```bash
git add .
git commit -m "Add feature: description of what you added"
```

Good commit message examples:
- "Add support for custom security group configuration"
- "Fix instance termination bug when no instances exist"
- "Improve error handling in S3 upload"
- "Update documentation for redeploy command"

### 8. Push and Create Pull Request

```bash
git push origin feature/your-feature-name
```

Then create a pull request on GitHub with:
- Clear description of changes
- Reference to any related issues
- Screenshots if UI changes (though this is CLI-only)

## Code Style Guidelines

### Python Style

- Follow PEP 8
- Use type hints for all function signatures
- Maximum line length: 100 characters (configured in pyproject.toml)
- Use descriptive variable names
- Prefer explicit over implicit

### Example Function

```python
def create_security_group(self, group_name: str, description: str) -> Optional[str]:
    """Create security group with rules for AC server.
    
    Args:
        group_name: Name of the security group
        description: Description of the security group
        
    Returns:
        Security group ID, or None if creation failed
    """
    try:
        # Implementation
        return group_id
    except ClientError as e:
        logger.error(f"Error creating security group: {e}")
        return None
```

### Docstring Style

Use Google-style docstrings:

```python
def function_name(arg1: str, arg2: int) -> bool:
    """Short description.
    
    Longer description if needed.
    
    Args:
        arg1: Description of arg1
        arg2: Description of arg2
        
    Returns:
        Description of return value
        
    Raises:
        ValueError: When something goes wrong
    """
```

## Testing Guidelines

### Test Structure

- One test file per module (e.g., `test_deployer.py` for `deployer.py`)
- Use descriptive test names: `test_deploy_success`, `test_deploy_fails_when_bucket_creation_fails`
- Use pytest fixtures for common setup
- Mock external dependencies (AWS services)

### Test Coverage

- Aim for >80% code coverage
- Test happy paths and error cases
- Test edge cases and boundary conditions

### Example Test

```python
def test_deploy_success(deployer: Deployer, tmp_path: Path) -> None:
    """Test successful deployment."""
    pack_file = tmp_path / "test-pack.tar.gz"
    pack_file.write_text("test content")
    
    # Mock dependencies
    deployer.s3_manager.create_bucket = MagicMock(return_value=True)
    deployer.s3_manager.upload_pack = MagicMock(return_value="packs/test.tar.gz")
    deployer.ec2_manager.launch_instance = MagicMock(return_value="i-12345")
    
    # Act
    result = deployer.deploy(pack_file)
    
    # Assert
    assert result == "i-12345"
    deployer.s3_manager.create_bucket.assert_called_once()
```

## Project Structure

```
ac-server-manager-1/
├── src/
│   └── ac_server_manager/
│       ├── __init__.py       # Package initialization
│       ├── cli.py            # CLI interface (Click commands)
│       ├── config.py         # Configuration dataclasses
│       ├── deployer.py       # Main deployment orchestration
│       ├── ec2_manager.py    # EC2 operations
│       └── s3_manager.py     # S3 operations
├── tests/
│   ├── __init__.py
│   ├── test_cli.py           # CLI tests (add if needed)
│   ├── test_config.py        # Config tests
│   ├── test_deployer.py      # Deployer tests
│   ├── test_ec2_manager.py   # EC2 manager tests
│   └── test_s3_manager.py    # S3 manager tests
├── pyproject.toml            # Project configuration
├── requirements.txt          # Core dependencies
├── README.md                 # Main documentation
├── EXAMPLES.md              # Usage examples
└── CONTRIBUTING.md          # This file
```

## Adding New Features

### Example: Adding a New CLI Command

1. **Add the command in `cli.py`**:
   ```python
   @main.command()
   @click.option("--instance-id", help="Instance ID")
   def restart(instance_id: Optional[str]) -> None:
       """Restart an AC server instance."""
       # Implementation
   ```

2. **Add method in `deployer.py`**:
   ```python
   def restart(self, instance_id: Optional[str] = None) -> bool:
       """Restart AC server instance."""
       if self.stop(instance_id):
           return self.start(instance_id)
       return False
   ```

3. **Add tests in `tests/test_deployer.py`**:
   ```python
   def test_restart_success(deployer: Deployer) -> None:
       """Test successful restart."""
       deployer.stop = MagicMock(return_value=True)
       deployer.start = MagicMock(return_value=True)
       
       result = deployer.restart("i-12345")
       
       assert result is True
       deployer.stop.assert_called_once_with("i-12345")
       deployer.start.assert_called_once_with("i-12345")
   ```

4. **Update documentation in README.md**

## Common Issues

### Import Errors

If you see import errors, ensure you've installed the package in editable mode:
```bash
uv pip install -e ".[dev]"
```

### AWS Permission Errors

When testing with real AWS:
- Use a separate AWS account or IAM user for development
- Never commit AWS credentials
- Use environment variables or AWS CLI configuration

### Test Failures

- Check that mocks are set up correctly
- Verify test isolation (tests shouldn't depend on each other)
- Run tests individually to identify specific failures

## Documentation

When adding features, update:
- **README.md**: For user-facing features
- **EXAMPLES.md**: For usage examples
- **Docstrings**: For code documentation
- **Type hints**: For better IDE support

## Questions?

- Open an issue for bug reports
- Open a discussion for feature requests
- Check existing issues before creating new ones

## Code of Conduct

- Be respectful and constructive
- Welcome newcomers
- Focus on the best solution for users
- Give credit where due

## License

By contributing, you agree that your contributions will be licensed under the same license as the project.
