# -*- coding: utf-8 -*-
"""
Database Initialization Script

Initializes prompt templates in the database.
Run this script after deployment or to reset templates.

Usage:
    python -m scripts.init_templates

Or from backend directory:
    python scripts/init_templates.py
"""
import os
import sys
from datetime import datetime

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pymongo import MongoClient


def init_templates(db):
    """Initialize default templates in the database"""
    from app.core.summarization.defaults import get_default_templates
    from app.models.prompt_template import PromptTemplateModel

    templates = get_default_templates()
    inserted = 0
    skipped = 0
    updated = 0

    for template_data in templates:
        name = template_data["name"]

        # Check if exists
        existing = db.prompt_templates.find_one({"name": name})

        if existing:
            if existing.get("is_system"):
                # Update system template to latest version
                now = datetime.utcnow()
                template_data["updated_at"] = now
                template_data["version"] = existing.get("version", 1) + 1
                template_data["created_at"] = existing.get("created_at", now)

                db.prompt_templates.replace_one(
                    {"_id": existing["_id"]},
                    template_data
                )
                updated += 1
                print(f"  Updated: {name} (v{template_data['version']})")
            else:
                skipped += 1
                print(f"  Skipped: {name} (user-modified)")
        else:
            # Insert new
            now = datetime.utcnow()
            template_data["created_at"] = now
            template_data["updated_at"] = now
            template_data["version"] = 1

            db.prompt_templates.insert_one(template_data)
            inserted += 1
            print(f"  Inserted: {name}")

    # Ensure indexes
    model = PromptTemplateModel(db)
    model.ensure_indexes()
    print("  Indexes created")

    return {
        "inserted": inserted,
        "updated": updated,
        "skipped": skipped,
        "total": len(templates)
    }


def main():
    """Main entry point"""
    print("=" * 50)
    print("Prompt Templates Initialization")
    print("=" * 50)

    # Get MongoDB connection
    mongo_uri = os.getenv("MONGO_URI", "mongodb://localhost:27017")
    mongo_db = os.getenv("MONGO_DB", "podcast")

    print(f"\nConnecting to: {mongo_uri}")
    print(f"Database: {mongo_db}")

    try:
        client = MongoClient(mongo_uri)
        db = client[mongo_db]

        # Test connection
        db.command("ping")
        print("Connected successfully!\n")

    except Exception as e:
        print(f"Failed to connect: {e}")
        sys.exit(1)

    print("Initializing templates...")
    result = init_templates(db)

    print("\n" + "=" * 50)
    print("Summary:")
    print(f"  Inserted: {result['inserted']}")
    print(f"  Updated:  {result['updated']}")
    print(f"  Skipped:  {result['skipped']}")
    print(f"  Total:    {result['total']}")
    print("=" * 50)

    # List all templates
    print("\nCurrent templates in database:")
    for t in db.prompt_templates.find({"is_active": True}).sort("name", 1):
        system = "[SYSTEM]" if t.get("is_system") else "[USER]"
        print(f"  {system} {t['name']}: {t.get('display_name', '')} (v{t.get('version', 1)})")

    client.close()


if __name__ == "__main__":
    main()
