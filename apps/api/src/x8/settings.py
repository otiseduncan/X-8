from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="X8_", extra="ignore", protected_namespaces=("settings_",))

    env: str = "development"
    database_url: str = Field("postgresql+psycopg://x8:x8_dev_password@x8-postgres:5432/x8", validation_alias="DATABASE_URL")
    redis_url: str = Field("redis://x8-redis:6379/0", validation_alias="REDIS_URL")
    ollama_mode: str = "host_ollama_bridge"
    ollama_base_url: str = Field("http://host.docker.internal:11434", validation_alias=AliasChoices("X8_OLLAMA_BASE_URL", "OLLAMA_BASE_URL"))
    default_chat_model: str = "qwen3:8b"
    reasoning_model: str = "qwen3:14b"
    fallback_chat_model: str = "qwen3:1.7b"
    code_model: str = "qwen3:14b"
    fast_model: str = "qwen3:1.7b"
    embedding_model: str = "nomic-embed-text:latest"
    model_health_prompt: str = "Reply with XV8_READY only."
    memory_enabled: bool = True
    memory_activation_mode: str = "ready_when_chat_model_and_embedding_ready"
    embedding_required_for_memory: bool = True
    embedding_required_for_basic_chat: bool = False
    vector_collection_memory: str = "x8_memory"
    vector_collection_knowledge: str = "x8_knowledge"
    vector_collection_project: str = "x8_project"
    memory_storage_path: str = "/app/runtime/memory/memory-records.json"
    context_max_messages: int = 20
    context_max_attachment_chars: int = 12000
    context_max_memory_items: int = 20
    context_max_knowledge_items: int = 20
    attachment_max_mb: int = 10
    attachment_storage_path: str = "/app/runtime/attachments"
    attachment_allowed_extensions: str = ".txt,.md,.json,.yaml,.yml,.csv,.log,.py,.js,.ts,.tsx,.jsx,.html,.css,.png,.jpg,.jpeg,.webp,.pdf"
    knowledge_root: str = "/app/knowledge"
    workspace_root: str = "/workspace"
    local_bridge_url: str = "http://x8-local-bridge:5788"
    local_bridge_token: str = ""
    approved_project_roots: str = ""
    x7_import_root: str = "/imports/x7"
    x6_import_root: str = "/imports/x6"
    web_search_provider: str = "searxng_local"
    searxng_base_url: str = "http://x8-searxng:8080"
    brave_search_api_key: str = ""
    serpapi_api_key: str = ""
    tavily_api_key: str = ""
    bing_search_api_key: str = ""
    image_default_provider: str = "comfyui"
    comfyui_base_url: str = "http://x8-comfyui:8188"
    comfyui_model_dir: str = "/models/checkpoints"
    comfyui_workflow_dir: str = "/workflows"
    comfyui_output_dir: str = "/outputs"
    image_default_model: str = "juggernaut"
    docker_preset_workdir: str = "/workspace"
    speech_enabled: bool = True
    speech_default_provider: str = "google"
    speech_default_locale: str = "en-US"
    speech_default_gender: str = "female"
    speech_default_voice: str = "Google US English Female"
    google_tts_api_key: str = ""
    google_application_credentials: str = ""
    google_cloud_project: str = ""
    github_token: str = Field("", validation_alias=AliasChoices("X8_GITHUB_TOKEN", "GITHUB_TOKEN"))
    github_owner: str = Field("otiseduncan", validation_alias=AliasChoices("X8_GITHUB_OWNER", "GITHUB_OWNER"))
    github_repo: str = Field("X-8", validation_alias=AliasChoices("X8_GITHUB_REPO", "GITHUB_REPO"))
    github_default_branch: str = Field("main", validation_alias=AliasChoices("X8_GITHUB_DEFAULT_BRANCH", "GITHUB_DEFAULT_BRANCH"))
    cors_origins: list[str] = ["http://localhost:5173", "http://127.0.0.1:5173"]
