import json
import time
import os
import argparse
from dotenv import load_dotenv
from backend.pipeline import GenerationPipeline
from backend.eval_cache import EvalCacheManager

load_dotenv()


EST_INPUT_COST_PER_TOKEN = 0.0006 / 1000
EST_OUTPUT_COST_PER_TOKEN = 0.0008 / 1000

def estimate_tokens(text: str) -> int:
    return len(str(text)) // 4

def estimate_cost(prompt: str, output: dict) -> float:
    input_tokens = estimate_tokens(prompt) * 3 # rough estimate including schema
    output_tokens = estimate_tokens(json.dumps(output))
    return (input_tokens * EST_INPUT_COST_PER_TOKEN) + (output_tokens * EST_OUTPUT_COST_PER_TOKEN)

def evaluate(mode: str):
    if not os.getenv("GROQ_API_KEY"):
        print("Please set GROQ_API_KEY environment variable to run evaluation.")
        return

    # Load Datasets
    with open("datasets/standard_prompts.json", "r") as f:
        std_prompts = json.load(f)
    with open("datasets/edge_case_prompts.json", "r") as f:
        edge_prompts = json.load(f)
        
    all_prompts = std_prompts + edge_prompts
    
    if mode == "QUICK_EVALUATION":
        prompts = std_prompts[:2] + edge_prompts[:1]
    else:
        prompts = all_prompts

    pipeline = GenerationPipeline()
    cache_manager = EvalCacheManager()
    
    results = {
        "metrics": {
            "total_evaluated": len(prompts),
            "structured_compilations": 0,
            "vague_prompt_detection": 0,
            "validation_escalations": 0,
            "total_retries": 0,
            "total_latency_seconds": 0,
            "cache_hits": 0,
            "api_calls_avoided": 0,
            "estimated_cost_saved": 0.0
        },
        "details": []
    }

    print(f"Starting {mode} on {len(prompts)} prompts...")
    
    for item in prompts:
        print(f"\nEvaluating ID {item['id']} ({item['type']})...")
        start_time = time.time()
        
        # Check Eval Cache
        cached_eval = None
        if mode != "IGNORE_CACHE":
            cached_eval = cache_manager.get(item['prompt'])
            
        if mode == "CACHE_ONLY_MODE" and not cached_eval:
            print("Skipping (CACHE_ONLY_MODE active and no cache found).")
            continue
            
        if cached_eval:
            print("CACHE HIT! Skipping LLM generation.")
            output = cached_eval["result"]
            latency = 0.0  # Instant local load
            results["metrics"]["cache_hits"] += 1
            
            # Estimate savings
            results["metrics"]["api_calls_avoided"] += 1
            results["metrics"]["estimated_cost_saved"] += estimate_cost(item['prompt'], output)
            
            # Add small delay just for terminal UX
            time.sleep(0.1)
        else:
            try:
                output = pipeline.run(item['prompt'])
                latency = time.time() - start_time
                
                # Save to Eval Cache
                cache_manager.set(item['prompt'], item['id'], item['type'], output)
                
                print(f"Sleeping for 15 seconds to respect rate limits...")
                time.sleep(15) # Reduced sleep due to pipeline-level cache helping out
            except Exception as e:
                output = {"status": "failed", "reason": "system_error", "error_message": str(e)}
                latency = time.time() - start_time
        
        results["metrics"]["total_latency_seconds"] += latency
        
        if output.get("status") == "success":
            results["metrics"]["structured_compilations"] += 1
            status = "success"
            retries = output.get("total_retries_used", 0)
            results["metrics"]["total_retries"] += retries
        elif output.get("status") == "failed" and output.get("reason") == "vague_prompt":
            results["metrics"]["vague_prompt_detection"] += 1
            status = "vague_prompt_detection"
            retries = 0
        else:
            results["metrics"]["validation_escalations"] += 1
            status = "consistency_repair_exhausted"
            retries = 0
            
        results["details"].append({
            "id": item["id"],
            "type": item["type"],
            "status": status,
            "latency": latency,
            "retries": retries,
            "error_message": output.get("error_message") if status == "consistency_repair_exhausted" else None
        })
        
        print(f"Result: {status} in {latency:.2f}s (Retries: {retries})")
    
    total_evals = results["metrics"]["total_evaluated"]
    if total_evals > 0:
        results["metrics"]["average_latency_seconds"] = results["metrics"]["total_latency_seconds"] / total_evals
    
    print("\n=== EVALUATION COMPLETE ===")
    print(json.dumps(results["metrics"], indent=2))
    
    import os
    os.makedirs("reports", exist_ok=True)
    with open("reports/evaluation_results.json", "w") as f:
        json.dump(results, f, indent=2)
        
    print("Saved full details to reports/evaluation_results.json")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Evaluate the Software Generation Compiler")
    parser.add_argument("--mode", type=str, choices=["FULL_EVALUATION", "QUICK_EVALUATION", "CACHE_ONLY_MODE", "IGNORE_CACHE"], default="FULL_EVALUATION", help="Evaluation mode to run")
    args = parser.parse_args()
    
    evaluate(args.mode)
