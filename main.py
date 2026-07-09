from utils.db_deploy import Deploy
from utils.zipfounder import list_of_databases, extract_bak
import zipfile, tempfile, os

from worker.db_reader import Reader
from worker.writer import Writer

dbs = list_of_databases()
ZIP_DIR = 'bak_files'
for zip_name in dbs:

    zip_path = ZIP_DIR+f"/{zip_name}"
    work_dir = r"C:\\SQLwork"
    bak_path = extract_bak(zip_path, work_dir)

    current_db = Deploy(bak_path)
    current_db.restore_db()
    data_conn = current_db.connect_to_restored()
    reader = Reader(data_conn)
    print(reader.sourse_info())

    writer = Writer(data_conn, source_db_name=current_db.db_name, target_db_name='Target_base')
    writer.run_full_etl(zip_path)

    data_conn.close()
    current_db.drop_db()
    os.remove(bak_path)