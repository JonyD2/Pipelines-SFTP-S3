import os
import time
import boto3
from botocore.exceptions import ClientError
from botocore.config import Config
from pathlib import Path
import logging
import urllib3

# Configurações a partir de variáveis de ambiente
REGION_NAME = os.getenv('AWS_REGION', '')
BUCKET_NAME = os.getenv('AWS_BUCKET_NAME', '')
PREFIX = os.getenv('AWS_S3_PREFIX', '')
DATABASE_NAME = os.getenv('ATHENA_DATABASE', '')
LOCAL_SAVE_PATH = Path(os.getenv('LOCAL_SAVE_PATH', ''))
VIEWS = ['campaign', 'campaign_push', 'vouchers', 'partners', 'downloads', 'customer', 'adobe_device', 'adobe_pages_accessed','adobe_performance', 'adobe_state_visits', 'resume_transaction_comparison', 'adobe_traffic_source', 'adobe_traffic_domains', 'adobe_visits', 'adobe_visits_daily']

# Configurações do cliente
boto_config = Config(region_name=REGION_NAME)

# Criação de clientes AWS
athena = boto3.client('athena', config=boto_config, verify=False)
s3 = boto3.client('s3', config=boto_config, verify=False)

# Configuração do Logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Desativa o aviso de "Insecure Request"
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

def execute_athena_query(query):
    try:
        response = athena.start_query_execution(
            QueryString=query,
            QueryExecutionContext={'Database': DATABASE_NAME},
            ResultConfiguration={'OutputLocation': f's3://{BUCKET_NAME}/{PREFIX}'}
        )
        return response['QueryExecutionId']
    except ClientError as e:
        logging.error(f"Erro ao executar a consulta Athena: {e}")
        return None

def check_query_execution(query_execution_id, max_attempts=10, wait_time=5):
    attempts = 0
    while attempts < max_attempts:
        try:
            response = athena.get_query_execution(QueryExecutionId=query_execution_id)
        except ClientError as e:
            logging.error(f"Erro ao verificar o status da execução: {e}")
            return None

        status = response['QueryExecution']['Status']['State']
        if status in ['SUCCEEDED', 'FAILED', 'CANCELLED']:
            if status == 'FAILED':
                reason = response['QueryExecution']['Status'].get('StateChangeReason', 'Sem razão especificada')
                logging.error(f"Consulta falhou: {reason}")
            return status
        
        attempts += 1
        time.sleep(wait_time)
        wait_time = min(wait_time * 2, 120)  # Timer

    return "TIMEOUT"


def save_results_to_local(query_execution_id, filename):
    s3_folder_path = f"{PREFIX}{query_execution_id}.csv"
    try:
        files = s3.list_objects_v2(Bucket=BUCKET_NAME, Prefix=s3_folder_path)
        for obj in files.get('Contents', []):
            s3_file_path = obj['Key']
            if s3_file_path.endswith('.csv') and not s3_file_path.endswith('.csv.metadata'):
                local_path = LOCAL_SAVE_PATH / filename
                s3.download_file(BUCKET_NAME, s3_file_path, str(local_path))
                logging.info(f"Arquivo salvo localmente em: {local_path}")
                break
    except ClientError as e:
        logging.error(f"Erro ao salvar o arquivo localmente: {e}")

def delete_s3_folder(bucket_name, prefix):
    try:
        objects_to_delete = s3.list_objects_v2(Bucket=bucket_name, Prefix=prefix)
        delete_keys = [{'Key': obj['Key']} for obj in objects_to_delete.get('Contents', [])]

        if delete_keys:
            response = s3.delete_objects(Bucket=bucket_name, Delete={'Objects': delete_keys})
            deleted = response.get('Deleted', [])
            if len(delete_keys) == len(deleted):
                logging.info(f"'{prefix}' folder and its contents have been successfully deleted from bucket '{bucket_name}'")
            else:
                logging.warning("Some objects may not have been deleted successfully.")
    except ClientError as e:
        logging.error(f"Failed to delete S3 folder: {e}")
 
def main():
    total_start_time = time.time()
    delete_s3_folder(BUCKET_NAME, PREFIX)

    queries = [f"SELECT * FROM refined.vw_dash_{view}" for view in VIEWS]

    for query in queries:
        start_time = time.time()
        logging.info(f"Executando consulta: {query}")

        view_name = query.split(' ')[3].split('.')[-1]
        filename = view_name.removeprefix("vw_") + '.csv'

        query_execution_id = execute_athena_query(query)
        status = check_query_execution(query_execution_id)
        
        if status == 'SUCCEEDED':
            logging.info(f"Consulta concluída com sucesso. Salvando resultados para {filename}")
            save_results_to_local(query_execution_id, filename)
        else:
            logging.info(f"Consulta falhou ou foi cancelada: {status}")

        logging.info(f"Consulta executada em {time.time() - start_time} segundos\n")

    logging.info(f"Script executado em {time.time() - total_start_time} segundos")

if __name__ == "__main__":
    main()
    