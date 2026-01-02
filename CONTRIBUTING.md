# Contributing to Choir Backend

First off, thank you for considering contributing to Choir! 🎉

## 🚀 Quick Start for New Contributors

1. **Fork & Clone**
   ```bash
   git clone https://github.com/jonamarkin/choirbackend.git
   cd choirbackend
   ```

2. **Set up development environment**
   ```bash
   python -m venv venv
   source venv/bin/activate  # or venv\Scripts\activate on Windows
   pip install -r requirements/development.txt
   cp .env.example .env
   ```

3. **Initialize database**
   ```bash
   python manage.py migrate
   python manage.py setup_initial_data
   ```

4. **Run tests to ensure everything works**
   ```bash
   pytest
   ```

## 🎯 How Can I Contribute?

### Reporting Bugs

Before creating bug reports, please check existing issues. When creating a bug report, include:

- **Clear title and description**
- **Steps to reproduce**
- **Expected vs actual behavior**
- **Environment details** (OS, Python version, etc.)
- **Error messages/logs**

**Bug Report Template:**
```markdown
**Describe the bug**
A clear description of what the bug is.

**To Reproduce**
Steps to reproduce:
1. Go to '...'
2. Click on '...'
3. See error

**Expected behavior**
What you expected to happen.

**Screenshots/Logs**
If applicable, add screenshots or error logs.

**Environment:**
- OS: [e.g. Windows 11, macOS 14, Ubuntu 22.04]
- Python: [e.g. 3.11.5]
- Django: [e.g. 5.0.1]
```

### Suggesting Features

Feature suggestions are welcome! Please:

- **Check if it already exists** in issues
- **Describe the feature** clearly
- **Explain the use case** - why is it needed?
- **Provide examples** if possible

### Pull Requests

1. **Create an issue first** for major changes
2. **Fork the repo** and create a branch from `develop`
3. **Follow the code style** (PEP 8, Black formatting)
4. **Write tests** for new features
5. **Update documentation** as needed
6. **Ensure tests pass** before submitting

## 🏗️ Development Workflow

### Branch Naming

- `feature/description` - New features
- `bugfix/description` - Bug fixes
- `hotfix/description` - Urgent fixes
- `docs/description` - Documentation updates
- `refactor/description` - Code refactoring

Examples:
- `feature/member-bulk-import`
- `bugfix/attendance-date-filter`
- `docs/api-authentication`

### Commit Messages

Use conventional commits format:

```
<type>: <description>

[optional body]
[optional footer]
```

**Types:**
- `Add:` New feature or functionality
- `Fix:` Bug fix
- `Update:` Changes to existing functionality
- `Refactor:` Code refactoring
- `Docs:` Documentation changes
- `Test:` Adding or updating tests
- `Chore:` Maintenance tasks

**Examples:**
```bash
Add: member bulk import endpoint
Fix: attendance date filtering returns wrong results
Update: change subscription fee validation
Docs: add API authentication examples
Test: add unit tests for member serializer
```

### Code Style Guidelines

#### Python/Django

```python
# Good: Clear, documented, follows PEP 8
class Member(TenantAwareModel, TimestampedModel):
    """
    Represents a choir member.
    
    Attributes:
        full_name: Member's full legal name
        voice_part: Member's voice classification (soprano, alto, etc.)
    """
    full_name = models.CharField(max_length=255)
    voice_part = models.CharField(max_length=50, choices=VOICE_PART_CHOICES)
    
    def get_active_subscription(self):
        """Get member's current active subscription."""
        return self.subscriptions.filter(
            period__is_active=True,
            status='active'
        ).first()
```

**Style Rules:**
- Use 4 spaces for indentation
- Maximum line length: 88 characters (Black default)
- Use docstrings for classes and functions
- Use type hints where appropriate
- Use meaningful variable names

#### Serializers

```python
# Good: Clear field definitions, proper validation
class MemberSerializer(serializers.ModelSerializer):
    """Serializer for Member model."""
    organization_name = serializers.CharField(
        source='organization.name', 
        read_only=True
    )
    current_subscription = SubscriptionSerializer(
        source='get_current_subscription', 
        read_only=True
    )
    
    class Meta:
        model = Member
        fields = [
            'id', 'full_name', 'email', 'phone_number',
            'voice_part', 'organization_name', 'current_subscription'
        ]
        read_only_fields = ['id', 'organization']
    
    def validate_phone_number(self, value):
        """Ensure phone number is in correct format."""
        if not value.startswith('+'):
            raise serializers.ValidationError(
                "Phone number must start with country code"
            )
        return value
```

#### Views

