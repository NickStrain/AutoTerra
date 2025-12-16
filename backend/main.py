from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Dict, List, Optional
from contextlib import asynccontextmanager
import os
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


# Pydantic models
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