import asyncio
import asyncssh
import boto3
import os
import sys
import time

# Configurações
SFTP_HOST = 'HOST'
SFTP_USER = 'USER'
SFTP_PASS = 'PASS'
SFTP_PORT = 'PORT'
S3_BUCKET = 'BUCKET'
S3_FOLDER = "DIRECTORY"
TEMP_PATH = r'LOCAL_PATH'

async def download_and_upload(sftp, s3_client, semaphore, filename):
    remote_path = f"/{filename}"
    local_path = os.path.join(TEMP_PATH, filename)
    s3_key = f"{S3_FOLDER.strip('/')}/{filename}"
    
    async with semaphore:
        start_time = time.time()
        start_datetime = time.strftime('%H:%M:%S', time.localtime(start_time))
        
        print(f"\n[{filename}] Download iniciado às {start_datetime}...")
        
        # Download
        try:
            total_downloaded = 0
            chunk_size = 5000000  # Buffer
            attrs = await sftp.stat(remote_path)
            total_size_bytes = attrs.size
            
            async with sftp.open(remote_path, 'rb') as remote_file:
                with open(local_path, 'wb') as local_file:
                    while True:
                        data = await remote_file.read(chunk_size)
                        if not data:
                            break
                        local_file.write(data)
                        
                        total_downloaded += len(data)
                        elapsed = time.time() - start_time
                        
                        archive_size = total_size_bytes / (1024 * 1024 * 1024)
                        downloaded_gb = total_downloaded / (1024 * 1024 * 1024)

                        # Progresso/Velocidade de download
                        if elapsed > 0:
                            speed_mbs = (total_downloaded / (1024 * 1024)) / elapsed
                            print(f"[{filename}] Baixado: {downloaded_gb:.2f} GB / {archive_size:.2F} GB | {speed_mbs:.2f} MB/s", end='\r')
            
            print(f"\n[{filename}] Download concluído. Enviando para o S3.")

            # Upload S3
            s3_client.upload_file(local_path, S3_BUCKET, s3_key)
            
            print(f"[{filename}] Upload concluído. Removendo arquivo local.")

            print(f"[{filename}] Limpeza local concluída. Removendo arquivo do SFTP")
            await sftp.remove(remote_path)

            end_time = time.time()
            end_datetime = time.strftime('%H:%M:%S', time.localtime(end_time))
            total_duration = (end_time - start_time) / 60

            print(f"\n[{filename}] Processo concluído às {end_datetime}. Duração: {total_duration:.1f} minutos.")

            # Limpa os arquivos locais
            os.remove(local_path)
            
        except Exception as e:
            print(f"\nERRO ao processar [{filename}]: {e}")
            if os.path.exists(local_path):
                os.remove(local_path)

async def main():
    if not os.path.exists(TEMP_PATH):
        os.makedirs(TEMP_PATH)

    s3_client = boto3.client('s3')
    
    options = {'username': SFTP_USER, 'password': SFTP_PASS, 'port': SFTP_PORT, 'known_hosts': None}
    
    print(f"\nConectando-se a {SFTP_HOST}...")
    
    try:
        async with asyncssh.connect(SFTP_HOST, **options) as conn:
            async with conn.start_sftp_client() as sftp:
                files = await sftp.listdir('/')
                
                valid_files = []
                for f in files:
                    if f not in ['.', '..']:
                        try:
                            attrs = await sftp.stat('/' + f)
                            if stat.S_ISREG(attrs.permissions):
                                valid_files.append(f)
                        except Exception:
                            valid_files.append(f)
                
                print(f"{len(valid_files)} arquivos disponíveis.")

                # Qntd de arquivos baixados simultaneamente
                semaphore = asyncio.Semaphore(1)

                tasks = [download_and_upload(sftp, s3_client, semaphore, f) for f in valid_files]
                await asyncio.gather(*tasks)

    except Exception as e:
        print(f"Erro na conexão SFTP: {e}\n")
    finally:
        print("\nFim do processo.\n")

if __name__ == '__main__':
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
        
    asyncio.run(main())