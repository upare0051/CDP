"""
Alo ActivationOS Airflow DAG for Schema Change Detection.

This DAG runs periodically to check for schema changes in source tables
and alerts if changes are detected that might affect sync jobs.
"""

from datetime import datetime, timedelta
import requests

from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.utils.dates import days_ago
from airflow.models import Variable


# Configuration
ACTIVATIONOS_API_URL = Variable.get("activationos_api_url", default_var="http://localhost:8000/api/v1")
ACTIVATIONOS_API_KEY = Variable.get("activationos_api_key", default_var="")


def get_api_headers():
    """Get API headers with authentication."""
    headers = {"Content-Type": "application/json"}
    if ACTIVATIONOS_API_KEY:
        headers["Authorization"] = f"Bearer {ACTIVATIONOS_API_KEY}"
    return headers


def fetch_sync_jobs():
    """Fetch all sync jobs."""
    try:
        response = requests.get(
            f"{ACTIVATIONOS_API_URL}/syncs",
            headers=get_api_headers(),
            timeout=30,
        )
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print(f"Failed to fetch sync jobs: {e}")
        return []


def check_schema(job_id: int, source_connection_id: int, source_table: str):
    """Check schema for a single sync job."""
    try:
        response = requests.post(
            f"{ACTIVATIONOS_API_URL}/syncs/{job_id}/check-schema",
            headers=get_api_headers(),
            timeout=30,
        )
        if response.status_code == 200:
            result = response.json()
            return result.get("has_changes", False), result.get("changes", [])
        return False, []
    except Exception as e:
        print(f"Schema check failed for job {job_id}: {e}")
        return False, []


def check_all_schemas(**context):
    """
    Check schema changes for all active sync jobs.
    """
    jobs = fetch_sync_jobs()
    changes_detected = []

    for job in jobs:
        if not job.get("is_active"):
            continue

        job_id = job["id"]
        source_connection_id = job.get("source_connection_id")
        source_table = job.get("source_table")

        has_changes, changes = check_schema(job_id, source_connection_id, source_table)
        if has_changes:
            changes_detected.append({"job_id": job_id, "job_name": job.get("name"), "changes": changes})

    if changes_detected:
        print("Schema changes detected:")
        for change in changes_detected:
            print(f"Job {change['job_id']} ({change['job_name']}): {change['changes']}")
        raise Exception(f"Schema changes detected in {len(changes_detected)} jobs")

    print("No schema changes detected.")


default_args = {
    "owner": "activationos",
    "depends_on_past": False,
    "email_on_failure": False,
    "retries": 1,
    "retry_delay": timedelta(minutes=5),
}


dag = DAG(
    dag_id="activationos_schema_check",
    default_args=default_args,
    description="Check for schema changes in Alo ActivationOS source tables",
    schedule_interval="0 */6 * * *",  # Every 6 hours
    start_date=days_ago(1),
    catchup=False,
    tags=["activationos", "schema", "monitoring"],
)


with dag:
    check_task = PythonOperator(
        task_id="check_all_schemas",
        python_callable=check_all_schemas,
        provide_context=True,
    )

