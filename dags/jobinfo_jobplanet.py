from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.models import Variable

from datetime import datetime, timedelta
import boto3
from io import StringIO
from datetime import datetime
from airflow.hooks.base import BaseHook
from airflow.hooks.S3_hook import S3Hook
from airflow.hooks.mysql_hook import MySqlHook

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver import ActionChains
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys  import  Keys
import pandas as pd
from konlpy.tag import Hannanum
from collections import Counter
import logging
import re

from csv import writer
import os
import io
global word
word=2
global page
page=4
global wait
wait=10

def get_S3_connection():
    aws_access_key = Variable.get('AWS_ACCESS_KEY')
    aws_secret_access_key = Variable.get('AWS_SECRET_KEY')

    s3_client = boto3.client(
        's3',
        aws_access_key_id=aws_access_key,
        aws_secret_access_key=aws_secret_access_key,
        region_name='ap-northeast-2'
    )
    return s3_client

def get_RDS_connection():
    mysql_hook = MySqlHook(mysql_conn_id='rds_conn')

    conn = mysql_hook.get_conn()
    return conn

def jobplanet_login(**kwargs):
    options = Options()
    options.add_argument('--headless')
    options.add_argument('window-size=2000x1500')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')

    # 쿠키 허용 설정 추가
    options.add_argument("--enable-features=NetworkService,NetworkServiceInProcess")
    options.add_argument("--disable-features=VizDisplayCompositor")
    options.add_argument("--disable-gpu")
    options.add_argument("--enable-automation")
    options.add_argument("--disable-software-rasterizer")
    options.add_argument("--disable-extensions")
    options.add_argument("--start-maximized")
    options.add_argument("--disable-features=EnableEphemeralFlashPermission")
    options.add_argument("--disable-save-password-bubble")

    # 클라우드 플레어(봇 감지를 우회) 추가
    options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36")
    # Chrome 프로필 설정
    chrome_prefs = {
        'profile.default_content_setting_values': {
            'cookies': 1,  # 1: 모든 쿠키 허용
            'images': 1,   # 1: 이미지 표시
            # 다른 설정들도 필요에 따라 추가
        }
    }
    remote_webdriver = 'remote_chromedriver'
    with webdriver.Remote(f'{remote_webdriver}:4444/wd/hub', options=options) as driver:
    # Scraping part
        driver.get("https://jobplanet.co.kr/users/sign_in")
        driver.implicitly_wait(wait)
        jobplanet_id = Variable.get('JOBPLANET_ID')
        jobplanet_password = Variable.get('JOBPLANET_PASSWORD')

# 아이디 입력, variable 계정정보 뺼것
        driver.maximize_window()
        id_input = driver.find_element(By.ID, "user_email")
        ActionChains(driver).send_keys_to_element(id_input, jobplanet_id).perform()
        driver.implicitly_wait(wait)

# 비밀번호입력
        pw_input = driver.find_element(By.ID, 'user_password')
        ActionChains(driver).send_keys_to_element(pw_input, jobplanet_password).perform()
        driver.implicitly_wait(wait)

