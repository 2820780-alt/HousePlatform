import enum


class UserRole(str, enum.Enum):
    ADMIN = "ADMIN"
    SUPPLIER = "SUPPLIER"
    CONTRACTOR = "CONTRACTOR"
    CUSTOMER = "CUSTOMER"


class UserStatus(str, enum.Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    BLOCKED = "blocked"


class SupplierStatus(str, enum.Enum):
    POTENTIAL = "potential"
    VERIFIED = "verified"
    PARTNER = "partner"
    PREMIUM = "premium"
    BLOCKED = "blocked"


class AccessStatus(str, enum.Enum):
    ACTIVE = "active"
    SUSPENDED = "suspended"
    REVOKED = "revoked"


class RegionStatus(str, enum.Enum):
    DRAFT = "DRAFT"
    ACTIVE = "ACTIVE"
    DISABLED = "DISABLED"
    ARCHIVED = "ARCHIVED"


class SourceType(str, enum.Enum):
    MANUFACTURER = "MANUFACTURER"
    RETAIL = "RETAIL"
    SUPPLIER = "SUPPLIER"
    MANUAL_UPLOAD = "MANUAL_UPLOAD"


class SourceStatus(str, enum.Enum):
    ACTIVE = "ACTIVE"
    PAUSED = "PAUSED"
    DISABLED = "DISABLED"
    ERROR = "ERROR"


class SourceActionType(str, enum.Enum):
    INITIAL_MATERIAL_SCAN = "INITIAL_MATERIAL_SCAN"
    UPDATE_PRICES = "UPDATE_PRICES"
    FIND_NEW_PRODUCTS = "FIND_NEW_PRODUCTS"
    UPDATE_SPECIFICATIONS = "UPDATE_SPECIFICATIONS"
    UPDATE_CERTIFICATES = "UPDATE_CERTIFICATES"
    UPDATE_TECH_DOCUMENTS = "UPDATE_TECH_DOCUMENTS"
    SCAN_TECHNOLOGIES = "SCAN_TECHNOLOGIES"
    FULL_INITIAL_SCAN = "FULL_INITIAL_SCAN"
    CHECK_SOURCE_HEALTH = "CHECK_SOURCE_HEALTH"
    UPLOAD_SUPPLIER_FILE = "UPLOAD_SUPPLIER_FILE"


class TaskStatus(str, enum.Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"
    NEEDS_REVIEW = "NEEDS_REVIEW"


class TaskLogLevel(str, enum.Enum):
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"


class TaskResultType(str, enum.Enum):
    CREATED = "CREATED"
    UPDATED = "UPDATED"
    UNCHANGED = "UNCHANGED"
    CONFLICT = "CONFLICT"
    NEW_PRODUCT_FOUND = "NEW_PRODUCT_FOUND"
    NEEDS_REVIEW = "NEEDS_REVIEW"
    ERROR = "ERROR"


class MaterialStatus(str, enum.Enum):
    DRAFT = "DRAFT"
    AUTO_CREATED = "AUTO_CREATED"
    NEEDS_REVIEW = "NEEDS_REVIEW"
    VERIFIED = "VERIFIED"
    REJECTED = "REJECTED"
    ARCHIVED = "ARCHIVED"


class VerificationStatus(str, enum.Enum):
    AUTO_EXTRACTED = "AUTO_EXTRACTED"
    NEEDS_REVIEW = "NEEDS_REVIEW"
    VERIFIED = "VERIFIED"
    REJECTED = "REJECTED"


class CatalogProductStatus(str, enum.Enum):
    ACTIVE = "ACTIVE"
    UNAVAILABLE = "UNAVAILABLE"
    NEW_PRODUCT_FOUND = "NEW_PRODUCT_FOUND"
    NEEDS_REVIEW = "NEEDS_REVIEW"
    REJECTED = "REJECTED"
    ARCHIVED = "ARCHIVED"


class DocumentType(str, enum.Enum):
    CERTIFICATE = "CERTIFICATE"
    DECLARATION = "DECLARATION"
    FIRE_CERTIFICATE = "FIRE_CERTIFICATE"
    SANITARY_CERTIFICATE = "SANITARY_CERTIFICATE"
    QUALITY_PASSPORT = "QUALITY_PASSPORT"
    TECH_CARD = "TECH_CARD"
    INSTALLATION_GUIDE = "INSTALLATION_GUIDE"
    TYPICAL_NODE = "TYPICAL_NODE"
    ALBUM_OF_SOLUTIONS = "ALBUM_OF_SOLUTIONS"
    BIM_MODEL = "BIM_MODEL"
    VIDEO_GUIDE = "VIDEO_GUIDE"
    TEST_REPORT = "TEST_REPORT"
    TECHNICAL_APPROVAL = "TECHNICAL_APPROVAL"


class DocumentStatus(str, enum.Enum):
    ACTIVE = "ACTIVE"
    EXPIRED = "EXPIRED"
    ARCHIVED = "ARCHIVED"
    REJECTED = "REJECTED"
    NEEDS_REVIEW = "NEEDS_REVIEW"


class MatchCandidateStatus(str, enum.Enum):
    OPEN = "OPEN"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    NEEDS_REVIEW = "NEEDS_REVIEW"


class AdminDecision(str, enum.Enum):
    KEEP_OLD = "KEEP_OLD"
    REPLACE_WITH_NEW = "REPLACE_WITH_NEW"
    KEEP_BOTH = "KEEP_BOTH"
    SEND_TO_REVIEW = "SEND_TO_REVIEW"
    REJECT_NEW = "REJECT_NEW"
    APPROVE = "APPROVE"
    REJECT = "REJECT"


class UploadFileType(str, enum.Enum):
    CSV = "CSV"
    XLSX = "XLSX"


class UploadStatus(str, enum.Enum):
    UPLOADED = "UPLOADED"
    PROCESSING = "PROCESSING"
    PROCESSED = "PROCESSED"
    PARTIALLY_PROCESSED = "PARTIALLY_PROCESSED"
    FAILED = "FAILED"


class UploadRowStatus(str, enum.Enum):
    EXTRACTED = "EXTRACTED"
    NORMALIZED = "NORMALIZED"
    MATCHED = "MATCHED"
    NEEDS_REVIEW = "NEEDS_REVIEW"
    ERROR = "ERROR"
    REJECTED = "REJECTED"


class UnitType(str, enum.Enum):
    LENGTH = "length"
    AREA = "area"
    VOLUME = "volume"
    WEIGHT = "weight"
    QUANTITY = "quantity"
    PACKAGE = "package"
