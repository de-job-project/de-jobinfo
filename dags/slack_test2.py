from datetime import datetime, timedelta
from email.policy import default
from textwrap import dedent

import pymysql
from airflow import DAG
from airflow.operators.python_operator import PythonOperator
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


def execute_sql_and_return_result(**kwargs):

    connection = pymysql.connect(
        host="192.168.219.104",
        user="ssungcohol",
        password="skrxk362636!@",
        database="jobinfo_test",
    )
    # 실제 SQL 쿼리 실행 로직으로 대체해주세요
    # 여기서는 임시로 "실제 SQL 실행 로직"이라는 문자열을 반환하도록 했습니다.
    try:
        # 커서 생성
        with connection.cursor() as cursor:
            # SQL 쿼리 실행
            sql_query = """
                SELECT jobinfo_test.table_1.company, position, location, review
                FROM jobinfo_test.table_1
                JOIN jobinfo_test.table_2
                ON jobinfo_test.table_1.company = jobinfo_test.table_2.company;
            """
            cursor.execute(sql_query)

            # 결과 가져오기
            result = cursor.fetchall()
    finally:
        # 연결 닫기
        connection.close()

    return result


with DAG(
    "slack_test2",
    default_args=default_args,
    description="""
        1) 로컬 MySQL에 'employees' 테이블 생성
        2) 'employees' 테이블에 데이터 삽입
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

    t2 = PythonOperator(
        task_id="execute_sql_and_return_result",
        python_callable=execute_sql_and_return_result,
        provide_context=True,
        dag=dag,
    )

    t3 = SlackWebhookOperator(
        task_id="send_slack",
        http_conn_id="slack_conn",
        message='오늘의 채용 공고 + {{ task_instance.xcom_pull(task_ids="execute_sql_and_return_result") }}',
        dag=dag,
    )

    t1 >> t2 >> t3