# 로그인
        login_button = driver.find_element(By.CLASS_NAME,"btn_sign_up")
        ActionChains(driver).click(login_button).perform()
        driver.implicitly_wait(wait)

        companies = kwargs['ti'].xcom_pull(task_ids='load_jumpit_file')
        file_list = kwargs['ti'].xcom_pull(task_ids='read_s3_file')
        bucket_name = Variable.get('AWS_S3_BUCKET')
        driver.implicitly_wait(wait)
        bucket_name = Variable.get('AWS_S3_BUCKET')
        # companies=list(set(companies))
        logging.info(companies)
        logging.info(file_list)
        logging.info("시작")
        create_num = 0
        for company in companies:
            # 이미 존재하면 패스
            if f'path/in/s3/bucket/review_information_{company}.csv' in file_list:
                logging.info(f"{company} 있음")  
                continue
            # 없으면 만듦
            else:
                try:
                    # 검색창에 회사이름 친다
                    driver.maximize_window()
                    logging.info(f"{company} 파일이 없음")
                    search_company = driver.find_element(By.ID, "search_bar_search_query")
                    search_company.clear()
                    ActionChains(driver).send_keys_to_element(search_company, company).perform()
                    #search_company.send_keys(company)
                    logging.info(f"{company} 검색을 위해 검색창에 입력했습니다.")
                    search_company.send_keys(Keys.RETURN)
                    driver.implicitly_wait(wait)
                    logging.info(f"{company} 검색하기")

                # 검색 클릭
                    driver.find_element(By.XPATH, "/html/body/div[1]/div[2]/div/div[1]/div[1]/div/div[2]/div[1]/div/a").click()
                    driver.implicitly_wait(wait)
                    logging.info(f'{company} 회사 정보를 알기 위해 상세정보 클릭합니다.')
                # 크롤링 시행 바로밑에 있음
                    review_data = review_crawling(driver)
                    upload_to_s3(review_data, f'path/in/s3/bucket/review_information_{company}.csv', bucket_name)
                    file_list.append(f'path/in/s3/bucket/review_information_{company}.csv')
                    review_wordcloud = wordcloud_info(companies[0])
                    create_num = create_num + 1
                except:
                    logging.info(f'{company}의 정보는 없어서 파일 생성을 못한다.')
            if create_num == 15:
                break
            
            logging.info(file_list)

        s3_key = Variable.get('AWS_S3_KEY')
        if s3_key not in file_list:
            # 요약본 파일이 없는 경우, 정보수집 방법
            try:
                # 정보수집
                review_wordcloud = wordcloud_info(companies[0])
                company_salary_info = create_salary_infomation(driver, companies[0])
            except:
                pass
            entire_summary = pd.DataFrame({
                'company' : [companies[0]],
                'review_summary': [review_wordcloud[0]],
                'merit_summary': [review_wordcloud[1]],
                'demerit_summary': [review_wordcloud[2]],
                'interview_summary': [review_wordcloud[3]],
                'question_summary': [review_wordcloud[4]],
                'answer_summary': [review_wordcloud[5]],
                'average_salary' : [company_salary_info],
            })
            entire_summary.dropna(axis=1)

            upload_to_s3(entire_summary, s3_key, bucket_name)
            companies = companies[1:]

        # 전체 요약본 파일이 rds에 있을 때 정보수집 방법
        # 그 파일을 읽음
        s3_client = get_S3_connection()
        for company in companies:
            try:
                obj = s3_client.get_object(Bucket=bucket_name, Key=s3_key)
                df = pd.read_csv(obj['Body'], encoding='utf-8')
            except Exception as e:
                logging.info(f"Failed to read CSV file from S3: {e}")
            # 이미 요약본 자료가 존재하는 회사들 추출
            summary_company = df['company'].tolist() 


        # 그 회사들은 넘긴다.(=요약본에 있는 회사들)
            if company in summary_company:
                continue
        # 존재하지 않는다.(=요약본에 없는 회사들)
            else:
                try:
                # 워드 클라우드
                    review_wordcloud = wordcloud_info(company)
                # 연봉 정보 뽑음
                    company_salary_info = create_salary_infomation(driver, company)
                # 회사명과 정보들을 하나의 리스트로 모으기 
                    logging.info("summary file upload s3")
                    logging.info(df.head())
                    new_df = pd.DataFrame({
                    'company' : [company],
                    'review_summary': [review_wordcloud[0]],
                    'merit_summary': [review_wordcloud[1]],
                    'demerit_summary': [review_wordcloud[2]],
                    'interview_summary': [review_wordcloud[3]],
                    'question_summary': [review_wordcloud[4]],
                    'answer_summary': [review_wordcloud[5]],
                    'average_salary' : [company_salary_info],
                })
                    logging.info(new_df.head())
                    #df.dropna(axis=1)
                    #new_df.dropna(axis=1)
                    merged_df = pd.concat([df, new_df], ignore_index=True)
                    #merged_df.dropna(axis=1)
                    upload_to_s3(merged_df, s3_key, bucket_name)
                    logging.info("Data appended successfully.")
                except:
                    pass

# 회사별로 긴 정보 s3에 저장
def create_infomation_s3(**kwargs):
        driver = jobplanet_login()


