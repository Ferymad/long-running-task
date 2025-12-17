from agency_swarm.tools import BaseTool
from pydantic import Field
import json
import sqlite3
from datetime import datetime
import os

class CacheCostSnapshot(BaseTool):
    """Store normalized multi-cloud cost data in local SQLite database for performance optimization and offline analysis.

    Use this tool after normalizing cost data to persist it locally, reducing expensive cloud API
    calls (AWS Cost Explorer charges $0.01 per request). Cached data enables faster queries for
    historical analysis, baseline calculations, and anomaly detection without hitting rate limits.

    Do NOT use this tool for real-time data that changes frequently. Cache snapshots are intended
    for daily or hourly cost aggregations that remain stable. For live monitoring, query cloud
    providers directly.

    Returns: Confirmation message with cache key, record count, total cost cached, and timestamp.
    The cache_key is used to retrieve data later using SQLite MCP server queries like:
    SELECT * FROM cost_snapshots WHERE cache_key = 'your_key'

    The tool automatically creates the cost_snapshots table if it doesn't exist, with columns for
    provider, date, service, cost, and metadata. Each snapshot includes a unique cache_key for
    retrieval and a timestamp for cache invalidation strategies (e.g., 24-hour TTL).
    """

    normalized_data: str = Field(
        ...,
        description="JSON string containing normalized cost records from NormalizeCostData tool. Must be valid JSON array with records containing provider, cost, service, and time_period fields."
    )
    cache_key: str = Field(
        ...,
        description="Unique identifier for this snapshot (e.g., 'aws_2025-12-17_daily', 'gcp_prod_monthly'). Use format: {provider}_{date}_{granularity} for consistency. This key is used to retrieve cached data later."
    )
    ttl_hours: int = Field(
        default=24,
        description="Time-to-live in hours before cached data should be refreshed. Default 24 hours. Use 1 for hourly updates, 168 for weekly. Cache expiration timestamp is stored for automated cleanup."
    )

    def run(self):
        """Store normalized cost data in SQLite cache with metadata."""
        # Step 1: Parse normalized data
        try:
            records = json.loads(self.normalized_data)

            if not isinstance(records, dict) or "records" not in records:
                return "Error: normalized_data must be JSON object with 'records' array. Ensure you're passing output from NormalizeCostData tool."

            cost_records = records["records"]

            if not cost_records:
                return "Warning: No cost records to cache. normalized_data contains empty records array."

        except json.JSONDecodeError as e:
            return f"Error: Invalid JSON in normalized_data. Details: {str(e)}"

        # Step 2: Validate cache key format
        if not self.cache_key or len(self.cache_key) < 3:
            return "Error: cache_key must be at least 3 characters. Use descriptive format like 'aws_2025-12-17_daily'."

        try:
            # Step 3: Connect to SQLite database
            db_path = os.path.join(os.getcwd(), "cost_cache.db")
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()

            # Step 4: Create table if not exists
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS cost_snapshots (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    cache_key TEXT NOT NULL,
                    provider TEXT NOT NULL,
                    account_id TEXT,
                    service TEXT,
                    resource_type TEXT,
                    region TEXT,
                    cost REAL NOT NULL,
                    currency TEXT,
                    usage_amount REAL,
                    usage_unit TEXT,
                    time_period_start TEXT,
                    time_period_end TEXT,
                    tags TEXT,
                    metadata TEXT,
                    cached_at TEXT NOT NULL,
                    expires_at TEXT NOT NULL,
                    UNIQUE(cache_key, provider, service, time_period_start)
                )
            """)

            # Create index for faster queries
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_cache_key
                ON cost_snapshots(cache_key, cached_at)
            """)

            # Step 5: Calculate expiration timestamp
            from datetime import datetime, timedelta
            cached_at = datetime.now().isoformat()
            expires_at = (datetime.now() + timedelta(hours=self.ttl_hours)).isoformat()

            # Step 6: Insert cost records
            inserted_count = 0
            total_cost = 0

            for record in cost_records:
                try:
                    cursor.execute("""
                        INSERT OR REPLACE INTO cost_snapshots (
                            cache_key, provider, account_id, service, resource_type,
                            region, cost, currency, usage_amount, usage_unit,
                            time_period_start, time_period_end, tags, metadata,
                            cached_at, expires_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        self.cache_key,
                        record.get("provider", "unknown"),
                        record.get("account_id", ""),
                        record.get("service", ""),
                        record.get("resource_type", ""),
                        record.get("region", ""),
                        record.get("cost", 0),
                        record.get("currency", "USD"),
                        record.get("usage_amount", 0),
                        record.get("usage_unit", ""),
                        record.get("time_period_start", ""),
                        record.get("time_period_end", ""),
                        json.dumps(record.get("tags", {})),
                        json.dumps(record.get("metadata", {})),
                        cached_at,
                        expires_at
                    ))
                    inserted_count += 1
                    total_cost += record.get("cost", 0)

                except sqlite3.IntegrityError:
                    # Skip duplicate entries
                    continue

            # Step 7: Commit and close
            conn.commit()
            conn.close()

            # Step 8: Return success summary
            provider = cost_records[0].get("provider", "unknown") if cost_records else "unknown"

            return f"Success: Cached {inserted_count} cost records with key '{self.cache_key}'. Total cost cached: ${total_cost:.2f}. Provider: {provider}. Expires at: {expires_at}. Database: {db_path}. Retrieve with: SELECT * FROM cost_snapshots WHERE cache_key = '{self.cache_key}'"

        except sqlite3.Error as e:
            return f"Error accessing SQLite database: {str(e)}. Ensure write permissions for {db_path}. If database is corrupted, delete cost_cache.db and retry."
        except Exception as e:
            return f"Error caching cost snapshot: {str(e)}. Verify normalized_data structure matches expected format."


if __name__ == "__main__":
    # Test with sample normalized data
    sample_normalized = json.dumps({
        "normalized_count": 3,
        "total_cost": 12450.75,
        "currency": "USD",
        "unique_services": 3,
        "provider": "aws",
        "records": [
            {
                "provider": "aws",
                "account_id": "123456789012",
                "resource_id": "aws:Amazon EC2",
                "resource_name": "Amazon EC2",
                "resource_type": "service",
                "service": "Amazon EC2",
                "region": "us-east-1",
                "cost": 8200.50,
                "currency": "USD",
                "usage_amount": 720,
                "usage_unit": "hours",
                "time_period_start": "2025-12-10",
                "time_period_end": "2025-12-17",
                "tags": {},
                "metadata": {"granularity": "DAILY"}
            },
            {
                "provider": "aws",
                "account_id": "123456789012",
                "resource_id": "aws:Amazon S3",
                "resource_name": "Amazon S3",
                "resource_type": "service",
                "service": "Amazon S3",
                "region": "us-east-1",
                "cost": 2150.25,
                "currency": "USD",
                "usage_amount": 1500,
                "usage_unit": "GB",
                "time_period_start": "2025-12-10",
                "time_period_end": "2025-12-17",
                "tags": {},
                "metadata": {"granularity": "DAILY"}
            }
        ]
    })

    tool = CacheCostSnapshot(
        normalized_data=sample_normalized,
        cache_key="aws_2025-12-17_daily_test",
        ttl_hours=24
    )
    print(tool.run())
