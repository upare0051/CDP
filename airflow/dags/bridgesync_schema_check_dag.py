"""
BridgeSync Airflow DAG for Schema Change Detection.

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
BRIDGESYNC_API_URL = Variable.get("bridgesync_api_url", default_var="http://localhost:8000/api/v1")
BRIDGESYNC_API_KEY = Variable.get("bridgesync_api_key", default_var="")


def get_api_headers():
    """Get API headers with authentication."""
    headers = {"Content-Type": "application/json"}
    if BRIDGESYNC_API_KEY:
        headers["Authorization"] = f"Bearer {BRIDGESYNC_API_KEY}"
    return headers


def fetch_sync_jobs():
    """Fetch all sync jobs."""
    try:
        response = requests.get(
            f"{BRIDGESYNC_API_URL}/syncs",
            headers=get_api_headers(),
            timeout=30,
        )
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print(f"Failed to fetch sync jobs: {e}")
        return []


def check_all_schemas(**context):
    """
    Check schema changes for all active sync jobs.
    
    This task iterates through all sync jobs and checks if the source
    table schema has changed since the last check.
    """
    jobs = fetch_sync_jobs()
    changes_detected = []
    
    for job in jobs:
        if not job.get("is_active"):
            continue
        
        job_id = job["id"]
        job_name = job["name"]
        
        try:
            response = requests.get(
                f"{BRIDGESYNC_API_URL}/syncs/{job_id}/schema-changes",
                headers=get_api_headers(),
                timeout=60,
            )
            response.raise_for_status()
            result = response.json()
            
            if result.get("has_changes"):
                changes_detected.append({
                    "job_id": job_id,
                    "job_name": job_name,
                    "added_columns": result.get("added_columns", []),
                    "removed_columns": result.get("removed_columns", []),
                    "modified_columns": result.get("modified_columns", []),
                })
                print(f"Schema change detected for job {job_name}: {result}")
            else:
                print(f"No schema changes for job {job_name}")
                
        except Exception as e:
            print(f"Failed to check schema for job {job_name}: {e}")
    
    if changes_detected:
        # In production, you might want to send alerts here
        print(f"Schema changes detected in {len(changes_detected)} jobs:")
        for change in changes_detected:
            print(f"  - {change['job_name']}: added={change['added_columns']}, removed={change['removed_columns']}")
        
        # Push to XCom for downstream tasks
        context["ti"].xcom_push(key="schema_changes", value=changes_detected)
    
    return len(changes_detected)


# DAG Definition
default_args = {
    "owner": "bridgesync",
    "depends_on_past": False,
    "email_on_failure": False,
    "retries": 1,
    "retry_delay": timedelta(minutes=5),
}

dag = DAG(
    dag_id="bridgesync_schema_check",
    default_args=default_args,
    description="Check for schema changes in BridgeSync source tables",
    schedule_interval="0 */6 * * *",  # Every 6 hours
    start_date=days_ago(1),
    catchup=False,
    tags=["bridgesync", "schema", "monitoring"],
)

with dag:
    check_schemas_task = PythonOperator(
        task_id="check_all_schemas",
        python_callable=check_all_schemas,
        provide_context=True,
    )