def review_crawling(driver):
    review = [] # 리뷰
    merit = []  # 장점
    demerit = [] # 단점
    interview_summary = []  # 면접 한줄 요약
    interview_question = [] # 면접 질문
    interview_answer = []   # 면접 답변 또는 분위기
    hire_way = []   # 채용 방식
    result_date = []    # 결과 발표 시기

    # 팝업장 제거1 클릭
    try:
        driver.find_element(By.CLASS_NAME,"ab-close-button").click()
        driver.implicitly_wait(wait)
    except:
        pass

    # 팝업장 제거2 클릭
    try:
        driver.find_element(By.CLASS_NAME, "btn_close_x_ty1").click()
        driver.implicitly_wait(wait)
    except:
        pass

    # 리뷰 갯수 세는거
    try:
        review_count = driver.find_element(By.ID, "viewReviewsTitle").find_element(By.CLASS_NAME, "num").text
        review_count = int(review_count)
    except:
        review_count = 0

    # 리뷰페이지에서 4페이지만 뽑음 , 카운트 페이지마다 새는거로 바꿀것
    for _ in range(page):
        reviews = driver.find_elements(By.CLASS_NAME, "content_wrap")

        for i in reviews:
            try:
                summary = (i.find_element(By.CLASS_NAME, "us_label ")).text
                summary = summary.replace(".", "").replace("\n", " ").replace('\"',"")
                review.append(summary)

                review_detail = i.find_elements(By.CLASS_NAME, "df1")
                merit.append(review_detail[0].text.replace(".", "").replace("\n", " ").replace('\"',""))
                demerit.append(review_detail[1].text.replace(".", "").replace("\n", " ").replace('\"',""))
            except:
                pass

        # 총리뷰 갯수가 5개보다 많다면 다음 페이지 이동,
        review_count = review_count - 5
        if review_count > 0:
            try:
                driver.find_element(By.CLASS_NAME, "btn_pgnext").click()
                driver.implicitly_wait(wait)
            except:
                pass
        else:
            break

    # 면접탭으로 넘어감
    selector = "#viewCompaniesMenu > ul > li.viewInterviews > a"
    link = driver.find_element(By.CSS_SELECTOR, selector)
    interview_url = link.get_attribute('href')
    driver.get(interview_url)
    driver.implicitly_wait(wait)

    # 팝업 없애기
    try:
        driver.find_element(By.CLASS_NAME, "btn_delete_follow_banner").click()
        driver.implicitly_wait(wait)
    except:
        pass

    # 직군 선택버튼
    driver.find_element(By.XPATH, '//*[@id="occupation_select"]').click()
    driver.implicitly_wait(wait)

    # 전체 직군 면접 리뷰 갯수 세는거
    interview_count = driver.find_element(By.ID, "viewInterviewsTitle").find_element(By.CLASS_NAME, "num").text
    interview_count = int(interview_count)

    try:
        # 데이터(11912) 직군 선택
        driver.find_element(By.XPATH, "//select/option[@value='11912']").click()
        driver.implicitly_wait(wait)

        # 데이터 직군 한정 면접 리뷰 개수
        interview_count = driver.find_element(By.ID, "viewInterviewsTitle").find_elements(By.CLASS_NAME, "num")[1].text
        interview_count = int(interview_count)
    except:
        pass

    try:
        # 데이터 직군이 없을 때 개발 직군을 선택
        driver.find_element(By.XPATH, "//select/option[@value='11600']").click()
        driver.implicitly_wait(wait)

        # 개발 직군 한정 면접 리뷰 개수
        interview_count = driver.find_element(By.ID, "viewInterviewsTitle").find_elements(By.CLASS_NAME, "num")[1].text
        interview_count = int(interview_count)
    except:
        pass

    # 면접리뷰 2페이지 추출
    for _ in range(page):
        reviews = driver.find_elements(By.CLASS_NAME, "content_wrap")

        for i in reviews:
            try:
                # 면접 리뷰 수집
                # 면접 리뷰 한 줄로 요약
                review_summary = (i.find_element(By.CLASS_NAME, "us_label.")).text
                #문장 한 줄로 바꾸고 전처리
                review_summary = review_summary.replace(".", "").replace("\n", " ").replace('\"', "")
                # 문장 interview_summary에 추가
                interview_summary.append(review_summary)
            except:
                interview_summary.append("no data")

            try:
                #면접질문이 어떤게 나왔는지 수집
                review_detail = i.find_elements(By.CLASS_NAME, "df1")
                interview_question.append(review_detail[0].text.replace(".", "").replace("\n", " ").replace('\"',""))
            except:
                interview_question.append("no data")

            try:
                #면접직문에 어떤 답을 했는지
                review_detail = i.find_elements(By.CLASS_NAME, "df1")
                interview_answer.append(review_detail[1].text.replace(".", "").replace("\n", " ").replace('\"',""))
            except:
                interview_answer.append("no data")

            try:
                # 면접방식(그룹,1:1면접,ppt)
                review_detail = i.find_elements(By.CLASS_NAME, "df1")
                hire_way.append(review_detail[2].text.replace(".", "").replace("\n", " ").replace('\"',""))
            except:
                hire_way.append("no data")
            
            try:
                # 결과 발표시기
                review_detail = i.find_elements(By.CLASS_NAME, "df1")
                result_date.append(review_detail[3].text.replace(".", "").replace("\n", " ").replace('\"',""))
            except:
                result_date.append("no data")

        # 리뷰 5개 이상 모으면 다음 페이지
        if interview_count > 5:
            try:
                driver.find_element(By.CLASS_NAME, "btn_pgnext").click()
                driver.implicitly_wait(wait)
            except:
                pass
        else:
            break

    # 리뷰 없으면 0리턴
    if len(review) == 0 and len(interview_summary) == 0:
        return 0

    # 리뷰,면접리뷰 중 리뷰 갯수가 많으면, 면접리뷰 리스트의 길이를 거기에 맞춤
    if len(review) > len(interview_summary):
        tmp = ["no data"] * (len(review) - len(interview_summary))
        # 리스트+리스트 로 리스트 길이를 맞춤
        interview_summary = interview_summary + tmp
        interview_question = interview_question + tmp
        interview_answer = interview_answer + tmp
        hire_way = hire_way + tmp
        result_date = result_date + tmp
        
     # 리뷰,면접리뷰 중 면접리뷰 갯수가 많으면, 리뷰 리스트의 길이를 거기에 맞춤
    elif len(review) < len(interview_summary):
        tmp = ["no data"] * (len(interview_summary) - len(review))
        review = review + tmp
        merit = merit + tmp
        demerit = demerit + tmp

    # 데이터 프레임 만듦
    result_info = pd.DataFrame({
        'review_summary' : review,
        'merit' : merit,
        'demerit' : demerit,
        'interview_summary' : interview_summary,
        'interview_question' : interview_question,
        'interview_answer' : interview_answer,
        'hire_way' : hire_way,
        'result_date' : result_date,
    })
    return result_info

