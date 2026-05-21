# -*- coding: utf-8 -*-
"""
Automated Tests for Summary Generation Flow

Tests:
1. Template loading validation
2. Prompt building validation
3. Field mapping validation
4. API response format validation
"""
import os
import sys
import json
from datetime import datetime
import pytest

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

from pymongo import MongoClient
from bson import ObjectId

pytestmark = pytest.mark.skipif(
    os.getenv("RUN_MONGO_TESTS", "0").lower() not in ("1", "true", "yes", "on"),
    reason="Requires a real MongoDB with initialized prompt templates. Set RUN_MONGO_TESTS=1 to run.",
)


def get_db():
    """Get database connection"""
    mongo_uri = os.getenv("MONGO_URI", "mongodb://localhost:27017")
    mongo_db = os.getenv("MONGO_DB", "podcast")
    client = MongoClient(mongo_uri)
    return client[mongo_db]


def test_templates_loaded():
    """Test 1: Verify templates loaded in database"""
    print("=" * 60)
    print("Test 1: Template Loading Validation")
    print("=" * 60)

    db = get_db()
    templates = list(db.prompt_templates.find({"is_active": True}).sort("name", 1))

    expected_templates = ["learning", "investment", "tech", "startup", "interview", "general"]
    found_names = [t["name"] for t in templates]

    print(f"\nExpected: {expected_templates}")
    print(f"Found: {found_names}")

    all_pass = True
    for name in expected_templates:
        if name in found_names:
            tmpl = next(t for t in templates if t["name"] == name)
            print(f"\n[PASS] {name}:")
            print(f"   - display_name: {tmpl.get('display_name')}")
            print(f"   - optional_blocks: {len(tmpl.get('optional_blocks', []))} blocks")
            print(f"   - parameters: {list(tmpl.get('parameters', {}).keys())}")
        else:
            print(f"\n[FAIL] {name}: NOT FOUND")
            all_pass = False

    return all_pass


def test_field_mapping():
    """Test 2: Verify template field mapping"""
    print("\n" + "=" * 60)
    print("Test 2: Field Mapping Validation")
    print("=" * 60)

    db = get_db()

    template_expected_fields = {
        "learning": ["tldr", "tags", "core_content", "guest_background", "key_concepts", "key_points", "examples", "action_items", "resources"],
        "investment": ["tldr", "tags", "core_content", "investment_signals", "mentioned_tickers", "market_insights", "risk_alerts", "key_points"],
        "tech": ["tldr", "tags", "core_content", "technologies", "product_insights", "tech_trends", "key_points", "examples"],
        "startup": ["tldr", "tags", "core_content", "guest_background", "business_model", "growth_tactics", "lessons_learned", "key_points", "action_items"],
        "interview": ["tldr", "tags", "core_content", "guest_background", "life_lessons", "controversial_views", "unique_insights", "key_points", "key_quotes"],
    }

    all_pass = True

    for tmpl_name, expected_fields in template_expected_fields.items():
        template = db.prompt_templates.find_one({"name": tmpl_name, "is_active": True})
        if not template:
            print(f"\n[FAIL] {tmpl_name}: Template not found")
            all_pass = False
            continue

        # Extract actual fields from blocks
        actual_fields = ["tldr", "tags"]
        for block in template.get("optional_blocks", []):
            output_field = block.get("output_field", {})
            key = output_field.get("key")
            if key:
                actual_fields.append(key)

        missing = set(expected_fields) - set(actual_fields)
        extra = set(actual_fields) - set(expected_fields)

        if missing or extra:
            print(f"\n[WARN] {tmpl_name}:")
            if missing:
                print(f"   Missing: {missing}")
            if extra:
                print(f"   Extra: {extra}")
            all_pass = False
        else:
            print(f"\n[PASS] {tmpl_name}: {len(actual_fields)} fields")

    return all_pass


def test_prompt_structure():
    """Test 3: Verify Prompt building logic"""
    print("\n" + "=" * 60)
    print("Test 3: Prompt Building Validation")
    print("=" * 60)

    db = get_db()

    from app.core.summarization.prompt_builder import PromptBuilder

    builder = PromptBuilder()

    test_template = "learning"
    template = db.prompt_templates.find_one({"name": test_template, "is_active": True})

    if not template:
        print(f"[FAIL] Template {test_template} not found")
        return False

    print(f"\nTemplate: {test_template}")

    # Get default enabled blocks
    default_blocks = [
        b["id"] for b in template.get("optional_blocks", [])
        if b.get("enabled_by_default", False)
    ]
    print(f"   Default blocks: {default_blocks}")

    # Build test messages
    test_transcript = "This is a test podcast transcript about AI and machine learning."
    try:
        messages = builder.build(
            template=template,
            transcript=test_transcript,
            enabled_blocks=None,
            title="Test Episode",
            guest="Test Guest"
        )

        print(f"\n[PASS] Prompt built successfully")
        print(f"   Messages: {len(messages)}")

        # Verify system message
        system_msg = messages[0]
        print(f"   System prompt: {len(system_msg['content'])} chars")

        # Verify user message
        user_msg = messages[1]
        user_content = user_msg["content"]

        required_parts = ["Test Episode", "Test Guest", "JSON", "transcript"]
        for part in required_parts:
            if part in user_content or part.lower() in user_content.lower():
                print(f"   [PASS] Contains: {part}")
            else:
                print(f"   [FAIL] Missing: {part}")
                return False

        return True

    except Exception as e:
        print(f"[FAIL] Prompt building failed: {e}")
        return False


