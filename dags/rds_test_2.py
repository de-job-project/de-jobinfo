from datetime import datetime, timedelta
from email.policy import default
from textwrap import dedent
import pymysql
from prettytable import PrettyTable

from airflow import DAG
from airflow.providers.mysql.operators.mysql import MySqlOperator
from airflow.providers.slack.operators.slack_webhook import SlackWebhookOperator
from airflow.operators.python_operator import PythonOperator

default_args = {
    'depends_on_past': False,
    'retries': 1,
    'retry_delay': timedelta(minutes=3)
}

sql_read_data = """
    SELECT mydb.jobinfo_jumpit.company, position, skills, average_salary, due_date, link
    FROM mydb.jobinfo_jumpit
    JOIN mydb.jobinfo_jobplanet
    ON mydb.jobinfo_jumpit.company = mydb.jobinfo_jobplanet.company;
"""

def execute_sql_and_return_result(**kwargs):
    
    connection = pymysql.connect(
        host='database.c7muissskf9a.ap-northeast-2.rds.amazonaws.com',
        user='legoking',
        password='1q2w3e4r5t!',
        database='mydb'
    )

    try:
        # 커서 생성
        with connection.cursor() as cursor:
            # SQL 쿼리 실행
            sql_query = """
                SELECT mydb.jobinfo_jumpit.company, position, skills, average_salary, due_date, link
                FROM mydb.jobinfo_jumpit
                JOIN mydb.jobinfo_jobplanet
                ON mydb.jobinfo_jumpit.company = mydb.jobinfo_jobplanet.company;
            """
            cursor.execute(sql_query)

            # 결과 가져오기
            result = cursor.fetchall()
            
            # 표 생성
            table = PrettyTable()
            table.field_names = [i[0] for i in cursor.description]
            
            for row in result:
                table.add_row(row)
                
            result_str = str(table)
            print(result_str)
            
    finally:
        # 연결 닫기
        connection.close()
        
    return result_str

with DAG(
    'rds_test_2',
    default_args=default_args,
    schedule_interval='@once',
    start_date=datetime(2024, 1, 9),
    tags=['mysql', 'rds', 'test', 'job_info']
) as dag:
    t1 = MySqlOperator(
        task_id="rds_connection",
        mysql_conn_id="rds_conn",
        sql=sql_read_data,
        dag=dag
    )

    t2 = PythonOperator(
        task_id='execute_sql_and_return_result',
        python_callable=execute_sql_and_return_result,
        provide_context=True,
        op_args=[],
        op_kwargs={},
        dag=dag
    )

    t3 = SlackWebhookOperator(
        task_id='send_slack',
        http_conn_id='slack_conn',
        message=f'```오늘의 채용공고!!\n{{{{ task_instance.xcom_pull(task_ids="execute_sql_and_return_result") }}}}\n```',
        dag=dag
    )

    t1 >> t2 >> t3