# s3에 있는 파일을 불러와서 데이터 작업 후 rds에 있는 파일에 넣기
def create_summary_s3_to_rds(**kwargs):
    driver = jobplanet_login()
    companies = kwargs['ti'].xcom_pull(task_ids='load_jumpit_file')
    file_list = kwargs['ti'].xcom_pull(task_ids='read_s3_file')
    bucket_name = Variable.get('AWS_S3_BUCKET')
    s3_key = Variable.get('AWS_S3_KEY')
    # companies=list(set(companies))
    if s3_key not in file_list:
        # 요약본 파일이 없는 경우, 정보수집 방법
        try:
            # 정보수집
            review_wordcloud = wordcloud_info(companies[0])
            company_salary_info = create_salary_infomation(driver, companies[0])
        except:
            pass
        entire_summary = pd.DataFrame({
                'company' : [companies[0]],
                'review_summary': [review_wordcloud[0]],
                'merit_summary': [review_wordcloud[1]],
                'demerit_summary': [review_wordcloud[2]],
                'interview_summary': [review_wordcloud[3]],
                'question_summary': [review_wordcloud[4]],
                'answer_summary': [review_wordcloud[5]],
                'average_salary' : [company_salary_info],
            })
        entire_summary.dropna(axis=1)
        upload_to_s3(entire_summary, s3_key, bucket_name)
        companies = companies[1:]

    # 전체 요약본 파일이 rds에 있을 때 정보수집 방법
    # 그 파일을 읽음
    s3_client = get_S3_connection()
    try:
        obj = s3_client.get_object(Bucket=bucket_name, Key=s3_key)
        df = pd.read_csv(obj['Body'], encoding='utf-8')
    except Exception as e:
        logging.info(f"Failed to read CSV file from S3: {e}")

    # 이미 요약본 자료가 존재하는 회사들 추출
    summary_company = df['company'].tolist() 
    for company in companies:
        # 그 회사들은 넘긴다.(=요약본에 있는 회사들)
        if company in summary_company:
            continue
        # 존재하지 않는다.(=요약본에 없는 회사들)
        else:
            driver = jobplanet_login()
            try:
                # 워드 클라우드
                review_wordcloud = wordcloud_info(company)
                # 연봉 정보 뽑음
                company_salary_info = create_salary_infomation(driver, company)
                # 회사명과 정보들을 하나의 리스트로 모으기 
                new_df = pd.DataFrame({
                    'company' : [company],
                    'review_summary': [review_wordcloud[0]],
                    'merit_summary': [review_wordcloud[1]],
                    'demerit_summary': [review_wordcloud[2]],
                    'interview_summary': [review_wordcloud[3]],
                    'question_summary': [review_wordcloud[4]],
                    'answer_summary': [review_wordcloud[5]],
                    'average_salary' : [company_salary_info],
                })
                df.dropna(axis=1)
                new_df.dropna(axis=1)
                merged_df = pd.concat([df, new_df], ignore_index=True)
                merged_df.dropna(axis=1)
                upload_to_s3(merged_df, s3_key, bucket_name)
                logging.info("Data appended successfully.")
            except:
                pass

    
