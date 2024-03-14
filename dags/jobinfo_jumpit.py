<<<<<<< HEAD
=======
# 최신
>>>>>>> e85bad369270f57d81da8fe68dc3a4c8bc694d76
import csv
import logging
import os
from datetime import datetime, timedelta

import boto3
import pandas as pd
import requests
from airflow import DAG
from airflow.hooks.base import BaseHook
from airflow.hooks.mysql_hook import MySqlHook
from airflow.hooks.S3_hook import S3Hook
from airflow.operators.python import PythonOperator
from bs4 import BeautifulSoup


def get_job_details(job_url, user_agent):
    res = requests.get(job_url, user_agent)
    soup = BeautifulSoup(res.text, "html.parser")
    descriptions = soup.find_all("dl", class_="sc-2da322c6-1")
    due_date = descriptions[2].find("dd").get_text()

    return due_date


def crawl_jobs(base_url, keyword, user_agent):
    selected_jobs = {}
    res = requests.get(f"{base_url}/search?sort=relation&keyword={keyword}", user_agent)
    soup = BeautifulSoup(res.text, "html.parser")
    jobs = soup.find_all("div", class_="sc-c8169e0e-0")

    for job in jobs:
        company_info = job.find("div", class_="sc-635ec9d6-0")

        # 회사명, 직무, 상세 링크, 기술 스택
        company = company_info.find("div").get_text(strip=True)
        position = job.find("h2", class_="position_card_info_title").get_text(strip=True)
        job_url = job.find("a")["href"]
        link = f"{base_url}{job_url}"
        skills = company_info.find("ul").get_text(strip=True)
        items = company_info.find_all("ul")[-1]
        location = items.find_all("li")[0].get_text(strip=True)
        career = items.find_all("li")[1].get_text(strip=True)

        # 중복 항목 확인
        job_id = link  # 채용 공고의 URL을 고유 식별자로 사용
        if job_id not in selected_jobs:
            due_date = get_job_details(link, user_agent)
            result = {
                "link": link,  # link를 pk로 사용
                "company": company,
                "position": position,
                "skills": skills,
                "location": location,
                "career": career,
                "due_date": due_date
            }

            # 공백 제거 후 출력
            result = {key: value.strip() if isinstance(value, str) else value for key, value in result.items()}
            selected_jobs[job_id] = result

    return selected_jobs


def jumpit_crawling():
    base_url = "https://www.jumpit.co.kr"
    user_agent = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_4) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/83.0.4103.97 Safari/537.36"}
    # keywords = ["데이터 엔지니어", "데이터 엔지니어링", "데이터 분석가", "데이터 분석", "데이터 사이언티스트", "데이터 사이언스"]
    keywords = ["클라우드", "백엔드"]
    all_selected_jobs = {}
    
    for keyword in keywords:
        selected_jobs = crawl_jobs(base_url, keyword, user_agent)
        all_selected_jobs.update(selected_jobs)
    
    return all_selected_jobs


def write_to_csv(**context):
    selected_jobs = context["task_instance"].xcom_pull(key="return_value", task_ids="extract")
    data = [job.values() for job in selected_jobs.values()]

    # 현재 DAG 파일이 있는 디렉토리를 기준으로 파일 경로 지정
    file_path = os.path.join(os.path.dirname(__file__), 'jumpit.csv')
    logging.info(f"Attempting to write to: {file_path}")
    try: 
        with open(file=file_path, mode='w', encoding='utf-8', newline='') as file:
            writer = csv.writer(file)
            
            # 헤더 작성, 정수 인덱스 사용
            writer.writerow(list(selected_jobs[list(selected_jobs.keys())[0]].keys()))
            
            # 데이터 작성
            writer.writerows(data)
        logging.info(f"File successfully written to: {file_path}")
        context['task_instance'].xcom_push(key='return_value', value={'file_path': file_path})
        return file_path
    except Exception as e:
        logging.info(f"Error writing to file: {e}")


