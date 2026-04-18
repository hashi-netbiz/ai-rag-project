from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # LLM
    groq_api_key: str = ""

    # Embeddings
    google_api_key: str = ""

    # Vector Store
    pinecone_api_key: str = ""
    pinecone_index_name: str = "rag-rbac-chatbot"

    # Auth
    jwt_secret_key: str = "dev-secret-change-in-production"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 60

    # Observability
    langchain_api_key: str = ""
    langchain_tracing_v2: str = "false"
    langchain_project: str = "rag-rbac-chatbot"

    # CORS
    allowed_origins: str = "http://localhost:3000,http://localhost:3001"

    # Guardrails — Input
    guardrail_max_query_length: int = 500
    guardrail_injection_block: bool = True
    guardrail_pii_sanitize: bool = True

    # Guardrails — Context
    guardrail_relevance_threshold: float = 0.0  # 0.0 = disabled; set to e.g. 0.1 to enable

    # Guardrails — Output
    guardrail_max_response_length: int = 2000
    guardrail_min_answer_length_faithfulness: int = 50


settings = Settings()
