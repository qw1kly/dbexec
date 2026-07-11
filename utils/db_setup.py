import pyodbc
import os
import sys
from utils.db_deploy import Deploy
from utils.zipfounder import extract_bak
from worker.writer import Writer


def get_input_with_default(prompt, default_value):
    user_input = input(f"{prompt} [{default_value}]: ").strip()
    return user_input if user_input else default_value


def check_db_structure(connection, db_name):
    required_tables = {'TPLANTS', 'TSHOPS', 'TMACHINES', 'TPOINT', 'TMEASUREMENTS', 'TPARAM_VALUES'}
    try:
        cursor = connection.cursor()
        cursor.execute(f"SELECT TABLE_NAME FROM [{db_name}].INFORMATION_SCHEMA.TABLES WHERE TABLE_TYPE = 'BASE TABLE'")
        existing_tables = {row[0].upper() for row in cursor.fetchall()}

        missing_tables = required_tables - existing_tables
        if missing_tables:
            print(f"Ошибка: Отсутствуют таблицы: {', '.join(missing_tables)}")
            return False
        return True
    except Exception as e:
        print(f"Ошибка проверки структуры БД: {e}")
        return False


def prepare_target_database(server_name, target_db_name, dbs, zip_dir, work_dir):
    """Проверяет наличие целевой БД или создает её из первого архива"""
    print(f"Проверка наличия целевой базы '{target_db_name}' на сервере...")

    try:
        master_conn = pyodbc.connect(
            r"DRIVER={ODBC Driver 17 for SQL Server};"
            rf"SERVER={server_name};"
            r"DATABASE=master;"
            r"Trusted_Connection=yes;"
        )
        cursor = master_conn.cursor()
        cursor.execute("SELECT name FROM sys.databases WHERE name = ?", target_db_name)
        db_exists = cursor.fetchone() is not None
        master_conn.close()
    except Exception as e:
        print(f"Критическая ошибка подключения к серверу: {e}")
        sys.exit(1)

    if db_exists:
        print("Целевая база найдена. Проверка структуры...")
        target_conn = pyodbc.connect(
            r"DRIVER={ODBC Driver 17 for SQL Server};"
            rf"SERVER={server_name};"
            rf"DATABASE={target_db_name};"
            r"Trusted_Connection=yes;"
        )

        if not check_db_structure(target_conn, target_db_name):
            print("Критическая ошибка: Целевая база повреждена.")
            sys.exit(1)
        target_conn.close()
    else:
        print("Целевая база не найдена. Создание фундамента из первого архива...")
        first_archive = dbs[0]
        zip_path = os.path.join(zip_dir, first_archive)
        bak_path = extract_bak(zip_path, work_dir)

        setup_db = Deploy(bak_path, db_name=target_db_name, data_dir=work_dir)
        setup_db.restore_db()
        data_conn = setup_db.connect_to_restored()

        if not check_db_structure(data_conn, target_db_name):
            data_conn.close()
            setup_db.drop_db()
            os.remove(bak_path)
            print("Критическая ошибка: Первый архив поврежден. Запустите скрипт заново, удалив битый архив.")
            sys.exit(1)

        print("Извлечение файлов спектров из базы-фундамента...")
        temp_writer = Writer(data_conn, source_db_name=target_db_name, target_db_name=target_db_name)
        temp_writer.waves_dir = os.path.join(work_dir, "waves")
        temp_writer.extract_wave_files(zip_path)

        data_conn.close()
        os.remove(bak_path)
        print(f"База '{target_db_name}' успешно создана.\n")
        dbs.pop(0)

    return dbs

    return dbs