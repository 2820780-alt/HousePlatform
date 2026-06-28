from pydantic import BaseModel, Field


class ModuleVisibilityItem(BaseModel):
    moduleCode: str
    canonicalModuleCode: str
    title: str
    route: str | None = None
    icon: str | None = None
    accessLevel: str
    scope: str
    availableActions: list[str]
    visible: bool
    status: str
    featureCodes: list[str] = Field(default_factory=list)
    legacyModuleCodes: list[str] = Field(default_factory=list)
    activeRegionCode: str | None = None
