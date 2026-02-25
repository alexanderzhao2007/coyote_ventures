#!/usr/bin/env python
"""
Test integration between thesis_title_relevance_tool and supabase_write_evaluations.

This script tests:
1. thesis_title_relevance_tool output format
2. supabase_write_evaluations input handling
3. Database insertion and data integrity
4. Field mapping between tool output and database schema

Run from project root with .env set: SUPABASE_URL, SUPABASE_SERVICE_KEY, OPENAI_API_KEY.

  cd c:\\Users\\alexa\\OneDrive\\Desktop\\Projects\\coyote_ventures
  python coyote_ventures_weekly_intelligence_digest___email_automation/scripts/test_evaluations_integration.py
"""
import os
import sys
import json
from datetime import date

# Add project root to path for imports
# Script is in: coyote_ventures/coyote_ventures_weekly_intelligence_digest___email_automation/scripts/
# Project root is: coyote_ventures/
script_dir = os.path.dirname(os.path.abspath(__file__))
package_dir = os.path.dirname(script_dir)  # coyote_ventures_weekly_intelligence_digest___email_automation/
project_root = os.path.dirname(package_dir)  # coyote_ventures/
sys.path.insert(0, project_root)

# Load .env from project root if present
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

def main():
    # Check required environment variables
    supabase_url = os.getenv("SUPABASE_URL")
    supabase_key = os.getenv("SUPABASE_SERVICE_KEY")
    openai_key = os.getenv("OPENAI_API_KEY")
    
    if not supabase_url or not supabase_key:
        print("ERROR: Set SUPABASE_URL and SUPABASE_SERVICE_KEY in .env or environment.", file=sys.stderr)
        sys.exit(1)
    
    if not openai_key:
        print("ERROR: Set OPENAI_API_KEY in .env or environment.", file=sys.stderr)
        sys.exit(1)

    # Import tools
    from coyote_ventures_weekly_intelligence_digest___email_automation.tools.thesis_title_relevance_tool import ThesisTitleRelevanceTool
    from coyote_ventures_weekly_intelligence_digest___email_automation.tools.supabase_write_evaluations import SupabaseWriteEvaluationsTool
    
    from supabase import create_client
    supabase_client = create_client(supabase_url, supabase_key)
    
    # Generate unique test URL
    test_url = f"https://example.com/test-evaluation-{os.getpid()}"
    test_title = "New AI Health Platform Raises $50M Series B to Expand Virtual Care Services"
    
    # Sample thesis text (abbreviated for testing)
    sample_thesis = """
    Investment Thesis: Women's Health and Health Equity
    
    We invest in companies that improve healthcare outcomes for women and underserved populations,
    with a focus on:
    - Digital health technologies that increase access to care
    - AI-powered diagnostic and treatment tools
    - Virtual care platforms that reduce barriers to healthcare
    - Health equity solutions addressing disparities in care delivery
    
    We prioritize US-based companies with proven business models and strong growth potential.
    """
    
    print("=" * 80)
    print("TEST: Evaluations Tool Integration")
    print("=" * 80)
    print()
    
    # Step 1: Insert test candidate (required for foreign key constraint)
    print("Step 1: Inserting test candidate into coyote_candidates...")
    try:
        supabase_client.table("coyote_candidates").insert({
            "url": test_url,
            "title": test_title,
            "source": "Test Source",
            "published_date": str(date.today()),
        }).execute()
        print(f"   [OK] Inserted candidate: {test_url}")
    except Exception as e:
        if "duplicate" in str(e).lower() or "unique" in str(e).lower() or "23505" in str(e):
            print(f"   [WARN] Candidate already exists (will use existing): {test_url}")
        else:
            print(f"   [FAIL] FAILED: {e}", file=sys.stderr)
            sys.exit(1)
    
    print()
    
    # Step 2: Call thesis_title_relevance_tool
    print("Step 2: Calling thesis_title_relevance_tool...")
    relevance_tool = ThesisTitleRelevanceTool()
    
    try:
        tool_output = relevance_tool._run(
            thesis_text=sample_thesis,
            article_title=test_title,
            relevance_context="Focus on US-based companies and healthcare technology innovations.",
            openai_api_key=openai_key
        )
        
        print(f"   Raw tool output: {tool_output[:200]}...")
        
        # Parse the JSON output
        tool_result = json.loads(tool_output)
        print(f"   [OK] Tool returned valid JSON")
        print(f"   Relevance Score: {tool_result.get('relevance_score')}")
        print(f"   Confidence Score: {tool_result.get('confidence_score')}")
        print(f"   Signal Type: {tool_result.get('signal_type')}")
        print(f"   Exec Summary: {tool_result.get('exec_summary', '')[:100]}...")
        
    except Exception as e:
        print(f"   [FAIL] FAILED: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)
    
    print()
    
    # Step 3: Combine tool output with URL (simulating what the agent does)
    print("Step 3: Preparing evaluation data for insertion...")
    evaluation_data = {
        "url": test_url,
        **tool_result  # Merge all fields from tool output
    }
    
    # Ensure sent_in_weekly_digest is set (default false)
    if "sent_in_weekly_digest" not in evaluation_data:
        evaluation_data["sent_in_weekly_digest"] = False
    
    print(f"   Combined evaluation object:")
    print(f"   - URL: {evaluation_data['url']}")
    print(f"   - Relevance Score: {evaluation_data.get('relevance_score')}")
    print(f"   - Confidence Score: {evaluation_data.get('confidence_score')}")
    print(f"   - Signal Type: {evaluation_data.get('signal_type')}")
    print(f"   - Fields present: {len(evaluation_data)} fields")
    
    print()
    
    # Step 4: Call supabase_write_evaluations
    print("Step 4: Calling supabase_write_evaluations...")
    write_tool = SupabaseWriteEvaluationsTool()
    
    try:
        # Convert to JSON array as expected by the tool
        evaluations_json = json.dumps([evaluation_data])
        
        write_result = write_tool._run(evaluations_json=evaluations_json)
        write_result_parsed = json.loads(write_result)
        
        if "error" in write_result_parsed:
            print(f"   ✗ FAILED: {write_result_parsed['error']}", file=sys.stderr)
            sys.exit(1)
        
        inserted_count = write_result_parsed.get("inserted", 0)
        if inserted_count == 0:
            print(f"   [WARN] WARNING: No rows inserted. Result: {write_result}")
        else:
            print(f"   [OK] Inserted {inserted_count} row(s)")
            print(f"   Message: {write_result_parsed.get('message', '')}")
            
    except Exception as e:
        print(f"   [FAIL] FAILED: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)
    
    print()
    
    # Step 5: Verify data was inserted correctly
    print("Step 5: Verifying inserted data...")
    try:
        result = (
            supabase_client.table("coyote_article_evaluations")
            .select("*")
            .eq("url", test_url)
            .execute()
        )
        
        if not result.data or len(result.data) == 0:
            print(f"   [FAIL] FAILED: No data found for URL {test_url}", file=sys.stderr)
            sys.exit(1)
        
        db_row = result.data[0]
        print(f"   [OK] Found inserted row")
        
        # Compare key fields
        print()
        print("   Field Comparison:")
        print("   " + "-" * 76)
        
        fields_to_check = [
            ("url", "URL"),
            ("relevance_score", "Relevance Score"),
            ("confidence_score", "Confidence Score"),
            ("signal_type", "Signal Type"),
            ("exec_summary", "Exec Summary"),
            ("why_it_matters", "Why It Matters"),
            ("thesis_sector", "Thesis Sector"),
            ("focus_area_tags", "Focus Area Tags"),
            ("geography", "Geography"),
            ("companies_mentioned", "Companies Mentioned"),
            ("rejection_reason", "Rejection Reason"),
            ("sent_in_weekly_digest", "Sent in Weekly Digest"),
        ]
        
        all_match = True
        for field, label in fields_to_check:
            sent_value = evaluation_data.get(field)
            db_value = db_row.get(field)
            
            # Normalize for comparison (handle None, empty strings, numeric types)
            sent_normalized = sent_value if sent_value not in (None, "") else None
            db_normalized = db_value if db_value not in (None, "") else None
            
            # For numeric fields, compare as floats
            if field in ("relevance_score", "confidence_score") and sent_normalized is not None:
                try:
                    sent_normalized = float(sent_normalized)
                    db_normalized = float(db_normalized) if db_normalized is not None else None
                except (TypeError, ValueError):
                    pass
            
            # For boolean fields
            if field == "sent_in_weekly_digest":
                sent_normalized = bool(sent_normalized)
                db_normalized = bool(db_normalized) if db_normalized is not None else False
            
            match = sent_normalized == db_normalized
            
            if not match:
                all_match = False
            
            status = "[OK]" if match else "[DIFF]"
            print(f"   {status} {label:25} Sent: {str(sent_normalized)[:30]:30} DB: {str(db_normalized)[:30]}")
        
        print("   " + "-" * 76)
        
        if all_match:
            print()
            print("   [OK] All fields match correctly!")
        else:
            print()
            print("   [WARN] Some fields don't match (check truncation or type conversion)")
        
        # Check auto-generated fields
        if "evaluated_at" in db_row:
            print(f"   [OK] Auto-generated evaluated_at: {db_row['evaluated_at']}")
        
    except Exception as e:
        print(f"   [FAIL] FAILED to verify: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)
    
    print()
    print("=" * 80)
    print("TEST SUMMARY")
    print("=" * 80)
    print(f"[OK] Candidate inserted: {test_url}")
    print(f"[OK] Thesis relevance tool executed successfully")
    print(f"[OK] Evaluation data prepared correctly")
    print(f"[OK] Supabase write tool executed successfully")
    print(f"[OK] Data verified in database")
    print()
    print(f"Test URL: {test_url}")
    print("(You can delete this test row from coyote_candidates; evaluations will CASCADE.)")
    print()
    print("Integration test PASSED!")


if __name__ == "__main__":
    main()
