from pydantic import BaseModel, Field, field_validator, ValidationInfo
from typing import List, Dict, Optional, Any, Literal

# --- STAGE 1: INTENT SCHEMA ---
class IntentExtraction(BaseModel):
    core_purpose: str = Field(..., description="The main goal or purpose of the application.")
    target_audience: str = Field(..., description="Who will use this application.")
    key_features: List[str] = Field(..., description="List of the main features derived from the prompt.")
    is_vague: bool = Field(..., description="True if the prompt lacks enough detail to confidently build an app.")
    clarification_questions: Optional[List[str]] = Field(None, description="Questions to ask the user if is_vague is true.")
    assumptions_made: Optional[List[str]] = Field(None, description="Assumptions made by the system to fill in missing details.")

# --- STAGE 2: SYSTEM DESIGN SCHEMA ---
class Role(BaseModel):
    name: str = Field(..., description="Name of the user role, e.g., 'admin', 'user'.")
    description: str = Field(..., description="What this role can do.")

class Entity(BaseModel):
    name: str = Field(..., description="Name of the main data entity (e.g., 'User', 'Product').")
    description: str = Field(..., description="What this entity represents.")
    relationships: List[str] = Field(..., description="Relationships to other entities.")

class SystemDesign(BaseModel):
    architecture_overview: str = Field(..., description="High level description of the system architecture.")
    external_integrations: List[str] = Field(default=[], description="List of third-party services or APIs used (e.g., Stripe, SendGrid).")
    roles: List[Role] = Field(..., description="All user roles in the system.")
    entities: List[Entity] = Field(..., description="Key data entities in the system.")
    user_flows: List[str] = Field(..., description="Main user workflows.")

# --- STAGE 3: DETAILED CONFIGURATION SCHEMAS ---

# 1. Database Schema
class DBField(BaseModel):
    name: str = Field(..., description="Name of the column.")
    type: Literal["string", "integer", "float", "boolean", "datetime", "uuid", "relation"] = Field(..., description="Data type of the column.")
    is_primary_key: bool = Field(default=False)
    is_required: bool = Field(default=True)
    references_table: Optional[str] = Field(None, description="If type is relation, the name of the table it references.")

class DBTable(BaseModel):
    name: str = Field(..., description="Name of the database table. Must be plural.")
    fields: List[DBField] = Field(..., description="Columns in the table.")

class DatabaseSchema(BaseModel):
    tables: List[DBTable] = Field(..., description="All database tables.")

# 2. API Schema
class APIEndpoint(BaseModel):
    path: str = Field(..., description="The endpoint path, e.g., '/api/users'.")
    method: Literal["GET", "POST", "PUT", "DELETE", "PATCH"] = Field(..., description="HTTP method.")
    description: str = Field(..., description="What this endpoint does.")
    request_body_schema: Optional[Dict[str, Any]] = Field(None, description="JSON schema for the request body, if any.")
    response_schema: Dict[str, Any] = Field(..., description="JSON schema for a successful response.")
    interacts_with_tables: List[str] = Field(..., description="List of DB tables this endpoint reads/writes.")
    external_services_called: List[str] = Field(default=[], description="External APIs called by this endpoint (e.g., Stripe, AWS).")

class APISchema(BaseModel):
    endpoints: List[APIEndpoint] = Field(..., description="All API endpoints.")

# 3. UI Schema
class UIComponent(BaseModel):
    type: str = Field(..., description="Component type, e.g., 'table', 'form', 'chart', 'list'.")
    name: str = Field(..., description="Component name.")
    api_calls: List[str] = Field(default=[], description="List of API paths this component calls (e.g., 'GET /api/users').")
    description: str = Field(..., description="What the component displays or does.")

class UIPage(BaseModel):
    path: str = Field(..., description="Route path, e.g., '/dashboard'.")
    name: str = Field(..., description="Page name.")
    components: List[UIComponent] = Field(..., description="Components on this page.")
    requires_auth: bool = Field(default=True)
    allowed_roles: List[str] = Field(..., description="Roles allowed to access this page.")

class UISchema(BaseModel):
    pages: List[UIPage] = Field(..., description="All UI pages.")

# 4. Auth Schema
class AuthRule(BaseModel):
    role: str = Field(..., description="Role name.")
    allowed_endpoints: List[str] = Field(..., description="List of API paths + methods this role can access, e.g., 'POST /api/users'. Use '*' for all.")

class AuthSchema(BaseModel):
    rules: List[AuthRule] = Field(..., description="Authorization rules mapping roles to endpoints.")

# --- FINAL OUTPUT SCHEMA ---
class ApplicationConfig(BaseModel):
    database: DatabaseSchema
    api: APISchema
    ui: UISchema
    auth: AuthSchema

    # Cross-layer validation
    @field_validator("api")
    @classmethod
    def validate_api_tables(cls, v: APISchema, info: ValidationInfo):
        # We can't easily cross-validate during raw Pydantic instantiation if dependencies aren't passed
        # properly, so we will handle cross-validation in the Repair Engine explicitly.
        # But we leave this here as a marker.
        return v