def test_summary_api_format():
    """Test 4: Verify API response format"""
    print("\n" + "=" * 60)
    print("Test 4: API Response Format Validation")
    print("=" * 60)

    db = get_db()

    summary = db.summaries.find_one({"template_name": {"$exists": True}})

    if not summary:
        print("[SKIP] No template summary found")
        return True

    print(f"\nSummary ID: {summary['_id']}")
    print(f"   Template: {summary.get('template_name')}")

    from app.models.summary import Summary

    response = Summary.to_response(summary)

    required_fields = ["id", "episode_id", "template_name", "tldr", "tags", "content"]
    all_present = True

    for field in required_fields:
        if field in response:
            print(f"   [PASS] {field}")
        else:
            print(f"   [FAIL] Missing: {field}")
            all_present = False

    # Check v3 flattening
    if summary.get("version") == "v3":
        content = summary.get("content", {})
        print(f"\n   Content keys: {list(content.keys())}")

        flattened = sum(1 for k in content.keys() if k in response and k != "content")
        print(f"   Flattened: {flattened}/{len(content)}")

    return all_present


def test_no_fallback_logic():
    """Test 5: Verify no fallback logic"""
    print("\n" + "=" * 60)
    print("Test 5: No Fallback Logic Validation")
    print("=" * 60)

    from app.services.summary_service import SummaryService

    db = get_db()
    service = SummaryService(db)

    fake_template_name = "nonexistent_template_xyz123"

    print(f"\nTesting nonexistent template: {fake_template_name}")

    # Check template doesn't exist
    template = db.prompt_templates.find_one({
        "name": fake_template_name,
        "is_active": True
    })

    if template:
        print(f"   [FAIL] Unexpected: template found")
        return False
    else:
        print(f"   [PASS] Template doesn't exist")

        # Test that service throws error
        try:
            fake_id = ObjectId()
            service.generate_summary(
                episode_id=fake_id,
                template_name=fake_template_name
            )
            print(f"   [FAIL] Service didn't throw error")
            return False

        except ValueError as e:
            if "not found or inactive" in str(e):
                print(f"   [PASS] ValueError thrown correctly")
                return True
            else:
                print(f"   [WARN] ValueError message: {e}")
                return False

        except Exception as e:
            error_msg = str(e).lower()
            if "not found" in error_msg or "not exist" in error_msg:
                print(f"   [PASS] Exception thrown: {type(e).__name__}")
                return True
            else:
                print(f"   [WARN] Unexpected error: {type(e).__name__}")
                return False


def test_debug_api():
    """Test 6: Verify debug mode API"""
    print("\n" + "=" * 60)
    print("Test 6: Debug Mode API Validation")
    print("=" * 60)

    db = get_db()

    summary = db.summaries.find_one({"template_name": {"$exists": True}})

    if not summary:
        print("[SKIP] No template summary found")
        return True

    episode_id = summary.get("episode_id")
    template_name = summary.get("template_name")

    print(f"\nEpisode ID: {episode_id}")
    print(f"   Template: {template_name}")

    # Build debug info
    tmpl_name = template_name
    template = db.prompt_templates.find_one({
        "name": tmpl_name,
        "is_active": True
    })

    if not template:
        print(f"   [FAIL] Template {tmpl_name} not found")
        return False

    locked = template.get("locked", {})
    optional_blocks = template.get("optional_blocks", [])

    expected_fields = ["tldr", "tags"]
    expected_fields.extend(locked.get("required_fields", []))

    enabled = summary.get("enabled_blocks", [])
    if enabled:
        active_blocks = [b for b in optional_blocks if b.get("id") in enabled]
    else:
        active_blocks = [b for b in optional_blocks if b.get("enabled_by_default", False)]

    for block in active_blocks:
        output_field = block.get("output_field", {})
        key = output_field.get("key")
        if key:
            expected_fields.append(key)

    content = summary.get("content", {})
    actual_fields = list(content.keys())
    missing_fields = [f for f in expected_fields if f not in actual_fields]

    print(f"\nDebug Info:")
    print(f"   Expected: {expected_fields}")
    print(f"   Actual: {actual_fields}")
    print(f"   Missing: {missing_fields if missing_fields else 'None'}")

    return True


def main():
    """Run all tests"""
    print("\n" + "=" * 60)
    print("    Summary System Automated Tests")
    print("=" * 60)

    results = {}

    tests = [
        ("Template Loading", test_templates_loaded),
        ("Field Mapping", test_field_mapping),
        ("Prompt Building", test_prompt_structure),
        ("API Format", test_summary_api_format),
        ("No Fallback", test_no_fallback_logic),
        ("Debug API", test_debug_api),
    ]

    for test_name, test_func in tests:
        try:
            results[test_name] = test_func()
        except Exception as e:
            print(f"[ERROR] {test_name}: {e}")
            results[test_name] = False

    # Summary
    print("\n" + "=" * 60)
    print("Test Results Summary")
    print("=" * 60)

    for test_name, passed in results.items():
        status = "[PASS]" if passed else "[FAIL]"
        print(f"  {status}: {test_name}")

    total = len(results)
    passed = sum(results.values())

    print(f"\nTotal: {passed}/{total} passed")

    if passed == total:
        print("\n[SUCCESS] All tests passed!")
        return 0
    else:
        print(f"\n[WARNING] {total - passed} test(s) failed")
        return 1


if __name__ == "__main__":
    exit(main())
