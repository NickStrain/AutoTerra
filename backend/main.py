from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Dict, List, Optional
from contextlib import asynccontextmanager
import os
import re
import requests
import shutil
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

# Import sandbox tester
from sandbox_testing import TerraformSandboxTester

load_dotenv()

# Global instances
rag_system = None
sandbox_tester = None
terraform_available = False

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan event handler for startup and shutdown"""
    global rag_system, sandbox_tester, terraform_available
    
    # Startup
    print("Initializing Terraform IaC RAG System...")
    
    # Check if Terraform is installed
    terraform_available = shutil.which('terraform') is not None
    if terraform_available:
        print("✓ Terraform found in PATH")
    else:
        print("⚠ WARNING: Terraform not found in PATH")
        print("  Sandbox testing will be disabled")
        print("  Install from: https://www.terraform.io/downloads")
    
    # Get environment variables
    PINECONE_API_KEY = os.getenv("PINECONE_API_KEY")
    PINECONE_ENVIRONMENT = os.getenv("PINECONE_ENVIRONMENT")
    HUGGINGFACE_API_KEY = os.getenv("HUGGINGFACE_API_KEY")
    api_key = os.getenv('GEMINI_API_KEY')
    if not HUGGINGFACE_API_KEY:
        raise Exception("No hugging face is set")
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
        
        # Initialize sandbox tester only if Terraform is available
        if terraform_available:
            try:
                sandbox_tester = TerraformSandboxTester()
                print("✓ Sandbox Tester initialized successfully")
            except Exception as e:
                print(f"⚠ WARNING: Sandbox tester initialization failed: {e}")
                sandbox_tester = None
        else:
            print("⚠ Sandbox Tester disabled (Terraform not found)")
        
        print("✓ RAG System initialized successfully")
        
    except Exception as e:
        print(f"ERROR: Error initializing systems: {e}")
        raise
    
    yield
    
    # Shutdown
    print("Shutting down...")

app = FastAPI(title="Terraform IaC Generator API", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Pydantic models
class QueryRequest(BaseModel):
    query: str

class GenerateRequest(BaseModel):
    query: str
    requirements: Dict
    variables: Dict
    run_sandbox_test: bool = True
    run_security_scan: bool = True
    generate_plan: bool = True

class AnalyzeResponse(BaseModel):
    requirements: Dict
    message: str

class ValidationResultModel(BaseModel):
    valid: bool
    format_valid: bool
    init_success: bool
    validate_output: str
    errors: List[str]
    warnings: List[str]

class SecurityScanResultModel(BaseModel):
    passed: bool
    critical_issues: int
    high_issues: int
    medium_issues: int
    low_issues: int
    findings: List[Dict]
    scanner: str

class SandboxTestResult(BaseModel):
    status: str
    timestamp: str
    validation: Optional[ValidationResultModel]
    security_scans: List[SecurityScanResultModel]
    plan_output: Optional[str]
    overall_passed: bool
    summary: str

class GenerateResponse(BaseModel):
    terraform_code: str
    validation_summary: Dict
    requirements: Dict
    variables: Dict
    used_variables: List[str]
    unused_variables: List[str]
    sandbox_test_result: Optional[SandboxTestResult] = None
    sandbox_test_available: bool
    message: str

# GitHub models
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

# Sandbox testing models
class SandboxTestRequest(BaseModel):
    terraform_code: str
    run_security_scan: bool = True
    generate_plan: bool = True

class SandboxTestResponse(BaseModel):
    status: str
    timestamp: str
    validation: Optional[ValidationResultModel]
    security_scans: List[SecurityScanResultModel]
    plan_output: Optional[str]
    overall_passed: bool
    summary: str


@app.get("/")
async def root():
    """Health check endpoint"""
    return {
        "status": "online",
        "service": "Terraform IaC Generator API",
        "version": "1.0.0",
        "terraform_available": terraform_available
    }

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

@app.options("/api/test-sandbox")
async def options_test_sandbox():
    """Handle CORS preflight for test-sandbox"""
    return {"status": "ok"}

@app.post("/api/analyze-query", response_model=AnalyzeResponse)
async def analyze_query(request: QueryRequest):
    """Analyze user query and extract requirements"""
    if not rag_system:
        raise HTTPException(status_code=503, detail="RAG system not initialized")
    
    if not request.query.strip():
        raise HTTPException(status_code=400, detail="Query cannot be empty")
    
    try:
        print(f"\nAnalyzing query: {request.query}")
        
        requirements = rag_system.query_understanding_agent(request.query)
        
        return AnalyzeResponse(
            requirements=requirements,
            message="Query analyzed successfully"
        )
        
    except Exception as e:
        print(f"ERROR: Error analyzing query: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/generate", response_model=GenerateResponse)
async def generate_terraform(request: GenerateRequest):
    """Generate Terraform code with AI validation and optional sandbox testing"""
    if not rag_system:
        raise HTTPException(status_code=503, detail="RAG system not initialized")
    
    try:
        print(f"\n{'='*70}")
        print(f"TERRAFORM CODE GENERATION STARTED")
        print(f"{'='*70}")
        print(f"Variables: {request.variables}")
        
        # AI-powered input validation
        print("\n[1/6] Validating inputs with AI...")
        correction_result = rag_system.validator.validate_and_correct(
            request.variables,
            request.requirements.get('resource_type', 'infrastructure')
        )
        
        validated_variables = correction_result.corrected_variables
        print(f"      Variables after validation: {validated_variables}")
        
        # Multi-Strategy Retrieval
        print("\n[2/6] Retrieving relevant documentation...")
        retrieval_results = rag_system.retrieval.multi_strategy_retrieve(
            request.query,
            request.requirements['resource_type']
        )
        print(f"      Retrieved {len(retrieval_results)} relevant chunks")
        
        # Re-ranking & Validation
        print("\n[3/6] Re-ranking and validating context...")
        best_context = rag_system.reranker.rerank_and_validate(
            request.query,
            retrieval_results
        )
        print(f"      Selected best {len(best_context)} context chunks")
        
        # Multi-Agent Generation
        print("\n[4/6] Generating code with multi-agent system...")
        terraform_code, validation_results, variable_tracker = rag_system.agents.generate_with_agents(
            request.query,
            best_context,
            validated_variables
        )
        print(f"      Initial code generated ({len(terraform_code)} chars)")
        
        # Reflection & QA
        print("\n[5/6] Applying reflection and quality assurance...")
        final_code = rag_system.reflection.reflection_qa_pipeline(
            terraform_code,
            validation_results,
            best_context,
            validated_variables,
            variable_tracker,
            max_iterations=4
        )
        print(f"      Final code refined ({len(final_code)} chars)")
        
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
        
        print(f"\n      Generation complete!")
        print(f"      Variables used: {len(used_vars)}/{len(validated_variables)}")
        
        # Run sandbox testing if enabled and available
        sandbox_result = None
        if request.run_sandbox_test and terraform_available and sandbox_tester:
            print(f"\n[6/6] Running sandbox testing...")
            print(f"{'='*70}")
            
            try:
                test_result = sandbox_tester.test_terraform_code(
                    terraform_code=final_code,
                    run_security_scan=request.run_security_scan,
                    generate_plan=request.generate_plan
                )
                
                # Convert to response model
                sandbox_result = SandboxTestResult(
                    status=test_result.status,
                    timestamp=test_result.timestamp,
                    validation=ValidationResultModel(**test_result.validation.__dict__) if test_result.validation else None,
                    security_scans=[SecurityScanResultModel(**scan.__dict__) for scan in test_result.security_scans],
                    plan_output=test_result.plan_output,
                    overall_passed=test_result.overall_passed,
                    summary=test_result.summary
                )
                
                print(f"\n      Sandbox testing complete!")
                print(f"      Status: {test_result.status}")
                print(f"      Overall passed: {test_result.overall_passed}")
                
                if not test_result.overall_passed:
                    print(f"      WARNING: Sandbox tests failed!")
                    if test_result.validation and test_result.validation.errors:
                        print(f"      Validation errors: {len(test_result.validation.errors)}")
                    for scan in test_result.security_scans:
                        if not scan.passed:
                            print(f"      Security issues: {scan.critical_issues} critical, {scan.high_issues} high")
                
            except Exception as e:
                print(f"      WARNING: Sandbox testing failed: {e}")
                import traceback
                traceback.print_exc()
        elif request.run_sandbox_test and not terraform_available:
            print(f"\n[6/6] Sandbox testing skipped (Terraform not installed)")
            print(f"      Install Terraform from: https://www.terraform.io/downloads")
        else:
            print(f"\n[6/6] Sandbox testing skipped (disabled)")
        
        print(f"\n{'='*70}")
        print(f"GENERATION PIPELINE COMPLETE")
        print(f"{'='*70}\n")
        
        message = "Terraform code generated successfully"
        if sandbox_result:
            message += " and tested in sandbox"
        elif request.run_sandbox_test and not terraform_available:
            message += " (sandbox testing unavailable - Terraform not installed)"
        
        return GenerateResponse(
            terraform_code=final_code,
            validation_summary=validation_summary,
            requirements=request.requirements,
            variables=validated_variables,
            used_variables=used_vars,
            unused_variables=unused_vars,
            sandbox_test_result=sandbox_result,
            sandbox_test_available=terraform_available,
            message=message
        )
        
    except Exception as e:
        print(f"ERROR: Error generating code: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/extract-github", response_model=GitHubExtractionResponse)
async def extract_from_github(request: GitHubExtractionRequest):
    """Extract Terraform code from GitHub repositories"""
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
            print(f"\nProcessing: {repo.full_name}")
            
            files = extract_terraform_from_repo(
                repo.full_name,
                repo.html_url,
                headers
            )
            
            all_files.extend(files)
            repos_processed += 1
            
            print(f"   Extracted {len(files)} Terraform files")
            
        except Exception as e:
            print(f"   ERROR processing {repo.full_name}: {e}")
            continue
    
    print(f"\n{'='*70}")
    print(f"EXTRACTION COMPLETE")
    print(f"{'='*70}")
    print(f"Repositories processed: {repos_processed}/{len(request.repositories)}")
    print(f"Total Terraform files extracted: {len(all_files)}")
    
    return GitHubExtractionResponse(
        status="success",
        repositories_processed=repos_processed,
        total_files=len(all_files),
        files=all_files,
        message=f"Successfully extracted {len(all_files)} Terraform files from {repos_processed} repositories"
    )

@app.post("/api/test-sandbox", response_model=SandboxTestResponse)
async def test_in_sandbox(request: SandboxTestRequest):
    """Test Terraform code in isolated sandbox"""
    if not terraform_available:
        raise HTTPException(
            status_code=503, 
            detail="Terraform not installed. Install from https://www.terraform.io/downloads"
        )
    
    if not sandbox_tester:
        raise HTTPException(status_code=503, detail="Sandbox tester not initialized")
    
    if not request.terraform_code.strip():
        raise HTTPException(status_code=400, detail="Terraform code cannot be empty")
    
    try:
        print(f"\n{'='*70}")
        print(f"SANDBOX TESTING STARTED")
        print(f"{'='*70}")
        
        # Test the code
        result = sandbox_tester.test_terraform_code(
            terraform_code=request.terraform_code,
            run_security_scan=request.run_security_scan,
            generate_plan=request.generate_plan
        )
        
        # Convert result to response model
        response = SandboxTestResponse(
            status=result.status,
            timestamp=result.timestamp,
            validation=ValidationResultModel(**result.validation.__dict__) if result.validation else None,
            security_scans=[SecurityScanResultModel(**scan.__dict__) for scan in result.security_scans],
            plan_output=result.plan_output,
            overall_passed=result.overall_passed,
            summary=result.summary
        )
        
        print(f"\n{'='*70}")
        print(f"SANDBOX TESTING COMPLETE")
        print(f"{'='*70}")
        print(f"Status: {result.status}")
        print(f"Overall passed: {result.overall_passed}")
        
        return response
        
    except Exception as e:
        print(f"ERROR: Sandbox testing failed: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


def extract_terraform_from_repo(
    repo_full_name: str,
    repo_url: str,
    headers: dict
) -> List[TerraformFileData]:
    """Extract all Terraform files from a single repository"""
    files = []
    skip_dirs = ['.git', '.terraform', 'test', 'tests', 'examples', 'example', '.github']
    
    resource_pattern = re.compile(r'resource\s+"([^"]+)"\s+"([^"]+)"')
    module_pattern = re.compile(r'module\s+"([^"]+)"\s*\{[^}]*source\s*=\s*"([^"]+)"', re.DOTALL)
    provider_pattern = re.compile(r'provider\s+"([^"]+)"')
    variable_pattern = re.compile(r'variable\s+"([^"]+)"')
    output_pattern = re.compile(r'output\s+"([^"]+)"')
    
    def fetch_contents(path: str = ""):
        url = f"https://api.github.com/repos/{repo_full_name}/contents/{path}" if path else \
              f"https://api.github.com/repos/{repo_full_name}/contents"
        
        try:
            response = requests.get(url, headers=headers, timeout=10)
            if response.status_code == 200:
                return response.json()
        except Exception as e:
            print(f"      WARNING: Error fetching {path}: {e}")
        return []
    
    def classify_file_type(filepath: str, content: str) -> str:
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
        if item['type'] == 'dir':
            if any(skip in item['path'] for skip in skip_dirs):
                return
            sub_contents = fetch_contents(item['path'])
            for sub_item in sub_contents:
                process_item(sub_item)
        
        elif item['type'] == 'file':
            if item['name'].endswith('.tf') or item['name'].endswith('.tfvars') or item['name'].endswith('.hcl'):
                try:
                    file_response = requests.get(item['download_url'], headers=headers, timeout=10)
                    
                    if file_response.status_code == 200:
                        content = file_response.text
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
                    print(f"      WARNING: Error processing {item['path']}: {e}")
    
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
        "sandbox_tester": "initialized" if sandbox_tester else "not initialized",
        "terraform_available": terraform_available,
        "components": {
            "pinecone": rag_system is not None,
            "gemini": rag_system is not None,
            "retrieval": rag_system is not None and rag_system.retrieval is not None,
            "reranker": rag_system is not None and rag_system.reranker is not None,
            "agents": rag_system is not None and rag_system.agents is not None,
            "reflection": rag_system is not None and rag_system.reflection is not None,
            "validator": rag_system is not None and rag_system.validator is not None,
            "sandbox_tester": sandbox_tester is not None,
        }
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)