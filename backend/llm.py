"""
Multi-Tier LLM Answer Synthesis Module with Graceful Fallbacks.

3-Tier Architecture:
  1. Primary: Google Gemini (gemini-1.5-flash)
  2. Fallback Tier 1: Hugging Face Serverless Inference API (Mistral-7B-Instruct)
  3. Fallback Tier 2: Extractive Retrieval Fallback (Zero external API dependencies)
"""

import re
import json
import requests
import google.generativeai as genai
from config import settings


def _build_rag_prompt(
    query: str,
    chunks: list[dict],
    chat_history: list[dict] = None,
) -> str:
    """Build the RAG prompt with system instructions, context chunks, and query."""
    system = (
        "You are a helpful Medical Document Assistant. "
        "Answer the user's question based ONLY on the provided source documents. "
        "If the information is not in the sources, say 'I don't have enough information to answer this.' "
        "ALWAYS cite your sources using [Source N] tags after every factual statement. "
        "Be precise, professional, and concise."
    )

    sources_text = "\n\n"
    for i, chunk in enumerate(chunks):
        source_label = f"[Source {i + 1}"
        if chunk.get("metadata", {}).get("document_title"):
            source_label += f": {chunk['metadata']['document_title']}"
        if chunk.get("metadata", {}).get("page_number"):
            source_label += f" (Page {chunk['metadata']['page_number']})"
        source_label += "]"
        sources_text += f"{source_label}\n{chunk['text']}\n\n"

    history_text = ""
    if chat_history:
        history_text = "\n\nRecent conversation:\n"
        for msg in chat_history[-6:]:
            role = "User" if msg["role"] == "user" else "Assistant"
            history_text += f"{role}: {msg['content']}\n"

    prompt = f"""{system}

--- SOURCE DOCUMENTS ---
{sources_text}
--- END SOURCES ---
{history_text}
User Question: {query}

Answer (with [Source N] citations):"""

    return prompt


def _parse_citations(answer: str, chunks: list[dict]) -> list[dict]:
    """Extract and validate [Source N] citations from the LLM response."""
    pattern = r"\[Source\s+(\d+)\]"
    matches = re.findall(pattern, answer)
    cited_indices = set(int(m) for m in matches)

    # Fallback: if answer is short and no explicit citations were matched, include all top chunks
    if not cited_indices and chunks:
        cited_indices = set(range(1, min(len(chunks) + 1, 4)))

    citations = []
    for idx in sorted(cited_indices):
        if 1 <= idx <= len(chunks):
            chunk = chunks[idx - 1]
            metadata = chunk.get("metadata", {})
            citations.append({
                "source_index": idx,
                "document_title": metadata.get("document_title", "Unknown"),
                "document_id": metadata.get("document_id", ""),
                "page_number": metadata.get("page_number"),
                "snippet": chunk["text"][:200] + "..." if len(chunk["text"]) > 200 else chunk["text"],
            })

    return citations


# ─── TIER 1: Google Gemini ──────────────────────────────────────────

def _call_gemini(prompt: str) -> str:
    """Primary LLM call to Google Gemini API."""
    if not settings.gemini_api_key or settings.gemini_api_key == "your_gemini_api_key_here":
        raise ValueError("Gemini API key is not configured.")

    genai.configure(api_key=settings.gemini_api_key)
    model = genai.GenerativeModel("gemini-1.5-flash")
    response = model.generate_content(prompt)
    
    if not response or not response.text:
        raise ValueError("Empty response received from Gemini API.")
        
    return response.text.strip()


# ─── TIER 2: Hugging Face Mistral Inference API ──────────────────────

