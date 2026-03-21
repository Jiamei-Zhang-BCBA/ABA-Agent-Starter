"""
Seed script — creates initial plan, tenant, and admin user for development.
Run: python -m scripts.seed
"""

import asyncio
import uuid

from sqlalchemy import select

from app.database import async_session, engine, Base
from app.models.tenant import Plan, Tenant
from app.models.user import User, UserRole
from app.services.auth_service import hash_password
from app.core.plan_config import PLAN_CONFIGS


async def seed():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with async_session() as db:
        # Check if already seeded
        result = await db.execute(select(Plan).limit(1))
        if result.scalar_one_or_none():
            print("Database already seeded. Skipping.")
            return

        # Create plans
        plans = {}
        for name, config in PLAN_CONFIGS.items():
            plan = Plan(
                name=name,
                features_json={"features": config.features if isinstance(config.features, list) else config.features},
                max_clients=config.max_clients,
                max_staff=config.max_staff,
                monthly_jobs=config.monthly_jobs,
                price_cents=config.price_cents,
            )
            db.add(plan)
            await db.flush()
            plans[name] = plan
            print(f"Created plan: {name}")

        # Create demo tenant with enterprise plan
        tenant = Tenant(
            name="演示机构",
            plan_id=plans["enterprise"].id,
            settings_json={"language": "zh-CN"},
        )
        db.add(tenant)
        await db.flush()
        print(f"Created tenant: {tenant.name} (id: {tenant.id})")

        # Create demo users
        demo_users = [
            ("管理员", "admin@demo.com", UserRole.ORG_ADMIN),
            ("张督导", "bcba@demo.com", UserRole.BCBA),
            ("小李老师", "teacher@demo.com", UserRole.TEACHER),
            ("兜兜妈妈", "parent@demo.com", UserRole.PARENT),
        ]

        for name, email, role in demo_users:
            user = User(
                tenant_id=tenant.id,
                role=role.value,
                name=name,
                email=email,
                password_hash=hash_password("demo123"),
            )
            db.add(user)
            print(f"Created user: {name} ({email}) role={role.value}")

        await db.commit()
        print("\nSeed complete! Login with any demo user, password: demo123")


if __name__ == "__main__":
    asyncio.run(seed())
