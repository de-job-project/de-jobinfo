# 최신
from datetime import datetime, timedelta
from email.policy import default
from textwrap import dedent

import pymysql
from airflow import DAG
from airflow.operators.python_operator import PythonOperator
from airflow.providers.mysql.hooks.mysql import MySqlHook
from airflow.providers.mysql.operators.mysql import MySqlOperator
from airflow.providers.slack.operators.slack_webhook import SlackWebhookOperator
from prettytable import PrettyTable

default_args = {
    "depends_on_past": False,
    "retries": 1,
    "retry_delay": timedelta(minutes=3),
}

sql_read_data = """
    SELECT mydb.jobinfo_jumpit.company, position, skills, location, career, due_date, review_summary, merit_summary, demerit_summary, average_salary
    FROM mydb.jobinfo_jumpit
    LEFT JOIN mydb.jobinfo_jobplanet
    ON mydb.jobinfo_jumpit.company = mydb.jobinfo_jobplanet.company;
"""


def get_db_connection():
    mysql_hook = MySqlHook(mysql_conn_id="rds_conn")

    return mysql_hook.get_conn()


def postAndReview_sql_and_return_result(**kwargs):

    connection = get_db_connection()

    try:
        # 커서 생성
        with connection.cursor() as cursor:
            # SQL 쿼리 실행
            sql_query = """
                SELECT mydb.jobinfo_jobplanet.company AS 회사명, merit_summary AS 장점, demerit_summary AS 단점, answer_summary AS '면접 분위기 및 답변'
                FROM mydb.jobinfo_jobplanet
                ORDER BY mydb.jobinfo_jobplanet.company;
            """
            cursor.execute(sql_query)

            # 결과 가져오기
            result = cursor.fetchall()

            # 표 생성
            table = PrettyTable()
            table.field_names = [i[0] for i in cursor.description]

            for row in result:
                table.add_row(row)

            postAndReview_str = str(table)
            print(postAndReview_str)

    finally:
        # 연결 닫기
        connection.close()

    return postAndReview_str


def totalPost_sql_and_return_result(**kwargs):

    connection = get_db_connection()

    try:
        # 커서 생성
        with connection.cursor() as cursor:
            # SQL 쿼리 실행
            sql_query = """
                SELECT mydb.jobinfo_jumpit.company AS 회사명, position AS 직급, skills AS 필요역량, average_salary AS 평균연봉, due_date AS 마감기한, link AS 채용페이지
                FROM mydb.jobinfo_jumpit
                LEFT JOIN mydb.jobinfo_jobplanet
                ON mydb.jobinfo_jumpit.company = mydb.jobinfo_jobplanet.company
                ORDER BY mydb.jobinfo_jobplanet.company;
            """
            cursor.execute(sql_query)

            # 결과 가져오기
            result = cursor.fetchall()

            # 표 생성
            table = PrettyTable()
            table.field_names = [i[0] for i in cursor.description]

            for row in result:
                table.add_row(row)

            totalPost_result_str = str(table)
            print(totalPost_result_str)

    finally:
        # 연결 닫기
        connection.close()

    return totalPost_result_str


def closeDeadline_sql_and_return_result(**kwargs):

    connection = get_db_connection()

    try:
        # 커서 생성
        with connection.cursor() as cursor:
            # SQL 쿼리 실행
            sql_query = """
                SELECT mydb.jobinfo_jumpit.company AS 회사명, position AS 직급, skills AS 필요역량, due_date AS 마감기한, link AS 채용페이지
                FROM mydb.jobinfo_jumpit
                WHERE timestampdiff(DAY, due_date, now()) > -3
                ORDER BY mydb.jobinfo_jumpit.company;
            """
            cursor.execute(sql_query)

            # 결과 가져오기
            result = cursor.fetchall()

            # 표 생성
            table = PrettyTable()
            table.field_names = [i[0] for i in cursor.description]

            for row in result:
                table.add_row(row)

            closeDeadline_result_str = str(table)
            print(closeDeadline_result_str)

    finally:
        # 연결 닫기
        connection.close()

    return closeDeadline_result_str


with DAG(
    "jobinfo_slack",
    default_args=default_args,
    schedule_interval="0 10 * * *",
    start_date=datetime(2024, 1, 9),
    catchup=False,
    max_active_runs=1,
    tags=["mysql", "rds", "test", "job_info"],
) as dag:
    t1 = MySqlOperator(
        task_id="rds_connection", mysql_conn_id="rds_conn", sql=sql_read_data, dag=dag
    )

    t2 = PythonOperator(
        task_id="postAndReview_sql_and_return_result",
        python_callable=postAndReview_sql_and_return_result,
        provide_context=True,
        op_args=[],
        op_kwargs={},
        dag=dag,
    )

    t3 = PythonOperator(
        task_id="totalPost_sql_and_return_result",
        python_callable=totalPost_sql_and_return_result,
        provide_context=True,
        op_args=[],
        op_kwargs={},
        dag=dag,
    )

    t4 = PythonOperator(
        task_id="closeDeadline_sql_and_return_result",
        python_callable=closeDeadline_sql_and_return_result,
        provide_context=True,
        op_args=[],
        op_kwargs={},
        dag=dag,
    )

    t5 = SlackWebhookOperator(
        task_id="send_slack_totalPost",
        http_conn_id="slack_conn",
        message=f'```오늘의 채용공고!!\n{{{{ ti.xcom_pull(task_ids="totalPost_sql_and_return_result") }}}}\n```',
        dag=dag,
    )

    t6 = SlackWebhookOperator(
        task_id="send_slack_postAndReview",
        http_conn_id="slack_conn",
        message=f'```채용 공고와 리뷰!!\n{{{{ ti.xcom_pull(task_ids="postAndReview_sql_and_return_result") }}}}\n```',
        dag=dag,
    )

    t7 = SlackWebhookOperator(
        task_id="send_slack_closeDeadline",
        http_conn_id="slack_conn",
        message=f'```마감임박 채용공고!!\n{{{{ ti.xcom_pull(task_ids="closeDeadline_sql_and_return_result") }}}}\n\n\n produced by - 김해빈, 노은지, 박광현, 조성재```',
        dag=dag,
    )

    t1 >> t2 >> t3 >> t4 >> t5 >> t6 >> t7
