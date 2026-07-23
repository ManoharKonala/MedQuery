"""
Application configuration using Pydantic Settings.
Loads values from .env file automatically.
"""

from pydantic_settings import BaseSettings
from pydantic import Field


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # PostgreSQL
    db_host: str = Field(default="localhost", alias="DB_HOST")
    db_port: int = Field(default=5432, alias="DB_PORT")
    db_name: str = Field(default="medicalquery", alias="DB_NAME")
    db_user: str = Field(default="postgres", alias="DB_USER")
    db_password: str = Field(default="postgres", alias="DB_PASSWORD")

    # Google Gemini
    gemini_api_key: str = Field(default="", alias="GEMINI_API_KEY")

    # HuggingFace (Fallback LLM)
    hf_api_key: str = Field(default="", alias="HF_API_KEY")
    hf_model: str = Field(
        default="mistralai/Mistral-7B-Instruct-v0.2", alias="HF_MODEL"
    )

    # Models
    embedding_model: str = Field(default="all-MiniLM-L6-v2", alias="EMBEDDING_MODEL")
    reranker_model: str = Field(
        default="cross-encoder/ms-marco-MiniLM-L-6-v2", alias="RERANKER_MODEL"
    )

    # ChromaDB
    chroma_persist_dir: str = Field(default="./chroma_db", alias="CHROMA_PERSIST_DIR")

    # Uploads
    upload_dir: str = Field(default="./uploads", alias="UPLOAD_DIR")

    # CORS
    frontend_url: str = Field(
        default="http://localhost:5173", alias="FRONTEND_URL"
    )

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
