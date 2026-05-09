from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import os
import traceback
from dotenv import load_dotenv

load_dotenv()

from backend.pipeline import GenerationPipeline
from backend.runtime import RuntimeSimulator

app = FastAPI(title="Software Generation Compiler API")

# Setup CORS for the frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class GenerateRequest(BaseModel):
    prompt: str

@app.post("/generate")
async def generate_app(request: GenerateRequest):
    from backend.config import LLMConfig
    if LLMConfig.get_provider() == "none":
        raise HTTPException(status_code=500, detail="No valid API key (OpenRouter or Groq) is set on the server.")
    
    try:
        pipeline = GenerationPipeline()
        result = pipeline.run(request.prompt)
        
        if result.get("status") == "success":
            # Run the runtime simulation
            simulation = RuntimeSimulator.simulate(result["application_config"])
            result["simulation"] = simulation
            
        return result
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/health")
async def health_check():
    from backend.config import LLMConfig
    provider = LLMConfig.get_provider()
    return {
        "status": "ok",
        "llm_configured": provider != "none",
        "provider": provider
    }

@app.get("/project/{project_name}/files")
async def get_project_files(project_name: str):
    base_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "generated_apps", project_name))
    if not os.path.exists(base_path) or "generated_apps" not in base_path:
        raise HTTPException(status_code=404, detail="Project not found")
        
    file_tree = []
    for root, dirs, files in os.walk(base_path):
        for f in files:
            full_path = os.path.join(root, f)
            rel_path = os.path.relpath(full_path, base_path)
            file_tree.append(rel_path)
            
    return {"files": sorted(file_tree)}

@app.get("/project/{project_name}/file/{file_path:path}")
async def get_project_file_content(project_name: str, file_path: str):
    base_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "generated_apps", project_name))
    target_path = os.path.abspath(os.path.join(base_path, file_path))
    
    if not target_path.startswith(base_path):
        raise HTTPException(status_code=403, detail="Forbidden")
        
    if not os.path.exists(target_path):
        raise HTTPException(status_code=404, detail="File not found")
        
    with open(target_path, "r") as f:
        return {"content": f.read()}

@app.get("/evaluate/metrics")
async def get_evaluation_metrics():
    eval_file = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "reports", "evaluation_results.json"))
    if not os.path.exists(eval_file):
        return {"status": "no_data"}
        
    try:
        import json
        with open(eval_file, "r") as f:
            data = json.load(f)
        return {"status": "ok", "metrics": data.get("metrics", {})}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