```python
# Good: Clear, documented, handles errors
@api_view(['GET', 'POST'])
def member_list(request):
    """
    List all members or create a new member.
    
    GET: Returns paginated list of members
    POST: Creates a new member
    """
    if request.method == 'GET':
        members = Member.objects.filter(
            organization=request.user.organization,
            deleted_at__isnull=True
        )
        serializer = MemberSerializer(members, many=True)
        return Response(serializer.data)
    
    elif request.method == 'POST':
        serializer = MemberSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save(
                organization=request.user.organization,
                created_by=request.user
            )
            return Response(
                serializer.data, 
                status=status.HTTP_201_CREATED
            )
        return Response(
            serializer.errors, 
            status=status.HTTP_400_BAD_REQUEST
        )
```

### Testing

**Always write tests for:**
- New features
- Bug fixes
- Edge cases

**Test Structure:**

```python
# apps/members/tests/test_models.py
import pytest
from members import Member
from core.models import Organization


@pytest.mark.django_db
class TestMemberModel:
   """Test suite for Member model."""

   def test_create_member(self):
      """Test creating a member successfully."""
      org = Organization.objects.create(
         name="Test Choir",
         slug="test-choir"
      )
      member = Member.objects.create(
         organization=org,
         full_name="John Doe",
         voice_part="tenor"
      )
      assert member.full_name == "John Doe"
      assert member.organization == org

   def test_member_str_representation(self):
      """Test string representation of member."""
      # Test implementation
      pass
```

**Running Tests:**
```bash
# All tests
pytest

# Specific app
pytest apps/members/

# With coverage
pytest --cov=apps --cov-report=html

# Verbose output
pytest -v
```

## 📁 Project Structure

When adding new functionality, follow this structure:

```
apps/your_module/
├── __init__.py
├── models.py          # Database models
├── serializers.py     # DRF serializers
├── views.py           # API views
├── urls.py            # URL routing
├── filters.py         # Django-filter classes (if needed)
├── services.py        # Business logic (complex operations)
├── permissions.py     # Custom permissions (if needed)
├── admin.py           # Django admin config
└── tests/
    ├── __init__.py
    ├── test_models.py
    ├── test_views.py
    ├── test_serializers.py
    └── factories.py   # Factory Boy factories
```

## 🔍 Code Review Process

### For Reviewers

When reviewing PRs, check for:

- [ ] Code follows style guidelines
- [ ] Tests are included and pass
- [ ] Documentation is updated
- [ ] No security vulnerabilities
- [ ] Performance considerations
- [ ] Backwards compatibility
- [ ] Edge cases are handled

### For Contributors

Before requesting review:

- [ ] All tests pass locally
- [ ] Code is formatted with Black
- [ ] No linting errors (flake8)
- [ ] Documentation is updated
- [ ] Commit messages follow conventions
- [ ] PR description is clear

## 📝 Documentation Standards

### Code Documentation

```python
def complex_function(param1: str, param2: int) -> dict:
    """
    Brief description of what the function does.
    
    Longer description if needed, explaining the logic,
    edge cases, or important implementation details.
    
    Args:
        param1: Description of first parameter
        param2: Description of second parameter
    
    Returns:
        Dictionary containing:
            - key1: Description
            - key2: Description
    
    Raises:
        ValueError: When param2 is negative
        
    Example:
        >>> complex_function("test", 5)
        {'result': 'success'}
    """
    # Implementation
    pass
```

### API Documentation

Document endpoints with docstrings:

```python
@api_view(['POST'])
def create_member(request):
    """
    Create a new member.
    
    **Endpoint:** `POST /api/v1/members/`
    
    **Permissions:** Requires authentication, Admin or Super Admin role
    
    **Request Body:**
    ```json
    {
        "full_name": "John Doe",
        "email": "john@example.com",
        "phone_number": "+233244123456",
        "voice_part": "tenor"
    }
    ```
    
    **Response:** `201 CREATED`
    ```json
    {
        "id": "uuid",
        "full_name": "John Doe",
        "email": "john@example.com",
        "created_at": "2024-01-01T00:00:00Z"
    }
    ```
    
    **Errors:**
    - `400 BAD REQUEST`: Invalid data
    - `401 UNAUTHORIZED`: Not authenticated
    - `403 FORBIDDEN`: Insufficient permissions
    """
    # Implementation
    pass
```

## 🚀 Release Process

1. **Version bumping** (semantic versioning)
   - MAJOR: Breaking changes
   - MINOR: New features (backwards compatible)
   - PATCH: Bug fixes

2. **Update CHANGELOG.md**

3. **Tag the release**
   ```bash
   git tag -a v1.0.0 -m "Release version 1.0.0"
   git push origin v1.0.0
   ```

## 🤔 Questions?

- Open a discussion on GitHub
- Join our Discord/Slack (if available)
- Email: dev@vocalessence.com

## 📜 Code of Conduct

- Be respectful and inclusive
- Provide constructive feedback
- Focus on what's best for the project
- Show empathy towards other contributors

---

Thank you for contributing to Choir Backend! 🎵