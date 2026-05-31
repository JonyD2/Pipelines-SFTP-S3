# SFTP

O script STFP.py tem como objetivo automatizar o processo de extração e carga (ETL). 
Conectando-se a um servidor SFTP, listando a quantidade de arquivos e os baixando, realizando o upload para um bucket no S3 e limpando o arquivo do servidor SFTP no fim do processo.

# CSV - S3 Download

O script CSV S3 Download.py tem como objetivo otimizar o tempo de atualização de dashboards no Power BI.
Conecta-se a um bucket S3, lista as views necessárias para download e as baixa no formato CSV. Isso possibilita a melhora na velocidade de aualização em dashboards pesados.