def _call_huggingface_mistral(prompt: str) -> str:
    """Fallback Tier 1 LLM call to Hugging Face Serverless Inference API (Mistral-7B)."""
    headers = {}
    if settings.hf_api_key and settings.hf_api_key != "your_huggingface_api_key_here":
        headers["Authorization"] = f"Bearer {settings.hf_api_key}"

    # Try router API endpoint first, fallback to model inference endpoint
    api_urls = [
        f"https://router.huggingface.co/hf-inference/v1/chat/completions",
        f"https://api-inference.huggingface.co/models/{settings.hf_model}",
    ]

    payload = {
        "inputs": prompt,
        "parameters": {
            "max_new_tokens": 512,
            "temperature": 0.3,
            "return_full_text": False,
        },
    }

    last_error = None
    for url in api_urls:
        try:
            res = requests.post(url, headers=headers, json=payload, timeout=15)
            if res.status_code == 200:
                data = res.json()
                if isinstance(data, list) and len(data) > 0:
                    generated = data[0].get("generated_text", "")
                    if generated:
                        return generated.strip()
                elif isinstance(data, dict):
                    if "choices" in data and len(data["choices"]) > 0:
                        return data["choices"][0].get("message", {}).get("content", "").strip()
                    elif "generated_text" in data:
                        return data["generated_text"].strip()
            else:
                last_error = f"HF HTTP {res.status_code}: {res.text[:200]}"
        except Exception as err:
            last_error = str(err)

    raise ValueError(f"HuggingFace Mistral call failed: {last_error}")


# ─── TIER 3: Local Extractive Retrieval Fallback ────────────────────

def _generate_extractive_fallback(query: str, chunks: list[dict]) -> str:
    """Fallback Tier 2: Local extractive synthesis from top retrieved chunks.

    Guarantees that an answer is ALWAYS produced locally with zero external API calls.
    """
    answer_lines = [
        "*(Note: Generated via Extractive Document Summary — LLM APIs unavailable)*\n",
        f"Key relevant sections found for **\"{query}\"**:\n",
    ]

    for i, chunk in enumerate(chunks[:3]):
        doc_title = chunk.get("metadata", {}).get("document_title", "Document")
        page_num = chunk.get("metadata", {}).get("page_number")
        page_info = f" (Page {page_num})" if page_num else ""
        
        answer_lines.append(
            f"**[Source {i + 1}: {doc_title}{page_info}]**\n{chunk['text'].strip()}\n"
        )

    return "\n".join(answer_lines)


# ─── MAIN ENTRY POINT (3-TIER CASCADE) ─────────────────────────────

def generate_answer(
    query: str,
    chunks: list[dict],
    chat_history: list[dict] = None,
) -> dict:
    """Generate an answer with RAG context using 3-Tier Fallback Cascade.

    Flow:
      Try Gemini API  ──(error)──► Try HF Mistral API  ──(error)──► Extractive Summary

    Returns:
        dict with keys: answer, sources
    """
    if not chunks:
        return {
            "answer": "I don't have enough information to answer this question. Please upload relevant medical documents first.",
            "sources": [],
        }

    prompt = _build_rag_prompt(query, chunks, chat_history)
    answer = None
    tier_used = "Gemini (Primary)"

    # --- Tier 1: Gemini ---
    try:
        print("[LLM] Attempting Tier 1 (Gemini)...")
        answer = _call_gemini(prompt)
        print("[LLM] Tier 1 (Gemini) succeeded.")
    except Exception as e_gemini:
        print(f"[LLM] Tier 1 (Gemini) failed: {e_gemini}")
        
        # --- Tier 2: Hugging Face Mistral ---
        try:
            print("[LLM] Attempting Tier 2 (HuggingFace Mistral)...")
            answer = _call_huggingface_mistral(prompt)
            tier_used = "HuggingFace Mistral (Fallback 1)"
            print("[LLM] Tier 2 (HuggingFace Mistral) succeeded.")
        except Exception as e_hf:
            print(f"[LLM] Tier 2 (HuggingFace Mistral) failed: {e_hf}")

            # --- Tier 3: Local Extractive Fallback ---
            print("[LLM] Using Tier 3 (Extractive Summary Fallback)...")
            answer = _generate_extractive_fallback(query, chunks)
            tier_used = "Extractive Retrieval (Fallback 2)"

    # Parse and validate citations
    sources = _parse_citations(answer, chunks)

    return {
        "answer": answer,
        "sources": sources,
        "tier": tier_used,
    }