# 연봉정보 뽑는 함수
def create_salary_infomation(driver, company):
    # 팝업창 닫기
    try:
        driver.find_element(By.CLASS_NAME, "ab-close-button").click()
    except:
        pass

    try:
        search_company = driver.find_element(By.ID, "search_bar_search_query")
        search_company.clear()
        search_company.send_keys(company)
        #엔터 누르는거
        search_company.send_keys(Keys.RETURN)
        driver.implicitly_wait(wait)
        # 검색해서 나오는 회사중 맨 앞의 회사 클릭
        driver.find_element(By.CLASS_NAME, "tit").click()
        driver.implicitly_wait(wait)
    except:
        pass

    # 팝업창 닫기 1   
    try:
        driver.find_element(By.CLASS_NAME,"ab-close-button").click()
        driver.implicitly_wait(wait)
    except:
        pass
    
    #팝업창 닫기 2
    try:
        driver.find_element(By.CLASS_NAME, "btn_close_x_ty1").click()
        driver.implicitly_wait(wait)
    except:
        pass

    # 연봉 탭 클릭
    try:
        selector = "#viewCompaniesMenu > ul > li.viewSalaries > a"
        link = driver.find_element(By.CSS_SELECTOR, selector)
        salary_url = link.get_attribute('href')
        driver.get(salary_url)
        driver.implicitly_wait(wait)
    except:
        return "no data"

    # 그 기업의 평균연봉 정보 수집
    try:
        average = driver.find_element(By.CLASS_NAME, "chart_header")
        average = average.find_element(By.CLASS_NAME, "num")
        average_salary = average.text
        return average_salary
    except:
        average_salary = "정보 없음"
        logging.info(f'{company} salary information not find')
        return average_salary

