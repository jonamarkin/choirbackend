# Changelog

## [Unreleased] - 2026-01-23

### Added

#### Organization Management
- **Organization invite codes**: Added 4-digit unique organization codes for user onboarding
  - New `code` field on `Organization` model with auto-generation via `generate_organization_code()`
  - Users can now join organizations using invite codes during registration or via dedicated endpoint
- **Organization API endpoints** (`/api/v1/core/organizations/`):
  - `GET /` - List all organizations (system admin only)
  - `GET /{id}` - Retrieve organization details (system admin only)
  - `POST /` - Create new organization with auto-generated code (system admin only)
  - `PUT /{id}` - Update organization (system admin only)
  - `GET /{id}/members` - List organization members
  - `POST /{id}/add_member` - Add user to organization by email
  - `POST /{id}/remove_member` - Remove user from organization
- **Join organization endpoint** (`POST /api/v1/auth/join-organization/`): Allows authenticated users to join an organization using a 4-digit code

#### New Serializers
- `OrganizationSerializer` - Full organization details with nested members
- `CreateOrganizationSerializer` - For organization creation with auto-generated code
- `AddOrganizationMemberSerializer` - For add/remove member operations
- `JoinOrganizationSerializer` - For join organization requests
- `OrganizationUserSerializer` - Lightweight user representation for organization contexts

### Changed

#### Code Structure Refactoring
- **Authentication module restructured**:
  - `authentication/views.py` → `authentication/views/auth_views.py`
  - `authentication/serializers.py` → `authentication/serializers/user_serializers.py`
  - Added `__init__.py` files for proper package structure
- **Core module restructured**:
  - Added `core/views/` package with `organization_views.py`
  - Added `core/serializers/` package with `organization_serializers.py`
  - Added `core/urls.py` for organization routes

#### Role System Improvements
- **Removed `system_admin` role** from `User.ROLE_CHOICES` - platform-level admin now uses Django's built-in `is_superuser`
- **Updated `is_system_admin()`** method to return `self.is_superuser` instead of checking role
- **Enhanced role check methods** (`is_super_admin()`, `is_finance_admin()`, `is_attendance_officer()`, `is_treasurer()`) to also grant access to superusers
- Updated subscription assignees filter to remove `system_admin` from executives list

#### Registration Flow
- Organization code field in `RegisterSerializer` changed from `required=False` to `required=True`
- Registration now looks up organization by `code` field instead of `slug`

#### API Documentation (OpenAPI/Swagger)
- Added `@extend_schema(tags=[...])` decorators to all viewsets for better API grouping:
  - `Authentication` tag for auth endpoints
  - `Social Login` tag for OAuth endpoints
  - `Organization` tag for organization management
  - `Payments` tag for payment endpoints
  - `Subscriptions` tag for subscription endpoints
- Removed redundant per-method `tags` parameters (now using class-level tags)
- Added `persistAuthorization: True` to Swagger UI settings for better developer experience

#### Settings Updates
- Updated serializer paths in `REST_AUTH` settings to reflect new module structure:
  - `authentication.serializers.UserSerializer` → `authentication.serializers.user_serializers.UserSerializer`
  - `authentication.serializers.RegisterSerializer` → `authentication.serializers.user_serializers.RegisterSerializer`
- Removed unused `import os` from base settings
- Removed unused `import base64` from base settings
- Cleaned up comment formatting in `HUBTEL_CONFIG`

### Fixed
- Fixed indentation issues in `AuthViewSet.login()` method for inactive account responses
- Fixed import statements to use absolute imports for better clarity

### Database Migrations Required
- `authentication/migrations/0004_alter_user_role.py` - Updates role choices
- `core/migrations/0002_organization_code.py` - Adds code field to Organization
- `core/migrations/0003_alter_organization_code.py` - Makes code field required and unique
