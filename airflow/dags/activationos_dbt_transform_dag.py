"""
Alo ActivationOS Airflow DAG for dbt transformations.

Runs dbt staging/intermediate/mart models and tests on a schedule.
"""

from datetime import timedelta

from airflow import DAG
from airflow.operators.bash import BashOperator
from airflow.utils.dates import days_ago
from airflow.models import Variable


DBT_PROJECT_DIR = Variable.get(
    "activationos_dbt_project_dir",
    default_var="platform/dbt",
)

DBT_PROFILES_DIR = Variable.get(
    "activationos_dbt_profiles_dir",
    default_var="/Users/utkarshparekh/.dbt",
)


default_args = {
    "owner": "activationos",
    "depends_on_past": False,
    "email_on_failure": False,
    "retries": 1,
    "retry_delay": timedelta(minutes=5),
}


dag = DAG(
    dag_id="activationos_dbt_transform",
    default_args=default_args,
    description="Run dbt transformations for Alo ActivationOS marts",
    schedule_interval="15 * * * *",  # Hourly at :15
    start_date=days_ago(1),
    catchup=False,
    tags=["activationos", "dbt", "transform"],
)


with dag:
    dbt_deps = BashOperator(
        task_id="dbt_deps",
        bash_command=f"cd {DBT_PROJECT_DIR} && dbt deps --profiles-dir {DBT_PROFILES_DIR}",
    )

    dbt_staging = BashOperator(
        task_id="dbt_build_staging",
        bash_command=f"cd {DBT_PROJECT_DIR} && dbt build --select tag:staging --profiles-dir {DBT_PROFILES_DIR}",
    )

    dbt_intermediate = BashOperator(
        task_id="dbt_build_intermediate",
        bash_command=f"cd {DBT_PROJECT_DIR} && dbt build --select tag:intermediate --profiles-dir {DBT_PROFILES_DIR}",
    )

    dbt_marts = BashOperator(
        task_id="dbt_build_marts",
        bash_command=f"cd {DBT_PROJECT_DIR} && dbt build --select tag:mart --profiles-dir {DBT_PROFILES_DIR}",
    )

    dbt_deps >> dbt_staging >> dbt_intermediate >> dbt_marts

