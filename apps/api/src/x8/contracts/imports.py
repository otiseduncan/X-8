from pydantic import BaseModel, Field


class ImportedConfigValue(BaseModel):
    name: str
    detected_provider: str
    value_present: bool
    redacted_preview: str
    recommended_xv8_env_name: str
    classification: str


class X7ImportReport(BaseModel):
    import_root: str
    files_discovered: list[str] = Field(default_factory=list)
    providers_discovered: list[str] = Field(default_factory=list)
    values: list[ImportedConfigValue] = Field(default_factory=list)
    missing_recommended_variables: list[str] = Field(default_factory=list)
    env_local_template: str = ""


class LegacySourceStatus(BaseModel):
    source_id: str
    source_path: str
    mount_path: str
    import_status: str
    files_found: int = 0
    configs_found: int = 0
    providers_found: list[str] = Field(default_factory=list)
    missing_paths: list[str] = Field(default_factory=list)


class LegacyConfigImportReport(BaseModel):
    x7_import_status: LegacySourceStatus
    x6_import_status: LegacySourceStatus
    x7_files_found: int = 0
    x6_files_found: int = 0
    x7_configs_found: int = 0
    x6_configs_found: int = 0
    providers_found: list[str] = Field(default_factory=list)
    secrets_detected_redacted: list[ImportedConfigValue] = Field(default_factory=list)
    missing_paths: list[str] = Field(default_factory=list)
    migration_recommendations: list[str] = Field(default_factory=list)
    x7_report: X7ImportReport
    x6_report: X7ImportReport