# 워드클라우드 요약하는 함수
def wordcloud_info(company):
    s3_client = get_S3_connection()
    try:
        obj = s3_client.get_object(Bucket=Variable.get('AWS_S3_BUCKET'), Key=f"path/in/s3/bucket/review_information_{company}.csv")
        df = pd.read_csv(obj['Body'], encoding='utf-8')
        logging.info(df.head())

        words = []

        # 리뷰요약에 대해서, 많이 나오는 단어 새고, 한줄로 만듦
        text = ' '.join(df['review_summary'].tolist())
        words = text.split()

        # words를 센다.
        review_summary_counters = Counter(words)
        # counter가 사전 형식임. 단어가 1자리보다는 많고, 2개이상 나오는 단어
        del review_summary_counters['no']
        del review_summary_counters['data']
        review_summary_counter = {k: v for k, v in review_summary_counters.items() if len(k) >= word} 

        # 위에꺼, 갯수가 많은 순서대로 정렬
        if len(review_summary_counter) > 0:
            key = sorted(review_summary_counter, key=review_summary_counter.get, reverse=True)
            review_summary_key = key[:10]
            # ,를 넣고 한줄로 만듦
            review_summary = ', '.join(review_summary_key)

        elif len(review_summary_counters) == 0:
            review_summary = "없음"

        # 조건에 만족 못했어도 넣어야 하니까, 원본을 한줄로 만듦      
        else:
            key = sorted(review_summary_counters, key=review_summary_counters.get, reverse=True)
            review_summary_key = key[:10]
            review_summary = ', '.join(review_summary_key)

        # 리뷰의 장점에 대해서 위에와 똑같이 시행
        text = ' '.join(df['merit'].tolist())
        words = text.split()
        merit_counters = Counter(words)
        del merit_counters['no']
        del merit_counters['data']
        merit_counter = {k: v for k, v in merit_counters.items() if len(k) >= word}
        if len(merit_counter) > 0:
            key = sorted(merit_counter, key=merit_counter.get, reverse=True)
            merit_key = key[:10]
            merit = ', '.join(merit_key)
        elif len(merit_counters) == 0:
            merit = "없음"
        else:
            key = sorted(merit_counters, key=merit_counters.get, reverse=True)
            merit_key = key[:10]
            merit = ', '.join(merit_key)

        text = ' '.join(df['demerit'].tolist())
        words = text.split()
        # 리뷰의 단점에 대해서 위에와 똑같이 시행
        demerit_counters = Counter(words)
        del demerit_counters['no']
        del demerit_counters['data']
        demerit_counter = {k: v for k, v in demerit_counters.items() if len(k) >= word}
        if len(demerit_counter) > 0:
            key = sorted(demerit_counter, key=demerit_counter.get, reverse=True)
            demerit_key = key[:10]
            demerit = ', '.join(demerit_key)
        elif len(demerit_counters) == 0:
            demerit = "없음"
        else:
            key = sorted(demerit_counters, key=demerit_counters.get, reverse=True)
            demerit_key = key[:10]
            demerit = ', '.join(demerit_key)

        text = ' '.join(df['interview_summary'].tolist())
        words = text.split()
        # 인터뷰 요약에 대해서 위에와 똑같이 시행
        interview_summary_counters = Counter(words)
        del interview_summary_counters['no']
        del interview_summary_counters['data']
        interview_summary_counter = {k: v for k, v in interview_summary_counters.items() if len(k) >= word}
        if len(interview_summary_counter) > 0:
            key = sorted(interview_summary_counter, key=interview_summary_counter.get, reverse=True)
            interview_summary_key = key[:10]
            interview_summary = ', '.join(interview_summary_key)
        elif len(interview_summary_counters) == 0:
            interview_summary = "없음"
        else:
            key = sorted(interview_summary_counters, key=interview_summary_counters.get, reverse=True)
            interview_summary_key = key[:10]
            interview_summary = ', '.join(interview_summary_key)

        text = ' '.join(df['interview_question'].tolist())
        words = text.split()
        # 인터뷰 질문에 대해서 위에와 똑같이 시행
        interview_question_counters = Counter(words)
        del interview_question_counters['no']
        del interview_question_counters['data']
        interview_question_counter = {k: v for k, v in interview_question_counters.items() if len(k) >= word}
        if len(interview_question_counter) > 0:
            key = sorted(interview_question_counter, key=interview_question_counter.get, reverse=True)
            interview_question_key = key[:10]
            interview_question = ', '.join(interview_question_key)
        elif len(interview_question_counters) == 0:
            interview_question = "없음"
        else:
            key = sorted(interview_question_counters, key=interview_question_counters.get, reverse=True)
            interview_question_key = key[:10]
            interview_question = ', '.join(interview_question_key)

        text = ' '.join(df['interview_answer'].tolist())
        words = text.split()
        #면접 답변에 대해서 위와 같이 진행
        interview_answer_counters = Counter(words)
        del interview_answer_counters['no']
        del interview_answer_counters['data']
        interview_answer_counter = {k: v for k, v in interview_answer_counters.items() if len(k) >= word}
        if len(interview_answer_counter) > 0:
            key = sorted(interview_answer_counter, key=interview_answer_counter.get, reverse=True)
            interview_answer_key = key[:10]
            interview_answer = ', '.join(interview_answer_key)
        elif len(interview_answer_counters) == 0:
            interview_answer = "없음"
        else:
            key = sorted(interview_answer_counters, key=interview_answer_counters.get, reverse=True)
            interview_answer_key = key[:10]
            interview_answer = ', '.join(interview_answer_key)

        arguments = (review_summary, merit, demerit, interview_summary, interview_question, interview_answer)
        cleaned_result = [re.sub(r'\x1b\[[0-9;]*m', '', arg) for arg in arguments]

        # 결과들 한줄로
        return cleaned_result
    except Exception as e:
        logging.info(f'{company} 정보 없ㅇ,ㅡ')
        logging.info(f"Failed to read CSV file from S3: {e}")
        return ["정보 없음"] * 6

    



