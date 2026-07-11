import os
import sys
from utils.db_deploy import Deploy
from utils.zipfounder import list_of_databases, extract_bak
from worker.writer import Writer
from utils.db_setup import get_input_with_default, check_db_structure, prepare_target_database

print("НАСТРОЙКА ПАРАМЕТРОВ")
SERVER_NAME = get_input_with_default("Введите имя SQL сервера или 'Enter'", r".\VDE_SQL_SERVER")
TARGET_DB_NAME = get_input_with_default("Введите имя целевой базы или 'Enter'", "Target_base")
WORK_DIR = get_input_with_default("Введите рабочую папку для БД и спектров или 'Enter'", r"C:\SQLwork")
print("-" * 30 + "\n")

os.makedirs(WORK_DIR, exist_ok=True)

dbs = list_of_databases()
ZIP_DIR = 'bak_files'

if not dbs:
    print("В папке архивов нет файлов для обработки.")
    sys.exit(0)

dbs = prepare_target_database(SERVER_NAME, TARGET_DB_NAME, dbs, ZIP_DIR, WORK_DIR)

if not dbs:
    print("Все доступные архивы интегрированы.")
    sys.exit(0)

for zip_name in dbs:
    print(f"Обработка архива: {zip_name}")
    zip_path = os.path.join(ZIP_DIR, zip_name)

    bak_path = extract_bak(zip_path, WORK_DIR)

    current_db = Deploy(bak_path, data_dir=WORK_DIR)
    current_db.restore_db()
    data_conn = current_db.connect_to_restored()

    if not check_db_structure(data_conn, current_db.db_name):
        print(f"Пропуск: База в архиве '{zip_name}' не имеет нужных таблиц.")
        data_conn.close()
        current_db.drop_db()
        os.remove(bak_path)
        print("-" * 30)
        continue

    writer = Writer(data_conn, source_db_name=current_db.db_name, target_db_name=TARGET_DB_NAME)
    # Перенаправляем сохранение спектров в пользовательскую папку
    writer.waves_dir = os.path.join(WORK_DIR, "waves")
    writer.run_full_etl(zip_path)

    data_conn.close()
    current_db.drop_db()
    os.remove(bak_path)
    print("-" * 30)

print("\nИНТЕГРАЦИЯ ВСЕХ БАЗ ЗАВЕРШЕНА.")