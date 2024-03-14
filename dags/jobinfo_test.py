
from airflow import DAG
from datetime import datetime, timedelta
from airflow.operators.bash import BashOperator
from airflow.operators.python import PythonOperator
from airflow.utils.dates import days_ago

default_args = {
    'start_date': days_ago(1),
}

dag = DAG(
	# firstDAG_test는 DAG의 이름. unique한 값을 가져야 함
    'firstDAG_test',
    # dag에서 사용할 기본적인 파라미터 값. 위에서 정의한 내용의 일부를 사용
    default_args=default_args,
    # DAG가 언제 실행될지 설정. "@once" : 한 번만 실행
    schedule_interval="@once",
)

def Hello_airflow():
    print("Hello airflow")

t1 = BashOperator(
    task_id='bash',
    bash_command='echo "Hello airflow"',
    dag=dag,
)

t2 = PythonOperator(
    task_id='python',
    python_callable=Hello_airflow,
    dag=dag,
)

t1 >> t2
