"""
BridgeSync Airflow DAG for Sync Job Orchestration.

This DAG is dynamically generated for each sync job and handles:
- Scheduled sync runs (via cron)
- Manual trigger support
- Error handling and retries
- Integration with BridgeSync API
"""

from datetime import datetime, timedelta
from typing import Optional
import json
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
    """Fetch all active sync jobs from BridgeSync API."""
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


def trigger_sync_job(job_id: int, force_full_refresh: bool = False, **context):
    """
    Trigger a sync job execution via BridgeSync API.
    
    This function is called by Airflow to execute a sync job.
    The actual sync logic is handled by the BridgeSync backend.
    """
    airflow_run_id = context.get("run_id", context.get("dag_run").run_id if context.get("dag_run") else None)
    
    print(f"Triggering sync job {job_id}, airflow_run_id: {airflow_run_id}")
    
    try:
        response = requests.post(
            f"{BRIDGESYNC_API_URL}/syncs/{job_id}/trigger",
            headers=get_api_headers(),
            params={
                "force_full_refresh": force_full_refresh,
            },
            timeout=3600,  # 1 hour timeout for long syncs
        )
        response.raise_for_status()
        result = response.json()
        
        print(f"Sync result: {result}")
        
        if result.get("status") == "failed":
            raise Exception(f"Sync failed: {result.get('message')}")
        
        return result
        
    except requests.exceptions.RequestException as e:
        print(f"API request failed: {e}")
        raise


def check_sync_status(run_id: str, **context):
    """Check the status of a sync run."""
    try:
        response = requests.get(
            f"{BRIDGESYNC_API_URL}/runs/{run_id}",
            headers=get_api_headers(),
            timeout=30,
        )
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print(f"Failed to check sync status: {e}")
        raise


# Default DAG arguments
default_args = {
    "owner": "bridgesync",
    "depends_on_past": False,
    "email_on_failure": False,
    "email_on_retry": False,
    "retries": 3,
    "retry_delay": timedelta(minutes=5),
    "execution_timeout": timedelta(hours=2),
}


def create_sync_dag(
    job_id: int,
    job_name: str,
    schedule: Optional[str] = None,
    description: Optional[str] = None,
):
    """
    Factory function to create a DAG for a sync job.
    
    Args:
        job_id: BridgeSync sync job ID
        job_name: Name for the DAG
        schedule: Cron schedule expression (None for manual only)
        description: DAG description
    """
    dag_id = f"bridgesync_sync_{job_id}"
    
    dag = DAG(
        dag_id=dag_id,
        default_args=default_args,
        description=description or f"BridgeSync sync job: {job_name}",
        schedule_interval=schedule,
        start_date=days_ago(1),
        catchup=False,
        max_active_runs=1,
        tags=["bridgesync", "reverse-etl", "sync"],
    )
    
    with dag:
        sync_task = PythonOperator(
            task_id="execute_sync",
            python_callable=trigger_sync_job,
            op_kwargs={
                "job_id": job_id,
                "force_full_refresh": False,
            },
            provide_context=True,
        )
        
        sync_task
    
    return dag


# Dynamic DAG generation from BridgeSync API
# This creates one DAG per active sync job with a cron schedule
try:
    sync_jobs = fetch_sync_jobs()
    
    for job in sync_jobs:
        if not job.get("is_active") or job.get("is_paused"):
            continue
        
        if job.get("schedule_type") != "cron":
            continue
        
        dag = create_sync_dag(
            job_id=job["id"],
            job_name=job["name"],
            schedule=job.get("cron_expression"),
            description=f"Sync {job.get('source_connection_name', 'source')} to {job.get('destination_connection_name', 'destination')}",
        )
        
        # Register DAG in global namespace
        globals()[dag.dag_id] = dag
        
except Exception as e:
    print(f"Failed to create dynamic DAGs: {e}")


# Static example DAG for manual testing
example_dag = DAG(
    dag_id="bridgesync_example_sync",
    default_args=default_args,
    description="Example BridgeSync sync DAG for testing",
    schedule_interval=None,  # Manual trigger only
    start_date=days_ago(1),
    catchup=False,
    tags=["bridgesync", "example"],
)

with example_dag:
    example_task = PythonOperator(
        task_id="example_sync",
        python_callable=lambda: print("Example sync task - configure job_id to run actual sync"),
    )
