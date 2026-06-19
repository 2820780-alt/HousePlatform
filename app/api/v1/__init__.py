from fastapi import APIRouter

from app.api.v1 import (
    admin_material_hub,
    admin_materials,
    admin_moderation,
    admin_suppliers,
    auth,
    dev_material_hub,
    material_hub_view,
    price_dynamics_view,
    supplier_branches,
    supplier_profile,
    supplier_upload,
)

api_router = APIRouter()

api_router.include_router(auth.router)
api_router.include_router(admin_suppliers.router)
api_router.include_router(admin_material_hub.router)
api_router.include_router(admin_materials.router)
api_router.include_router(admin_moderation.router)
api_router.include_router(material_hub_view.router)
api_router.include_router(price_dynamics_view.router)
api_router.include_router(dev_material_hub.router)
api_router.include_router(supplier_profile.router)
api_router.include_router(supplier_branches.router)
api_router.include_router(supplier_upload.router)
