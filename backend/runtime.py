from pydantic import BaseModel
from backend.schema import ApplicationConfig
from backend.scaffolder import Scaffolder
import time

class RuntimeSimulator:
    """
    Simulates the execution of the generated application configuration
    by physically scaffolding the source code and folder structures.
    """
    @staticmethod
    def simulate(config: dict) -> dict:
        try:
            # Re-validate the dictionary into our Pydantic model to ensure it is safe
            app_config = ApplicationConfig(**config)
            
            project_name = f"app_{int(time.time())}"
            output_dir = Scaffolder.generate_project(config, project_name)
            
            table_names = [t.name for t in app_config.database.tables]
            routes = [f"{e.method} {e.path}" for e in app_config.api.endpoints]
            pages = [p.path for p in app_config.ui.pages]
            
            return {
                "success": True,
                "message": "Configuration successfully compiled and scaffolded.",
                "details": {
                    "tables_migrated": len(table_names),
                    "api_routes_mounted": len(routes),
                    "ui_pages_rendered": len(pages),
                    "output_directory": output_dir
                }
            }
        except Exception as e:
            return {
                "success": False,
                "message": f"Execution simulation failed: {str(e)}"
            }
