from crewai.tools import BaseTool
from pydantic import BaseModel, Field
from typing import Type, Dict, Any, List, Optional
import requests
import json
import math
import os


def _str(val: Any, default: Optional[str], max_len: int) -> Optional[str]:
    """Coerce to string for DB; return default if None, empty, or literal 'null'. Truncate to max_len."""
    if val is None:
        return default
    s = str(val).strip()
    if not s or s.lower() == "null":
        return default
    return s[:max_len] if len(s) > max_len else s


class ThesisArticleComparisonInput(BaseModel):
    """Input schema for Thesis Article Comparison Tool."""
    thesis_text: str = Field(..., description="The full text of the investment thesis")
    article_text: str = Field(..., description="The full text of an article to compare")
    openai_api_key: Optional[str] = Field(None, description="OpenAI API key (optional if set as environment variable)")
    relevance_threshold: float = Field(0.7, description="Score threshold for relevance (default 0.7)")

class ThesisArticleComparisonTool(BaseTool):
    """Tool for analyzing semantic similarity between investment thesis and articles using OpenAI embeddings."""

    name: str = "thesis_article_comparison_tool"
    description: str = (
        "Analyzes semantic similarity between investment thesis and articles using OpenAI embeddings "
        "and gpt-4o-mini. Returns a result shaped for supabase_write_evaluations: relevance_score, "
        "confidence_score, signal_type, exec_summary, why_it_matters, thesis_sector, focus_area_tags, "
        "geography, companies_mentioned. Judge adds url per article and passes the array to supabase_write_evaluations."
    )
    args_schema: Type[BaseModel] = ThesisArticleComparisonInput

    def _get_api_key(self, provided_key: Optional[str] = None) -> str:
        """Get OpenAI API key from parameter or environment variable."""
        if provided_key:
            return provided_key
        
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OpenAI API key must be provided either as parameter or OPENAI_API_KEY environment variable")
        
        return api_key

    def _chunk_text(self, text: str, max_tokens: int = 7000) -> List[str]:
        """Chunk text to handle token limits. Simple word-based chunking."""
        words = text.split()
        # Rough estimate: 1 token ≈ 0.75 words
        max_words = int(max_tokens * 0.75)
        
        if len(words) <= max_words:
            return [text]
        
        chunks = []
        current_chunk = []
        
        for word in words:
            if len(current_chunk) >= max_words:
                chunks.append(" ".join(current_chunk))
                current_chunk = []
            current_chunk.append(word)
        
        if current_chunk:
            chunks.append(" ".join(current_chunk))
        
        return chunks

    def _get_embeddings(self, texts: List[str], api_key: str) -> List[List[float]]:
        """Get embeddings for texts using OpenAI API."""
        url = "https://api.openai.com/v1/embeddings"
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "model": "text-embedding-3-small",
            "input": texts
        }
        
        try:
            response = requests.post(url, headers=headers, json=payload, timeout=30)
            response.raise_for_status()
            
            data = response.json()
            return [item["embedding"] for item in data["data"]]
            
        except requests.exceptions.RequestException as e:
            raise Exception(f"Error getting embeddings from OpenAI: {str(e)}")
        except KeyError as e:
            raise Exception(f"Unexpected response format from OpenAI embeddings API: {str(e)}")

    def _cosine_similarity(self, vec1: List[float], vec2: List[float]) -> float:
        """Calculate cosine similarity between two vectors."""
        try:
            # Calculate dot product
            dot_product = sum(a * b for a, b in zip(vec1, vec2))
            
            # Calculate magnitudes
            magnitude1 = math.sqrt(sum(a * a for a in vec1))
            magnitude2 = math.sqrt(sum(a * a for a in vec2))
            
            # Avoid division by zero
            if magnitude1 == 0 or magnitude2 == 0:
                return 0.0
            
            return dot_product / (magnitude1 * magnitude2)
            
        except Exception as e:
            raise Exception(f"Error calculating cosine similarity: {str(e)}")

    def _get_average_embedding(self, embeddings: List[List[float]]) -> List[float]:
        """Calculate average embedding from multiple embeddings."""
        if not embeddings:
            return []
        
        if len(embeddings) == 1:
            return embeddings[0]
        
        # Calculate average for each dimension
        embedding_size = len(embeddings[0])
        avg_embedding = []
        
        for i in range(embedding_size):
            avg_value = sum(emb[i] for emb in embeddings) / len(embeddings)
            avg_embedding.append(avg_value)
        
        return avg_embedding

    def _get_gpt4_analysis(self, thesis_text: str, article_text: str, similarity_score: float, api_key: str) -> Dict[str, Any]:
        """Use gpt-4o-mini to analyze relevance and provide reasoning."""
        url = "https://api.openai.com/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        
        prompt = f"""
You are an investment analyst. Analyze the relevance between this investment thesis and article.

INVESTMENT THESIS:
{thesis_text[:2000]}...

ARTICLE:
{article_text[:2000]}...

SEMANTIC SIMILARITY SCORE (0-1): {similarity_score:.3f}

Return exactly one JSON object with these keys only (no markdown, no explanation):
{{
  "exec_summary": "2-3 sentence executive summary of how the article relates to the thesis",
  "why_it_matters": "Why this is relevant for investment or market intelligence",
  "thesis_sector": "Thesis sector most relevant (e.g. women's health, care model) or null",
  "focus_area_tags": "Comma-separated tags (e.g. AI health, virtual health, funding)",
  "geography": "Geography if mentioned (e.g. US, EU) or null",
  "companies_mentioned": "Comma-separated company names if any, or empty string",
  "signal_type": "One of: direct_thesis_match, market_intelligence, other",
  "confidence_score": 85
}}

Use signal_type: direct_thesis_match for strong thesis alignment, market_intelligence for related market context, other otherwise.
"""
        
        payload = {
            "model": "gpt-4o-mini",
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.3,
            "max_tokens": 800
        }
        
        try:
            response = requests.post(url, headers=headers, json=payload, timeout=45)
            response.raise_for_status()
            
            data = response.json()
            content = data["choices"][0]["message"]["content"]
            
            # Extract JSON from response
            try:
                # Find JSON block in the response
                start_idx = content.find("{")
                end_idx = content.rfind("}") + 1
                
                if start_idx != -1 and end_idx > start_idx:
                    json_str = content[start_idx:end_idx]
                    return json.loads(json_str)
                else:
                    return self._default_gpt_response(content[:200] + "...", 70)
                    
            except json.JSONDecodeError:
                return self._default_gpt_response("Formatting error occurred", 60)
                
        except requests.exceptions.RequestException as e:
            raise Exception(f"Error getting gpt-4o-mini analysis: {str(e)}")

    def _default_gpt_response(self, exec_summary: str, confidence_score: int) -> Dict[str, Any]:
        """Default GPT response shape for fallbacks (matches Supabase insertion shape)."""
        return {
            "exec_summary": exec_summary,
            "why_it_matters": "",
            "thesis_sector": None,
            "focus_area_tags": "",
            "geography": None,
            "companies_mentioned": "",
            "signal_type": "market_intelligence",
            "confidence_score": confidence_score,
        }

    def _determine_recommendation(self, relevance_score: int, threshold: float) -> str:
        """Determine recommendation based on relevance score and threshold."""
        score_decimal = relevance_score / 100.0
        
        if score_decimal >= threshold:
            return "RELEVANT"
        elif score_decimal >= (threshold * 0.7):  # 70% of threshold
            return "WATCHLIST"
        else:
            return "REJECT"

    def _run(self, thesis_text: str, article_text: str, openai_api_key: Optional[str] = None, relevance_threshold: float = 0.7) -> str:
        """Analyze semantic similarity between thesis and article texts."""
        try:
            # Get API key
            api_key = self._get_api_key(openai_api_key)
            
            # Validate inputs
            if not thesis_text.strip():
                raise ValueError("Thesis text cannot be empty")
            
            if not article_text.strip():
                raise ValueError("Article text cannot be empty")
            
            if not 0.0 <= relevance_threshold <= 1.0:
                raise ValueError("Relevance threshold must be between 0.0 and 1.0")
            
            # Chunk texts if necessary
            thesis_chunks = self._chunk_text(thesis_text)
            article_chunks = self._chunk_text(article_text)
            
            # Get embeddings for all chunks
            all_texts = thesis_chunks + article_chunks
            embeddings = self._get_embeddings(all_texts, api_key)
            
            # Separate thesis and article embeddings
            thesis_embeddings = embeddings[:len(thesis_chunks)]
            article_embeddings = embeddings[len(thesis_chunks):]
            
            # Calculate average embeddings
            avg_thesis_embedding = self._get_average_embedding(thesis_embeddings)
            avg_article_embedding = self._get_average_embedding(article_embeddings)
            
            # Calculate cosine similarity
            similarity_coefficient = self._cosine_similarity(avg_thesis_embedding, avg_article_embedding)
            
            # Convert to percentage for relevance score
            relevance_score = int(similarity_coefficient * 100)
            
            # Get gpt-4o-mini analysis (returns exec_summary, why_it_matters, thesis_sector, etc.)
            gpt = self._get_gpt4_analysis(thesis_text, article_text, similarity_coefficient, api_key)

            # Build result to match supabase_write_evaluations (Judge adds url per article)
            focus = gpt.get("focus_area_tags")
            if isinstance(focus, list):
                focus = ", ".join(str(x) for x in focus) if focus else ""
            companies = gpt.get("companies_mentioned")
            if isinstance(companies, list):
                companies = ", ".join(str(x) for x in companies) if companies else ""

            result = {
                "relevance_score": relevance_score,
                "confidence_score": int(gpt.get("confidence_score", 70)),
                "signal_type": _str(gpt.get("signal_type"), "other", 128),
                "exec_summary": _str(gpt.get("exec_summary"), "", 8192),
                "why_it_matters": _str(gpt.get("why_it_matters"), "", 2048),
                "thesis_sector": _str(gpt.get("thesis_sector"), None, 512),
                "focus_area_tags": _str(focus, "", 2048),
                "geography": _str(gpt.get("geography"), None, 512),
                "companies_mentioned": _str(companies, "", 2048),
            }
            return json.dumps(result)

        except Exception as e:
            error_result = {
                "relevance_score": 0,
                "confidence_score": 0,
                "signal_type": "other",
                "exec_summary": f"Analysis failed: {str(e)}"[:500],
                "why_it_matters": "",
                "thesis_sector": None,
                "focus_area_tags": "",
                "geography": None,
                "companies_mentioned": "",
            }
            return json.dumps(error_result)