# 점핏에서 저장한 정보 가져와서, 회사 이름만 수집
def load_jumpit_file():
    s3_hook = S3Hook(aws_conn_id='s3_conn')
    try:
        s3_client = get_S3_connection()
        bucket_name = Variable.get('AWS_S3_BUCKET')
        file_key = "path/in/s3/bucket/jobinfo_jumpit.csv"
        obj = s3_client.get_object(Bucket=bucket_name, Key=file_key)
        df = pd.read_csv(io.BytesIO(obj['Body'].read()))
        if 'company' not in df.columns:
            raise ValueError("'company' 컬럼이 데이터프레임에 존재하지 않습니다.")
        companies = df['company'].tolist()
        logging.info(companies)
        return companies
    except Exception as e:
        print(f"오류 발생: {e}")
        return []

def read_s3_file():
    conn = get_S3_connection()
    bucket_name = Variable.get('AWS_S3_BUCKET')
    if conn:
        logging.info("none")
    else:
        logging("conn: {conn}")
    try:
        response = conn.list_objects(Bucket=bucket_name)
        file_list = [obj['Key'] for obj in response.get('Contents', [])]
        return file_list
    except Exception as e:
        print(f"Error getting file list from S3: {e}")
        return []


def upload_to_s3(dataframe, file_name, bucket_name):
    s3_clinet = get_S3_connection()
    try:
        csv_buffer = StringIO()
        dataframe.to_csv(csv_buffer, index=False)

        s3_clinet.put_object(Body=csv_buffer.getvalue(), Bucket=bucket_name, Key=file_name)
        logging.info(f"File {file_name} uploaded to S3 successfully.")
    except Exception as e:
        logging.info(f"Error uploading file to S3: {e}")

def s3_to_rds():
    s3_client = get_S3_connection()

    s3_bucket = Variable.get('AWS_S3_BUCKET')
    s3_key = Variable.get('AWS_S3_KEY')
    s3_object = s3_client.get_object(Bucket=s3_bucket, Key=s3_key)

    datas = pd.read_csv(s3_object['Body'], encoding='utf-8')
    data = datas.where(pd.notnull(datas), None)
    conn = get_RDS_connection()
    conn.select_db('mydb')
    cur = conn.cursor()

    # 테이블에 데이터가 있으면 지우고 삽입하도록 설정
    if not data.empty:
        delete_query = "DELETE FROM jobinfo_jobplanet"
        cur.execute(delete_query)
    
    insert_query = f"INSERT INTO jobinfo_jobplanet ({', '.join(data.columns)}) VALUES ({', '.join(['%s'] * len(data.columns))})"
    for _, row in data.iterrows():
        cur.execute(insert_query, tuple(row))
        logging.info("sql insert start")

    conn.commit()
    cur.close()
    conn.close()


default_args = {
    'start_date': datetime(2024,1,10),
    
}

with DAG(
    dag_id = "jobinfo_jobplanet",
    schedule = '46 11 * * *',
    catchup = False,
    default_args=default_args,
) as dag:
    
    task1 = PythonOperator(
        task_id = 'load_jumpit_file',
        python_callable=load_jumpit_file,
        #provide_context = True,
        dag = dag,
    )
    task2 = PythonOperator(
        task_id = 'read_s3_file',
        python_callable=read_s3_file,
        #provide_context = True,
        dag=dag
    )
    task3 = PythonOperator(
        task_id = 'jobplanet_login',
        python_callable=jobplanet_login,
        dag=dag,
    )
    task4 = PythonOperator(
        task_id='s3_to_rds',
        python_callable=s3_to_rds,
        dag=dag,
    )

    task1 >> task2 >> task3 >> task4