"""
Chat API endpoints for conversational Q&A.

Provides endpoints for chat-based interaction with the knowledge base,
allowing users to ask questions about projects and get AI-powered responses.
"""

import re
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
    suggested_queries: list[str] = []


# In-memory session storage (in production, use Redis or database)
_sessions: dict[str, list[dict]] = {}


def _extract_search_terms(query: str) -> list[str]:
    """Extract meaningful search terms from a natural language query."""
    # Common project name patterns
    query_lower = query.lower()
    
    # Remove common filler words
    stopwords = {
        'find', 'show', 'get', 'where', 'is', 'the', 'a', 'an', 'for', 
        'of', 'in', 'on', 'at', 'to', 'from', 'with', 'about', 'what',
        'latest', 'recent', 'all', 'any', 'some', 'me', 'please', 'can',
        'you', 'i', 'want', 'need', 'looking', 'search', 'look'
    }
    
    # Extract meaningful words
    words = re.findall(r'\b[a-zA-Z0-9]+\b', query)
    meaningful = [w for w in words if w.lower() not in stopwords and len(w) > 1]
    
    # Also look for quoted phrases
    quoted = re.findall(r'"([^"]+)"', query)
    
    # Look for project codes (e.g., "POT", "DBM", "KQ")
    codes = re.findall(r'\b[A-Z]{2,4}\b', query)
    
    # Combine all search terms
    terms = list(set(meaningful + quoted + codes))
    return terms


