from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Dict, List, Optional
from contextlib import asynccontextmanager
import os
import re
import requests
from dotenv import load_dotenv

# Import your RAG system classes
from rag_pipeline import (
    PineconeIndex,
    RAGSystem,
    MultiStrategyRetrieval,
    IntelligentReranker,
    MultiAgentGeneration,
    ReflectionQA,
    LLMInputValidator,
    VariableTracker
)
from google import genai

load_dotenv()

# Global RAG system instance
rag_system = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan event handler for startup and shutdown"""
    global rag_system
    
    # Startup
    print("🚀 Initializing Terraform IaC RAG System...")
    
    # Get environment variables
    PINECONE_API_KEY = os.getenv("PINECONE_API_KEY")
    PINECONE_ENVIRONMENT = os.getenv("PINECONE_ENVIRONMENT")
    api_key = os.getenv('GEMINI_API_KEY') or os.getenv('GEMINI_API_KEY')
    
    if not PINECONE_API_KEY or not PINECONE_ENVIRONMENT:
        raise Exception("PINECONE_API_KEY and PINECONE_ENVIRONMENT must be set")
    
    if not api_key:
        raise Exception("GEMINI_API_KEY must be set")
    
    try:
        # Initialize Gemini client
        gemini_client = genai.Client(api_key=api_key)
        
        # Initialize Pinecone vector store
        vector_store = PineconeIndex(
            PINECONE_API_KEY,
            PINECONE_ENVIRONMENT,
            index_name="terraform-aws-docs"
        )
        
        # Initialize RAG system
        rag_system = RAGSystem(
            pinecone_index=vector_store,
            gemini_client=gemini_client,
            model_name="gemini-2.5-flash"
        )
        
        print("✅ RAG System initialized successfully")
        
    except Exception as e:
        print(f"❌ Error initializing RAG system: {e}")
        raise
    
    yield
    
    # Shutdown (cleanup if needed)
    print("👋 Shutting down...")

app = FastAPI(title="Terraform IaC Generator API", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # tighten later
    allow_credentials=True,
    allow_methods=["*"],  # MUST include OPTIONS
    allow_headers=["*"],  # MUST include Content-Type, Authorization
)


# Existing Pydantic models
class QueryRequest(BaseModel):
    query: str

class GenerateRequest(BaseModel):
    query: str
    requirements: Dict
    variables: Dict

class AnalyzeResponse(BaseModel):
    requirements: Dict
    message: str

class GenerateResponse(BaseModel):
    terraform_code: str
    validation_summary: Dict
    requirements: Dict
    variables: Dict
    used_variables: List[str]
    unused_variables: List[str]
    message: str

# New GitHub models
class GitHubRepository(BaseModel):
    id: int
    name: str
    full_name: str
    html_url: str
    private: bool
    description: Optional[str] = None

class GitHubExtractionRequest(BaseModel):
    github_token: str
    repositories: List[GitHubRepository]

class TerraformFileData(BaseModel):
    path: str
    content: str
    repo_name: str
    file_type: str
    resources: List[str]
    modules: List[str]
    providers: List[str]
    variables: List[str]
    outputs: List[str]
    size_bytes: int

class GitHubExtractionResponse(BaseModel):
    status: str
    repositories_processed: int
    total_files: int
    files: List[TerraformFileData]
    message: str


@app.get("/")
async def root():
    """Health check endpoint"""
    return {
        "status": "online",
        "service": "Terraform IaC Generator API",
        "version": "1.0.0"
    }

# FIXED: Add explicit OPTIONS handler for CORS preflight
@app.options("/api/analyze-query")
async def options_analyze_query():
    """Handle CORS preflight for analyze-query"""
    return {"status": "ok"}

@app.options("/api/generate")
async def options_generate():
    """Handle CORS preflight for generate"""
    return {"status": "ok"}

@app.options("/api/extract-github")
async def options_extract_github():
    """Handle CORS preflight for extract-github"""
    return {"status": "ok"}

@app.post("/api/analyze-query", response_model=AnalyzeResponse)
async def analyze_query(request: QueryRequest):
    """
    Analyze user query and extract requirements
    
    Layer 1: Query Understanding
    """
    if not rag_system:
        raise HTTPException(status_code=503, detail="RAG system not initialized")
    
    if not request.query.strip():
        raise HTTPException(status_code=400, detail="Query cannot be empty")
    
    try:
        print(f"\n📝 Analyzing query: {request.query}")
        
        # Use the query understanding agent
        requirements = rag_system.query_understanding_agent(request.query)
        
        return AnalyzeResponse(
            requirements=requirements,
            message="Query analyzed successfully"
        )
        
    except Exception as e:
        print(f"❌ Error analyzing query: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/generate", response_model=GenerateResponse)
async def generate_terraform(request: GenerateRequest):
    """
    Generate Terraform code with AI validation
    
    Layers 2-6: Variable Collection, Retrieval, Reranking, Generation, Reflection
    """
    if not rag_system:
        raise HTTPException(status_code=503, detail="RAG system not initialized")
    
    try:
        print(f"\n🏗️ Generating Terraform code...")
        print(f"Variables: {request.variables}")
        
        # AI-powered input validation (Layer 2)
        print("\n🔍 Validating inputs with AI...")
        correction_result = rag_system.validator.validate_and_correct(
            request.variables,
            request.requirements.get('resource_type', 'infrastructure')
        )
        
        # Use corrected variables
        validated_variables = correction_result.corrected_variables
        
        print(f"✅ Variables after validation: {validated_variables}")
        
        # Layer 3: Multi-Strategy Retrieval
        print("\n📚 Retrieving relevant documentation...")
        retrieval_results = rag_system.retrieval.multi_strategy_retrieve(
            request.query,
            request.requirements['resource_type']
        )
        
        # Layer 4: Re-ranking & Validation
        print("\n🎯 Re-ranking and validating context...")
        best_context = rag_system.reranker.rerank_and_validate(
            request.query,
            retrieval_results
        )
        
        # Layer 5: Multi-Agent Generation
        print("\n🤖 Generating code with multi-agent system...")
        terraform_code, validation_results, variable_tracker = rag_system.agents.generate_with_agents(
            request.query,
            best_context,
            validated_variables
        )
        
        # Layer 6: Reflection & QA
        print("\n✨ Applying reflection and quality assurance...")
        final_code = rag_system.reflection.reflection_qa_pipeline(
            terraform_code,
            validation_results,
            best_context,
            validated_variables,
            variable_tracker,
            max_iterations=4
        )
        
        # Final verification
        final_tracker = VariableTracker()
        final_tracker.add_variables(validated_variables)
        used_vars, unused_vars = final_tracker.check_usage_in_code(final_code)
        
        # Prepare validation summary
        validation_summary = {
            agent: {
                'is_valid': val.is_valid,
                'score': val.score,
                'issues_count': len(val.issues)
            }
            for agent, val in validation_results.items()
        }
        
        print(f"\n✅ Generation complete!")
        print(f"Variables used: {len(used_vars)}/{len(validated_variables)}")
        
        return GenerateResponse(
            terraform_code=final_code,
            validation_summary=validation_summary,
            requirements=request.requirements,
            variables=validated_variables,
            used_variables=used_vars,
            unused_variables=unused_vars,
            message="Terraform code generated successfully"
        )
        
    except Exception as e:
        print(f"❌ Error generating code: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

# NEW: GitHub Extraction Endpoint
@app.post("/api/extract-github", response_model=GitHubExtractionResponse)
async def extract_from_github(request: GitHubExtractionRequest):
    """
    Extract Terraform code from GitHub repositories
    Uses the GitHub API to fetch and parse Terraform files
    """
    if not request.github_token:
        raise HTTPException(status_code=400, detail="GitHub token is required")
    
    if not request.repositories:
        raise HTTPException(status_code=400, detail="No repositories provided")
    
    print(f"\n{'='*70}")
    print(f"GITHUB EXTRACTION STARTED")
    print(f"{'='*70}")
    print(f"Repositories to process: {len(request.repositories)}")
    
    all_files = []
    repos_processed = 0
    
    headers = {
        'Authorization': f'Bearer {request.github_token}',
        'Accept': 'application/vnd.github.v3+json'
    }
    
    for repo in request.repositories:
        try:
            print(f"\n📦 Processing: {repo.full_name}")
            
            # Extract files from this repository
            files = extract_terraform_from_repo(
                repo.full_name,
                repo.html_url,
                headers
            )
            
            all_files.extend(files)
            repos_processed += 1
            
            print(f"   ✅ Extracted {len(files)} Terraform files")
            
        except Exception as e:
            print(f"   ❌ Error processing {repo.full_name}: {e}")
            continue
    
    print(f"\n{'='*70}")
    print(f"EXTRACTION COMPLETE")
    print(f"{'='*70}")
    print(f"Repositories processed: {repos_processed}/{len(request.repositories)}")
    print(f"Total Terraform files extracted: {len(all_files)}")
    
    # Print detailed breakdown
    if all_files:
        print(f"\n📊 FILE BREAKDOWN:")
        file_types = {}
        resources_found = set()
        providers_found = set()
        
        for file in all_files:
            # Count file types
            file_types[file.file_type] = file_types.get(file.file_type, 0) + 1
            
            # Collect resources and providers
            resources_found.update(file.resources)
            providers_found.update(file.providers)
            
            # Print each file
            print(f"\n   📄 {file.repo_name}/{file.path}")
            print(f"      Type: {file.file_type}")
            print(f"      Size: {file.size_bytes} bytes")
            if file.resources:
                print(f"      Resources: {', '.join(file.resources[:3])}" + 
                      (f" +{len(file.resources)-3} more" if len(file.resources) > 3 else ""))
            if file.providers:
                print(f"      Providers: {', '.join(file.providers)}")
            if file.variables:
                print(f"      Variables: {len(file.variables)} defined")
            if file.outputs:
                print(f"      Outputs: {len(file.outputs)} defined")
        
        print(f"\n📈 STATISTICS:")
        print(f"   File types: {dict(file_types)}")
        print(f"   Unique resources: {len(resources_found)}")
        print(f"   Providers used: {', '.join(providers_found)}")
        print(f"   Total code size: {sum(f.size_bytes for f in all_files):,} bytes")
    
    return GitHubExtractionResponse(
        status="success",
        repositories_processed=repos_processed,
        total_files=len(all_files),
        files=all_files,
        message=f"Successfully extracted {len(all_files)} Terraform files from {repos_processed} repositories"
    )


def extract_terraform_from_repo(
    repo_full_name: str,
    repo_url: str,
    headers: dict
) -> List[TerraformFileData]:
    """
    Extract all Terraform files from a single repository
    """
    files = []
    skip_dirs = ['.git', '.terraform', 'test', 'tests', 'examples', 'example', '.github']
    
    # Regex patterns for parsing
    resource_pattern = re.compile(r'resource\s+"([^"]+)"\s+"([^"]+)"')
    module_pattern = re.compile(r'module\s+"([^"]+)"\s*\{[^}]*source\s*=\s*"([^"]+)"', re.DOTALL)
    provider_pattern = re.compile(r'provider\s+"([^"]+)"')
    variable_pattern = re.compile(r'variable\s+"([^"]+)"')
    output_pattern = re.compile(r'output\s+"([^"]+)"')
    
    def fetch_contents(path: str = ""):
        """Recursively fetch repository contents"""
        url = f"https://api.github.com/repos/{repo_full_name}/contents/{path}" if path else \
              f"https://api.github.com/repos/{repo_full_name}/contents"
        
        try:
            response = requests.get(url, headers=headers, timeout=10)
            
            if response.status_code == 200:
                return response.json()
        except Exception as e:
            print(f"      ⚠️  Error fetching {path}: {e}")
        
        return []
    
    def classify_file_type(filepath: str, content: str) -> str:
        """Classify the type of Terraform file"""
        filename = filepath.lower()
        
        if 'variables' in filename or filename.startswith('vars'):
            return 'variables'
        elif 'outputs' in filename:
            return 'outputs'
        elif 'providers' in filename or 'terraform' in filename:
            return 'providers'
        elif 'modules' in filename or '/modules/' in filepath:
            return 'module'
        elif 'main' in filename:
            return 'main'
        elif content.strip().startswith('terraform {'):
            return 'terraform_config'
        else:
            return 'resource'
    
    def parse_terraform_content(content: str) -> dict:
        """Parse Terraform file content to extract metadata"""
        resources = [f"{m[0]}.{m[1]}" for m in resource_pattern.findall(content)]
        modules = [m[1] for m in module_pattern.findall(content)]
        providers = list(set(provider_pattern.findall(content)))
        variables = variable_pattern.findall(content)
        outputs = output_pattern.findall(content)
        
        return {
            'resources': resources,
            'modules': modules,
            'providers': providers,
            'variables': variables,
            'outputs': outputs
        }
    
    def process_item(item: dict):
        """Process a single file or directory"""
        if item['type'] == 'dir':
            # Skip certain directories
            if any(skip in item['path'] for skip in skip_dirs):
                return
            
            # Recursively process directory
            sub_contents = fetch_contents(item['path'])
            for sub_item in sub_contents:
                process_item(sub_item)
        
        elif item['type'] == 'file':
            # Check if it's a Terraform file
            if item['name'].endswith('.tf') or item['name'].endswith('.tfvars') or item['name'].endswith('.hcl'):
                try:
                    # Fetch file content
                    file_response = requests.get(item['download_url'], headers=headers, timeout=10)
                    
                    if file_response.status_code == 200:
                        content = file_response.text
                        
                        # Parse the file
                        parsed = parse_terraform_content(content)
                        file_type = classify_file_type(item['path'], content)
                        
                        tf_file = TerraformFileData(
                            path=item['path'],
                            content=content,
                            repo_name=repo_full_name,
                            file_type=file_type,
                            resources=parsed['resources'],
                            modules=parsed['modules'],
                            providers=parsed['providers'],
                            variables=parsed['variables'],
                            outputs=parsed['outputs'],
                            size_bytes=len(content.encode('utf-8'))
                        )
                        
                        files.append(tf_file)
                        
                except Exception as e:
                    print(f"      ⚠️  Error processing {item['path']}: {e}")
    
    # Start processing from root
    contents = fetch_contents()
    
    for item in contents:
        process_item(item)
    
    return files


@app.get("/api/health")
async def health_check():
    """Detailed health check"""
    return {
        "status": "healthy",
        "rag_system": "initialized" if rag_system else "not initialized",
        "components": {
            "pinecone": rag_system is not None,
            "gemini": rag_system is not None,
            "retrieval": rag_system is not None and rag_system.retrieval is not None,
            "reranker": rag_system is not None and rag_system.reranker is not None,
            "agents": rag_system is not None and rag_system.agents is not None,
            "reflection": rag_system is not None and rag_system.reflection is not None,
            "validator": rag_system is not None and rag_system.validator is not None,
        }
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)