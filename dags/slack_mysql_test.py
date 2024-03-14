from datetime import datetime, timedelta
from email.policy import default
from textwrap import dedent

from airflow import DAG
from airflow.providers.mysql.operators.mysql import MySqlOperator
from airflow.providers.slack.operators.slack_webhook import SlackWebhookOperator

default_args = {
    "depends_on_past": False,
    "retries": 1,
    "retry_delay": timedelta(minutes=5),
}

sql_read_data = """
    SELECT jobinfo_test.table_1.company, position, location, review
    FROM jobinfo_test.table_1
    JOIN jobinfo_test.table_2
    ON jobinfo_test.table_1.company = jobinfo_test.table_2.company;
"""

with DAG(
    "read_to_local_mysql",
    default_args=default_args,
    description="""
        1) create 'employees' table in local mysqld
        2) insert data to 'employees' table
    """,
    schedule_interval="@once",
    start_date=datetime(2024, 1, 1),
    tags=["mysql", "local", "test", "company"],
) as dag:
    t1 = MySqlOperator(
        task_id="create_employees_table",
        mysql_conn_id="mysql_local_test",
        sql=sql_read_data,
        dag=dag,
    )
    t2 = SlackWebhookOperator(
        task_id="send_slack",
        http_conn_id="slack_conn",
        message="오늘의 채용 공고 + {sql_read_data}",
        dag=dag,
    )