def upload_to_s3(filename: str, key: str, bucket_name: str) -> None:
    s3_hook = S3Hook(aws_conn_id='s3_conn')
    s3_hook.load_file(
        filename=filename,
        key=key,
        bucket_name=bucket_name,
        replace=True,
    )
    logging.info(f"File successfully uploaded to S3. Bucket: {bucket_name}, Key: {key}")


def s3_to_rds(s3_bucket, s3_key, **kwargs):
    s3_hook = BaseHook.get_connection('s3_conn')
    s3_client = boto3.client(
        's3',
        aws_access_key_id=s3_hook.login,
        aws_secret_access_key=s3_hook.password,
        region_name='ap-northeast-2',
    )

    s3_object = s3_client.get_object(Bucket=s3_bucket, Key=s3_key)

    data = pd.read_csv(s3_object['Body'], encoding='utf-8')
    mysql_hook = MySqlHook(mysql_conn_id='rds_conn')

    connection = mysql_hook.get_conn()
    cursor = connection.cursor()

    if not data.empty:
        delete_query = "DELETE FROM jobinfo_jumpit"
        cursor.execute(delete_query)
    
    insert_query = f"INSERT INTO jobinfo_jumpit ({', '.join(data.columns)}) VALUES ({', '.join(['%s'] * len(data.columns))})"
    for _, row in data.iterrows():
        cursor.execute(insert_query, tuple(row))

    connection.commit()
    cursor.close()


dag = DAG(
    dag_id = 'jumpit_jobinfo',
    start_date = datetime(2024, 1, 9),
<<<<<<< HEAD
    schedule = '56 11 * * *',
=======
    schedule = '0 9 * * *',
>>>>>>> e85bad369270f57d81da8fe68dc3a4c8bc694d76
    catchup = False,
    max_active_runs = 1,
    default_args = {
        'retries': 1,
        'retry_delay': timedelta(minutes=3),
    }
)


extract = PythonOperator(
    task_id = 'extract',
    python_callable = jumpit_crawling,
    op_kwargs={
        'base_url': "https://www.jumpit.co.kr",
        'user_agent': {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_4) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/83.0.4103.97 Safari/537.36"}
    },
    provide_context=True,
    dag = dag
)


save_to_csv = PythonOperator(
    task_id = 'save_to_csv',
    python_callable = write_to_csv,
    provide_context=True,
    dag = dag
)


upload_to_s3 = PythonOperator(
    task_id = 'upload_to_s3',
    python_callable = upload_to_s3,
    provide_context = True,
    op_kwargs = {
            'filename' : '/opt/airflow/dags/jumpit.csv',
<<<<<<< HEAD
            'key': 'path/in/s3/bucket/jobinfo_jumpit.csv',
=======
            'key': 'path/in/s3/bucket/jobinfo_jumpit_v2.csv',
>>>>>>> e85bad369270f57d81da8fe68dc3a4c8bc694d76
            'bucket_name' : 'legoking'
    },
    dag = dag
)


s3_to_rds = PythonOperator(
    task_id = 's3_to_rds',
    python_callable = s3_to_rds,
    provide_context = True,
    op_kwargs = {
        's3_bucket': 'legoking',
<<<<<<< HEAD
        's3_key': 'path/in/s3/bucket/jobinfo_jumpit.csv'
=======
        's3_key': 'path/in/s3/bucket/jobinfo_jumpit_v2.csv'
>>>>>>> e85bad369270f57d81da8fe68dc3a4c8bc694d76
    },
    dag = dag
)


<<<<<<< HEAD
extract >> save_to_csv >> upload_to_s3 >> s3_to_rds
=======
extract >> save_to_csv >> upload_to_s3 >> s3_to_rds
>>>>>>> e85bad369270f57d81da8fe68dc3a4c8bc694d76
