import asyncio
import uuid
from app.db.session import AsyncSessionLocal
from app.db.models import ServiceTemplate
from sqlalchemy import select

async def seed_templates():
    async with AsyncSessionLocal() as db:
        # Check if templates already exist
        result = await db.execute(select(ServiceTemplate))
        if result.scalars().first():
            print("Templates already exist. Skipping seed.")
            return

        templates = [
            ServiceTemplate(
                id=uuid.uuid4(),
                sector="Astrology",
                title="Personal Birth Chart Reading",
                description="Deep dive into your personality, career, and relationships using your exactly planetary positions.",
                suggested_price_inr=1999,
                question_form_template={
                    "fields": [
                        {"name": "birth_date", "label": "Date of Birth", "type": "date", "required": True},
                        {"name": "birth_time", "label": "Time of Birth", "type": "time", "required": True},
                        {"name": "birth_place", "label": "Place of Birth", "type": "geo", "required": True},
                        {"name": "focus", "label": "Focus Area", "type": "chips", "options": ["Career", "Marriage", "Health", "Money"], "required": True}
                    ]
                }
            ),
            ServiceTemplate(
                id=uuid.uuid4(),
                sector="Content Growth",
                title="Video Performance Audit",
                description="Stop guessing. Get a data-backed audit of your video performance, hook, and retention.",
                suggested_price_inr=1499,
                question_form_template={
                    "fields": [
                        {"name": "channel_link", "label": "Channel/Profile Link", "type": "link", "required": True},
                        {"name": "goal", "label": "Main Goal", "type": "chips", "options": ["Boost Views", "Fix Retention", "Better CTR", "Monetization"], "required": True},
                        {"name": "platform", "label": "Platform", "type": "chips", "options": ["YouTube", "Instagram", "LinkedIn", "Twitter/X"], "required": True},
                        {"name": "analytics_shot", "label": "Studio Screenshot (CTR/Retention)", "type": "image", "required": False}
                    ]
                }
            ),
            ServiceTemplate(
                id=uuid.uuid4(),
                sector="Healthcare",
                title="Dermatology Skin Consult",
                description="Get a preliminary assessment of skin concerns from a verified specialist.",
                suggested_price_inr=999,
                question_form_template={
                    "fields": [
                        {"name": "skin_photo", "label": "Photo of Concern Area", "type": "image", "required": True},
                        {"name": "skin_type", "label": "Skin Type", "type": "chips", "options": ["Dry", "Oily", "Combination", "Sensitive"], "required": True},
                        {"name": "duration", "label": "How long has this persisted?", "type": "select", "options": ["Days", "Weeks", "Months", "Years"], "required": True},
                        {"name": "medications", "label": "Current Meds/Allergies", "type": "text", "required": False}
                    ]
                }
            ),
            ServiceTemplate(
                id=uuid.uuid4(),
                sector="Startup Advice",
                title="1-on-1 Strategy Session",
                description="Practical, no-fluff advice for founders struggling with growth or product-market fit.",
                suggested_price_inr=4999,
                question_form_template={
                    "fields": [
                        {"name": "pitch_link", "label": "Pitch Deck or Website", "type": "link", "required": True},
                        {"name": "stage", "label": "Current Stage", "type": "chips", "options": ["Idea/MVP", "Pre-Seed", "Seed/Growth"], "required": True},
                        {"name": "struggle", "label": "Top Bottleneck", "type": "chips", "options": ["Hiring", "Fundraising", "PMF", "Sales"], "required": True},
                        {"name": "team_size", "label": "Current Team Size", "type": "select", "options": ["Solo", "2-5", "5-20", "20+"], "required": True}
                    ]
                }
            )
        ]

        db.add_all(templates)
        await db.commit()
        print(f"Successfully seeded {len(templates)} templates.")

if __name__ == "__main__":
    import os
    import sys
    # Add app to path
    sys.path.append(os.getcwd())
    asyncio.run(seed_templates())
