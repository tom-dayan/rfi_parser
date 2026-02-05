"""
Chat API endpoints for conversational Q&A.

Provides endpoints for chat-based interaction with the knowledge base,
allowing users to ask questions about projects and get AI-powered responses.
"""

import uuid
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Project
from ..config import settings
from ..services.knowledge_base import get_knowledge_base
from ..services.content_cache import get_content_cache
from ..services.metadata_index import get_metadata_index


router = APIRouter(prefix="/api/chat", tags=["chat"])


class ChatMessage(BaseModel):
    """A chat message from the user."""
    content: str
    project_id: Optional[int] = None
    session_id: Optional[str] = None


class ChatResponse(BaseModel):
    """A chat response."""
    content: str
    session_id: str
    sources: list[dict] = []
    timestamp: str


# In-memory session storage (in production, use Redis or database)
_sessions: dict[str, list[dict]] = {}


@router.post("/message", response_model=ChatResponse)
async def send_message(
    message: ChatMessage,
    db: Session = Depends(get_db),
):
    """
    Send a message and get an AI-powered response.
    
    The response will search the knowledge base for relevant information
    and use AI to generate a helpful answer.
    """
    # Generate or use existing session ID
    session_id = message.session_id or str(uuid.uuid4())
    
    # Get or create session history
    if session_id not in _sessions:
        _sessions[session_id] = []
    
    history = _sessions[session_id]
    
    # Add user message to history
    history.append({
        "role": "user",
        "content": message.content,
        "timestamp": datetime.utcnow().isoformat(),
    })
    
    # Search for relevant context
    sources = []
    context = ""
    
    if message.project_id:
        # Search within project
        project = db.query(Project).filter(Project.id == message.project_id).first()
        if not project:
            raise HTTPException(status_code=404, detail="Project not found")
        
        # Use knowledge base for semantic search
        kb = get_knowledge_base(message.project_id)
        if kb and project.kb_indexed:
            search_results = kb.search_with_context(message.content, n_results=5)
            if search_results:
                context = "\n\n".join([
                    f"[From {r['source']}, Section: {r.get('section', 'N/A')}]\n{r['text']}"
                    for r in search_results
                ])
                sources = [
                    {
                        "filename": r["source"],
                        "section": r.get("section"),
                        "relevance": r.get("score", 0),
                    }
                    for r in search_results
                ]
    else:
        # Global search using metadata index
        index = get_metadata_index()
        cache = get_content_cache()
        
        # First try filename search
        results = index.search(message.content, limit=10)
        
        # If no filename matches, get recent/all files and search their content
        if not results:
            # Get all indexed files as candidates
            results = index.search("*", limit=20)
        
        if results:
            # Search through file contents for relevant information
            query_lower = message.content.lower()
            query_words = set(query_lower.split())
            
            for result in results:
                try:
                    content, _, _ = cache.get_or_parse(result["path"])
                    if content:
                        content_lower = content.lower()
                        # Check if content is relevant to the query
                        relevance = sum(1 for word in query_words if word in content_lower and len(word) > 2)
                        
                        if relevance > 0 or len(sources) < 3:
                            # Truncate content
                            truncated = content[:3000] + "..." if len(content) > 3000 else content
                            context += f"\n\n[From {result['filename']}]\n{truncated}"
                            sources.append({
                                "filename": result["filename"],
                                "path": result["path"],
                                "type": result.get("file_type"),
                                "relevance": relevance,
                            })
                        
                        # Limit to top 5 sources
                        if len(sources) >= 5:
                            break
                except Exception:
                    pass
            
            # Sort sources by relevance
            sources.sort(key=lambda x: x.get("relevance", 0), reverse=True)
    
    # Build prompt
    if context:
        system_prompt = f"""You are an assistant for OLI Architecture, PLLC - an architecture firm in New York.
You help OLI team members find information in project documents, specifications, drawings, and construction records.

## YOUR ROLE:
- Search and summarize information from OLI's project documents
- Help locate specific details, specifications, or drawing references
- Assist with understanding project requirements and specifications
- Support RFI and submittal response drafting

## DOCUMENTS FROM PROJECT FILES:
{context}

## RESPONSE GUIDELINES:
- Be concise and professional - match OLI's communication style
- Always cite the specific document/drawing where you found information
- Use bullet points for clarity
- Reference spec section numbers when applicable (e.g., "Per Section 033000...")
- If information is not in the documents, say "I couldn't find that in the indexed project files"
- Do NOT make up information or reference external codes unless asked

## KEY PROJECT CONSULTANTS:
- Structural: LERA Engineering
- MEP: CES Consulting Engineering Services
- Lighting: HLB Lighting Design"""
    else:
        system_prompt = """You are an assistant for OLI Architecture, PLLC.
No project documents are currently indexed. Please ensure the shared folder is configured and indexed, 
or try searching with different terms."""
    
    # Build conversation history for context
    conversation = "\n".join([
        f"{msg['role'].upper()}: {msg['content']}"
        for msg in history[-5:]  # Last 5 messages for context
    ])
    
    # Get AI response
    try:
        # Use a simple prompt structure
        full_prompt = f"{system_prompt}\n\nConversation:\n{conversation}\n\nAssistant:"
        
        # Generate response using configured AI provider
        response_text = await _generate_response(full_prompt)
        
    except Exception as e:
        response_text = f"I apologize, but I encountered an error generating a response: {str(e)}"
    
    # Add assistant response to history
    timestamp = datetime.utcnow().isoformat()
    history.append({
        "role": "assistant",
        "content": response_text,
        "timestamp": timestamp,
        "sources": sources,
    })
    
    # Keep history manageable
    if len(history) > 50:
        _sessions[session_id] = history[-50:]
    
    return ChatResponse(
        content=response_text,
        session_id=session_id,
        sources=sources,
        timestamp=timestamp,
    )


