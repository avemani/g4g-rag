import os
from datetime import datetime, timedelta
from airflow import DAG
from airflow.providers.docker.operators.docker import DockerOperator
from docker.types import Mount, DeviceRequest

default_args = {
    'owner': 'airflow',
    'depends_on_past': False,
    'email_on_failure': False,
    'email_on_retry': False,
    'retries': 1,
    'retry_delay': timedelta(minutes=5),
}

ETL_IMAGE_NAME = 'rag-worker:latest' 
ETL_NETWORK_MODE = 'network_you_use' # Update this with the actual network mode in Airflow
PATH_TO_ETL = os.environ.get('WORKER_PATH', '/full/path/to/project') 

# Read credentials from environment securely instead of string templating
POSTGRES_USER = os.environ.get('POSTGRES_USER', 'etluser')
POSTGRES_PASSWORD = os.environ.get('POSTGRES_PASSWORD', 'pass')
MONGO_USER = os.environ.get('MONGO_USER', 'mongouser')
MONGO_PASS = os.environ.get('MONGO_PASS', 'pass')

with DAG(
    'etl_docker_pipeline',
    default_args=default_args,
    description='ETL running from Docker',
    start_date=datetime(2026, 1, 1),
    catchup=False,
    max_active_runs=1,
    tags=['etl', 'docker'],
) as dag:

    hrefs_task = DockerOperator(
        task_id='hrefs_task',
        image=ETL_IMAGE_NAME,
        api_version='auto',
        auto_remove='force',
        working_dir='/g4g-rag/etl',
        command='python /g4g-rag/etl/collect_hrefs.py',
        docker_url='unix://var/run/docker.sock', # or 'tcp://dockerhost:2375'
        network_mode=ETL_NETWORK_MODE,
        environment={
            'POSTGRES_USER': POSTGRES_USER,
            'POSTGRES_PASSWORD': POSTGRES_PASSWORD,
            'MONGO_USER': MONGO_USER,
            'MONGO_PASS': MONGO_PASS
        },
        mounts=[
            Mount(
                source=PATH_TO_ETL,
                target='/g4g-rag',
                type='bind'
            )
        ]
    )

    collect_task = DockerOperator(
        task_id='collect_task',
        image=ETL_IMAGE_NAME,
        api_version='auto',
        auto_remove='force',
        working_dir='/g4g-rag/etl',
        command='python /g4g-rag/etl/collect_data.py',
        docker_url='unix://var/run/docker.sock',
        network_mode=ETL_NETWORK_MODE,
        environment={
            'POSTGRES_USER': POSTGRES_USER,
            'POSTGRES_PASSWORD': POSTGRES_PASSWORD,
            'MONGO_USER': MONGO_USER,
            'MONGO_PASS': MONGO_PASS
        },
        mounts=[
            Mount(
                source=PATH_TO_ETL,
                target='/g4g-rag',
                type='bind'
            )
        ]
    )

    migrate_task = DockerOperator(
        task_id='migrate_task',
        image=ETL_IMAGE_NAME,
        api_version='auto',
        auto_remove='force',
        working_dir='/g4g-rag/etl',
        command='python /g4g-rag/etl/migrate_data.py',
        docker_url='unix://var/run/docker.sock',
        network_mode=ETL_NETWORK_MODE,
        device_requests=[
            DeviceRequest(
                count=1,
                capabilities=[["gpu"]],
            )
        ],
        environment={
            'POSTGRES_USER': POSTGRES_USER,
            'POSTGRES_PASSWORD': POSTGRES_PASSWORD,
            'MONGO_USER': MONGO_USER,
            'MONGO_PASS': MONGO_PASS
        },
        mounts=[
            Mount(
                source=PATH_TO_ETL,
                target='/g4g-rag',
                type='bind'
            )
        ]
    )

    hrefs_task >> collect_task >> migrate_task