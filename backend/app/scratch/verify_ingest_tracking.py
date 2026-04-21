import os
import sys
from datetime import datetime

# Add parent of backend to path to support 'backend.app' imports
sys.path.append(os.path.dirname(os.getcwd()))

from backend.app.db.session import SessionLocal
from backend.app.services.jobscrapping.unified_ingest import run_unified_companies_ingestion
from backend.app.core.config import settings

def verify():
    print("Starting Ingestion Tracking Verification...")
    db = SessionLocal()
    try:
        # Mock settings to ensure deep enrichment is enabled for test
        settings.ingest_deep_enrich_enabled = True
        
        # Run unified ingestion in dry_run mode
        print("Triggering run_unified_companies_ingestion(dry_run=True)...")
        metrics = run_unified_companies_ingestion(db, dry_run=True)
        
        print("\n--- Ingestion Metrics ---")
        res = metrics.as_response()
        print(f"Total Jobs Seen: {res.get('total_jobs_seen')}")
        print(f"Total Tokens: {res.get('total_tokens')}")
        print(f"Total Cost: ${res.get('total_cost'):.6f}")
        
        deep_enrich = res.get("deep_enrich", {})
        print(f"Deep Enrich Fetched: {deep_enrich.get('deep_enrich_fetched')}")
        print(f"Deep Enrich Tokens: {deep_enrich.get('total_tokens')}")
        
        # Verify columns exist in DB (even if dry_run, we can check schema)
        from sqlalchemy import inspect
        inspector = inspect(db.bind)
        columns = [c['name'] for c in inspector.get_columns('scraper_runs')]
        print(f"\nScraper Runs Columns: {columns}")
        
        has_tokens = 'total_tokens' in columns
        has_cost = 'total_cost' in columns
        print(f"Schema Verification: {'SUCCESS' if has_tokens and has_cost else 'FAILED'}")
        
    except Exception as e:
        print(f"Verification FAILED: {e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()

if __name__ == "__main__":
    verify()