@router.get("/history/{session_id}")
async def get_history(session_id: str):
    """Get conversation history for a session."""
    if session_id not in _sessions:
        return {"messages": []}
    
    return {"messages": _sessions[session_id]}


@router.delete("/history/{session_id}")
async def clear_history(session_id: str):
    """Clear conversation history for a session."""
    if session_id in _sessions:
        del _sessions[session_id]
    return {"status": "cleared"}


async def _generate_response(prompt: str) -> str:
    """Generate a chat response using the configured AI provider."""
    try:
        if settings.ai_provider == "gemini":
            return await _generate_gemini_response(prompt)
        elif settings.ai_provider == "claude":
            return await _generate_claude_response(prompt)
        elif settings.ai_provider == "ollama":
            return await _generate_ollama_response(prompt)
        else:
            return f"Unknown AI provider: {settings.ai_provider}"
    except Exception as e:
        return f"Unable to generate response: {str(e)}"


async def _generate_gemini_response(prompt: str) -> str:
    """Generate response using Google Gemini."""
    from google import genai
    from google.genai import types
    
    client = genai.Client(api_key=settings.gemini_api_key)
    model_name = settings.gemini_model
    if not model_name.startswith("models/"):
        model_name = f"models/{model_name}"
    
    response = client.models.generate_content(
        model=model_name,
        contents=prompt,
        config=types.GenerateContentConfig(
            temperature=0.7,
            top_p=0.95,
        )
    )
    return response.text


async def _generate_claude_response(prompt: str) -> str:
    """Generate response using Claude."""
    import anthropic
    
    client = anthropic.Anthropic(api_key=settings.claude_api_key)
    
    response = client.messages.create(
        model=settings.claude_model,
        max_tokens=2048,
        messages=[{"role": "user", "content": prompt}]
    )
    return response.content[0].text


async def _generate_ollama_response(prompt: str) -> str:
    """Generate response using Ollama."""
    import httpx
    
    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.post(
            f"{settings.ollama_base_url}/api/generate",
            json={
                "model": settings.ollama_model,
                "prompt": prompt,
                "stream": False,
            }
        )
        response.raise_for_status()
        data = response.json()
        return data.get("response", "")
