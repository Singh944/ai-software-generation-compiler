import os
import json
from backend.schema import ApplicationConfig

class BaseGenerator:
    def __init__(self, base_dir: str, config: ApplicationConfig):
        self.base_dir = base_dir
        self.config = config

    def ensure_dir(self, path: str):
        full_path = os.path.join(self.base_dir, path)
        os.makedirs(full_path, exist_ok=True)
        return full_path

    def write_file(self, path: str, content: str):
        full_path = os.path.join(self.base_dir, path)
        with open(full_path, "w") as f:
            f.write(content)

class DBGenerator(BaseGenerator):
    def generate(self):
        self.ensure_dir("backend/models")
        schema_sql = "-- Auto-generated SQL Schema\n\n"
        for table in self.config.database.tables:
            schema_sql += f"CREATE TABLE {table.name} (\n"
            for field in table.fields:
                is_pk = " PRIMARY KEY" if field.is_primary_key else ""
                is_req = " NOT NULL" if field.is_required else ""
                refs = f" REFERENCES {field.references_table}" if field.references_table else ""
                schema_sql += f"    {field.name} {field.type.upper()}{is_pk}{is_req}{refs},\n"
            schema_sql = schema_sql.rstrip(",\n") + "\n);\n\n"
        self.write_file("backend/schema.sql", schema_sql)

class APIGenerator(BaseGenerator):
    def generate(self):
        self.ensure_dir("backend/api")
        api_code = "from fastapi import APIRouter\n\nrouter = APIRouter()\n\n"
        for endpoint in self.config.api.endpoints:
            safe_path = endpoint.path.replace('/', '_').replace('{', '').replace('}', '')
            method = endpoint.method.lower()
            api_code += f"@{method}('{endpoint.path}')\n"
            api_code += f"async def handle_{method}{safe_path}():\n"
            api_code += f"    \"\"\"{endpoint.description}\"\"\"\n"
            api_code += f"    return {{'message': 'Auto-generated stub'}}\n\n"
        self.write_file("backend/api/routes.py", api_code)
        
        main_code = "from fastapi import FastAPI\nfrom api.routes import router\n\napp = FastAPI()\napp.include_router(router)\n"
        self.write_file("backend/main.py", main_code)

class UIGenerator(BaseGenerator):
    def generate(self):
        self.ensure_dir("frontend/src/pages")
        app_tsx = "import React from 'react';\nimport { BrowserRouter, Routes, Route } from 'react-router-dom';\n"
        app_tsx += "// Page Imports\n"
        
        routes_jsx = []
        for page in self.config.ui.pages:
            safe_name = "".join(x.capitalize() for x in page.path.strip("/").split("/"))
            if not safe_name:
                safe_name = "Home"
            page_name = f"{safe_name}Page"
            
            app_tsx += f"import {page_name} from './pages/{page_name}';\n"
            routes_jsx.append(f"        <Route path=\"{page.path}\" element={{<{page_name} />}} />")
            
            page_code = f"import React from 'react';\n\nexport default function {page_name}() {{\n"
            page_code += f"  return (\n    <div className='page'>\n      <h1>{page.name}</h1>\n"
            for comp in page.components:
                page_code += f"      <section className='component-{comp.type}'>\n"
                page_code += f"        {comp.name} - {comp.description}\n"
                page_code += f"      </section>\n"
            page_code += "    </div>\n  );\n}\n"
            self.write_file(f"frontend/src/pages/{page_name}.tsx", page_code)
            
        app_tsx += "\nexport default function App() {\n  return (\n    <BrowserRouter>\n      <Routes>\n"
        app_tsx += "\n".join(routes_jsx)
        app_tsx += "\n      </Routes>\n    </BrowserRouter>\n  );\n}\n"
        self.write_file("frontend/src/App.tsx", app_tsx)

class AuthGenerator(BaseGenerator):
    def generate(self):
        self.ensure_dir("backend/auth")
        auth_code = "from fastapi import Depends, HTTPException\n\n"
        auth_code += "# Auto-generated auth rules\n"
        auth_code += f"RULES = {json.dumps([r.model_dump() for r in self.config.auth.rules], indent=2)}\n\n"
        auth_code += "def verify_role(required_roles):\n"
        auth_code += "    def dependency():\n"
        auth_code += "        # Implement JWT validation here\n"
        auth_code += "        pass\n"
        auth_code += "    return dependency\n"
        self.write_file("backend/auth/middleware.py", auth_code)

class Scaffolder:
    @staticmethod
    def generate_project(config_dict: dict, project_name: str = "generated_app") -> str:
        base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "generated_apps", project_name))
        config = ApplicationConfig(**config_dict)
        
        DBGenerator(base_dir, config).generate()
        APIGenerator(base_dir, config).generate()
        UIGenerator(base_dir, config).generate()
        AuthGenerator(base_dir, config).generate()
        
        # Metadata
        with open(os.path.join(base_dir, "metadata.json"), "w") as f:
            json.dump({"project": project_name, "status": "scaffolded", "generated_at": time.time()}, f)
            
        return base_dir