def _score_file_relevance(filename: str, content: str, search_terms: list[str]) -> float:
    """Score how relevant a file is to the search terms."""
    score = 0.0
    filename_lower = filename.lower()
    content_lower = content.lower() if content else ""
    
    for term in search_terms:
        term_lower = term.lower()
        # Filename matches are worth more
        if term_lower in filename_lower:
            score += 3.0
        # Content matches
        if content_lower:
            count = content_lower.count(term_lower)
            score += min(count * 0.5, 2.0)  # Cap per-term content score
    
    return score


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
    
    # Extract search terms for better matching
    search_terms = _extract_search_terms(message.content)
    
    # Search for relevant context
    sources = []
    context = ""
    suggested_queries = []
    
    if message.project_id:
        # Search within project
        project = db.query(Project).filter(Project.id == message.project_id).first()
        if not project:
            raise HTTPException(status_code=404, detail="Project not found")
        
        # Use knowledge base for semantic search
        kb = get_knowledge_base(message.project_id)
        if kb and project.kb_indexed:
            search_results = kb.search_with_context(message.content, n_results=8)
            if search_results:
                # Score and sort by relevance
                scored_results = []
                for r in search_results:
                    score = _score_file_relevance(
                        r.get('source', ''), 
                        r.get('text', ''), 
                        search_terms
                    )
                    scored_results.append((score + r.get('score', 0), r))
                
                scored_results.sort(key=lambda x: x[0], reverse=True)
                
                for _, r in scored_results[:5]:
                    text = r.get('text', '')[:2500]
                    context += f"\n\n---\n**Document:** {r['source']}\n**Section:** {r.get('section', 'N/A')}\n\n{text}\n---"
                    sources.append({
                        "filename": r["source"],
                        "section": r.get("section"),
                        "relevance": r.get("score", 0),
                    })
    else:
        # Global search using metadata index (lightweight, no file parsing)
        index = get_metadata_index()
        
        # Try multiple search strategies
        all_results = []
        
        # 1. Search by each extracted term
        for term in search_terms[:5]:  # Limit terms
            results = index.search(term, limit=10)
            all_results.extend(results)
        
        # 2. Search by full query
        results = index.search(message.content, limit=10)
        all_results.extend(results)
        
        # 3. Wildcard search if nothing found
        if not all_results:
            all_results = index.search("*", limit=30)
        
        # Deduplicate by path
        seen_paths = set()
        unique_results = []
        for r in all_results:
            if r["path"] not in seen_paths:
                seen_paths.add(r["path"])
                unique_results.append(r)
        
        # Score based on filename matching only (fast, no file parsing)
        scored_results = []
        for result in unique_results[:20]:
            score = _score_file_relevance(result["filename"], "", search_terms)
            if score > 0:
                scored_results.append((score, result))
        
        # Sort by score
        scored_results.sort(key=lambda x: x[0], reverse=True)
        
        # Take top results - include metadata without parsing content
        for score, result in scored_results[:8]:
            context += f"\n\n---\n**File:** {result['filename']}\n**Type:** {result.get('file_type', 'unknown')}\n**Path:** {result['path']}\n**Modified:** {result.get('modified_date', 'N/A')}\n---"
            sources.append({
                "filename": result["filename"],
                "path": result["path"],
                "type": result.get("file_type"),
                "relevance": score,
            })
        
        # Generate suggested queries if few results
        if len(sources) < 3:
            suggested_queries = [
                "Show all recent RFIs",
                "Find door detail drawings",
                "Search for specifications",
            ]
    
    # Build enhanced system prompt
    if context:
        system_prompt = f"""You are "Ask OLI" - an AI assistant for OLI Architecture, PLLC, an architecture firm based in New York.

## YOUR CAPABILITIES:
- Search and summarize information from OLI's project documents
- Locate specific details, specifications, drawing references, and project information
- Help understand project requirements, consultant comments, and construction records
- Assist with RFI and submittal response drafting

## IMPORTANT GUIDELINES:

### Response Style:
- Be concise and professional - architects value brevity
- Use bullet points for lists of information
- Bold important terms, drawing numbers, and spec sections
- If you cite a source, reference it clearly (e.g., "per Drawing S-036" or "Section 033000")

### What to Do:
- Answer based ONLY on the documents provided below
- Always cite which document contains the information
- If multiple documents are relevant, synthesize the information
- For technical questions, note which consultant to contact (LERA for structural, CES for MEP, HLB for lighting)

### What NOT to Do:
- Do NOT make up information not in the documents
- Do NOT reference external codes or standards unless asked
- Do NOT provide generic advice - stick to the project documents
- If information isn't available, say "I couldn't find that in the indexed files. Try these searches: [suggestions]"

## KEY PROJECT CONSULTANTS:
- **Structural:** LERA Consulting Structural Engineers
- **MEP (Electrical/Mechanical/Plumbing):** CES Consulting Engineering Services  
- **Lighting Design:** HLB Lighting Design

## DOCUMENTS FROM PROJECT FILES:
{context}

Now answer the user's question based on these documents."""
    else:
        # For global search, we have file metadata but not content
        if sources:
            system_prompt = f"""You are "Ask OLI" - an AI assistant for OLI Architecture, PLLC.

## YOUR ROLE:
Help users find files across all projects using the metadata I've found.

## IMPORTANT:
- I searched the file index and found matching files (listed below)
- I can only see file names and paths, NOT the file contents
- List the files I found and suggest which ones might be relevant
- If they want to read the contents, they should open a specific project first

## FILES FOUND:
{context}

Present these results helpfully. Mention which files match their query and suggest opening the relevant project for more details."""
        else:
            system_prompt = """You are "Ask OLI" - an AI assistant for OLI Architecture, PLLC.

I couldn't find any relevant documents for your query. This might be because:
1. The shared folder hasn't been configured yet
2. The files haven't been indexed
3. The search terms didn't match any files

**Suggestions:**
- Check that the shared folder path is configured in Settings
- Try indexing the files if not done yet
- Try different search terms (project names, document types, etc.)

Let me know if you need help setting up the knowledge base."""
    
    # Build conversation history for context (keep recent context)
    recent_history = history[-6:]  # Keep last 6 messages for context
    conversation = ""
    for msg in recent_history:
        role = msg['role'].upper()
        content = msg['content'][:1000]  # Limit message length
        conversation += f"\n{role}: {content}"
    
    # Get AI response
    try:
        full_prompt = f"{system_prompt}\n\nConversation:{conversation}\n\nASSISTANT:"
        response_text = await _generate_response(full_prompt)
        
    except Exception as e:
        response_text = f"I encountered an error generating a response: {str(e)}"
    
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
        suggested_queries=suggested_queries,
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
