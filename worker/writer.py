import os
import zipfile
import shutil
import io


class Writer:
    def __init__(self, connection, source_db_name, target_db_name):
        self.conn_obj = connection
        self.connection = connection.cursor()
        self.source_db = source_db_name
        self.target_db = target_db_name
        self.waves_dir = r"C:\SQLwork\waves"

    def _execute_sql(self, sql: str, commit: bool = True, ignore_missing: bool = False):
        """хелпер для выполнения запросов с обработкой ошибок."""
        try:
            self.connection.execute(sql)
            if commit:
                self.conn_obj.commit()
        except Exception as e:
            self.conn_obj.rollback()
            if ignore_missing and ('42S02' in str(e) or '208' in str(e)):
                pass  # Игнорируем таблицы, отсутствующие в старых версих БД
            else:
                print(f"    [!] Ошибка выполнения SQL: {e}")
                raise e

    def sync_dictionaries(self):
        """Дедупликация предприятий."""
        print("Синхронизация предприятий (TPLANTS)...")
        sql = f"""
            INSERT INTO [{self.target_db}].[dbo].[TPLANTS] 
                (PLANT_ID, NAME, CODE, COMMENT, ORDER_NUMBER, ORGANIZATION_ID)
            SELECT S.PLANT_ID, S.NAME, S.CODE, S.COMMENT, S.ORDER_NUMBER, S.ORGANIZATION_ID
            FROM [{self.source_db}].[dbo].[TPLANTS] S
            WHERE NOT EXISTS (
                SELECT 1 FROM [{self.target_db}].[dbo].[TPLANTS] T WHERE T.NAME = S.NAME
            )
        """
        self._execute_sql(sql)

    def sync_topology(self):
        """Ремаппинг цехов на обновленные предприятия."""
        print("Синхронизация цехов (TSHOPS)...")
        sql_shops = f"""
            INSERT INTO [{self.target_db}].[dbo].[TSHOPS] 
                (SHOP_ID, CODE, ORDER_NUMBER, NAME, COMMENT, PLANT_ID, DIVISION_ID)
            SELECT S.SHOP_ID, S.CODE, S.ORDER_NUMBER, S.NAME, S.COMMENT, 
                   T_PLANT.PLANT_ID, S.DIVISION_ID
            FROM [{self.source_db}].[dbo].[TSHOPS] S
            JOIN [{self.source_db}].[dbo].[TPLANTS] S_PLANT ON S.PLANT_ID = S_PLANT.PLANT_ID
            JOIN [{self.target_db}].[dbo].[TPLANTS] T_PLANT ON S_PLANT.NAME = T_PLANT.NAME
            WHERE NOT EXISTS (
                SELECT 1 FROM [{self.target_db}].[dbo].[TSHOPS] T 
                WHERE T.NAME = S.NAME AND T.PLANT_ID = T_PLANT.PLANT_ID
            )
        """
        self._execute_sql(sql_shops)

    def sync_equipment(self):
        """Перенос агрегатов (с учетом ремаппинга цехов) и датчиков."""
        print("Синхронизация агрегатов и датчиков...")
        sql_machines = f"""
            INSERT INTO [{self.target_db}].[dbo].[TMACHINES] 
                (MACHINE_ID, NAME, SHOP_ID, SERIAL_NUMBER, NUMBER, MACHINE_MODEL_SETTING_ID)
            SELECT M.MACHINE_ID, M.NAME, T_SHOP.SHOP_ID, 
                   M.SERIAL_NUMBER, M.NUMBER, M.MACHINE_MODEL_SETTING_ID
            FROM [{self.source_db}].[dbo].[TMACHINES] M
            JOIN [{self.source_db}].[dbo].[TSHOPS] S_SHOP ON M.SHOP_ID = S_SHOP.SHOP_ID
            JOIN [{self.source_db}].[dbo].[TPLANTS] S_PLANT ON S_SHOP.PLANT_ID = S_PLANT.PLANT_ID
            JOIN [{self.target_db}].[dbo].[TPLANTS] T_PLANT ON S_PLANT.NAME = T_PLANT.NAME
            JOIN [{self.target_db}].[dbo].[TSHOPS] T_SHOP ON S_SHOP.NAME = T_SHOP.NAME 
                 AND T_SHOP.PLANT_ID = T_PLANT.PLANT_ID
            WHERE NOT EXISTS (
                SELECT 1 FROM [{self.target_db}].[dbo].[TMACHINES] T 
                WHERE T.MACHINE_ID = M.MACHINE_ID
            )
        """
        self._execute_sql(sql_machines)

        sql_points = f"""
            INSERT INTO [{self.target_db}].[dbo].[TPOINT]
            SELECT * FROM [{self.source_db}].[dbo].[TPOINT]
            EXCEPT
            SELECT * FROM [{self.target_db}].[dbo].[TPOINT]
        """
        self._execute_sql(sql_points)

    def sync_settings_dictionaries(self):
        """Перенос словарей настроек с динамической проверкой Primary Key."""
        print("Синхронизация системных словарей...")
        settings_tables = [
            'TUNIT_TYPES', 'TDIRECTION_TYPES', 'TWINDOW_TYPES',
            'TPARAMETER_SETTINGS', 'TPOINT_SETTINGS', 'TCHANNEL_SETTINGS',
            'TMACHINE_MODEL_SETTINGS', 'TELEMENT_MODEL_SETTINGS',
            'TREGION_SETTINGS', 'TWAVE_SETTINGS', 'TSPECTRUM_SETTINGS',
            'TBAND_SETTINGS', 'TELEMENTS', 'TBEARING_SETTINGS'
        ]

        for table in settings_tables:
            # Генерация PK: отбрасываем первую 'T' и последнюю 'S', добавляем '_ID'
            pk_col = table[1:-1] + '_ID'
            sql = f"""
                INSERT INTO [{self.target_db}].[dbo].[{table}]
                SELECT * FROM [{self.source_db}].[dbo].[{table}] S
                WHERE NOT EXISTS (
                    SELECT 1 FROM [{self.target_db}].[dbo].[{table}] T
                    WHERE T.{pk_col} = S.{pk_col}
                )
            """
            self._execute_sql(sql, ignore_missing=True)

    def sync_measurements_safely(self):
        """Ручная транзакционная загрузка числовых данных измерений."""
        print("Перенос измерений (TMEASUREMENTS, TPARAM_VALUES)...")
        try:
            self.connection.execute("BEGIN TRAN")

            sql_meas = f"""
                INSERT INTO [{self.target_db}].[dbo].[TMEASUREMENTS]
                    (MEASUREMENT_ID, MEASURE_TIME, PARAMETER_SETTING_ID, MACHINE_EVENT_ID, POINT_ID, CHANNEL_SETTING_ID, COMMENT)
                SELECT S.MEASUREMENT_ID, S.MEASURE_TIME, S.PARAMETER_SETTING_ID, S.MACHINE_EVENT_ID, S.POINT_ID, S.CHANNEL_SETTING_ID, S.COMMENT
                FROM [{self.source_db}].[dbo].[TMEASUREMENTS] S
                WHERE NOT EXISTS (
                    SELECT 1 FROM [{self.target_db}].[dbo].[TMEASUREMENTS] T 
                    WHERE T.MEASUREMENT_ID = S.MEASUREMENT_ID
                )
            """
            self.connection.execute(sql_meas)

            sql_values = f"""
                INSERT INTO [{self.target_db}].[dbo].[TPARAM_VALUES]
                    (PARAM_VALUE_ID, VALUE, MEASUREMENT_ID)
                SELECT S.PARAM_VALUE_ID, S.VALUE, S.MEASUREMENT_ID
                FROM [{self.source_db}].[dbo].[TPARAM_VALUES] S
                WHERE NOT EXISTS (
                    SELECT 1 FROM [{self.target_db}].[dbo].[TPARAM_VALUES] T 
                    WHERE T.PARAM_VALUE_ID = S.PARAM_VALUE_ID
                )
            """
            self.connection.execute(sql_values)

            self.connection.execute("COMMIT")
        except Exception as e:
            self.connection.execute("ROLLBACK")
            print(f"    [!] Ошибка при загрузке измерений. Выполнен откат. Ошибка: {e}")
            raise e

    def sync_events_and_files(self):
        """Синхронизация связей бинарных данных и журнала тревог."""
        print("Синхронизация связей с бинарными данными...")
        tables_pks = {
            'TMACHINE_EVENTS': 'MACHINE_EVENT_ID',
            'TMEASUREMENT_FILES_INFO': 'FILE_INFO_ID',
            'TWAVE_DATA': 'WAVE_DATA_ID',
            'TSYNC_DATA': 'SYNC_DATA_ID'
        }

        for table, pk in tables_pks.items():
            sql = f"""
                INSERT INTO [{self.target_db}].[dbo].[{table}]
                SELECT * FROM [{self.source_db}].[dbo].[{table}] S
                WHERE NOT EXISTS (
                    SELECT 1 FROM [{self.target_db}].[dbo].[{table}] T
                    WHERE T.{pk} = S.{pk}
                )
            """
            self._execute_sql(sql, ignore_missing=True)


    def extract_wave_files(self, zip_path):
        """Извлечение осциллограмм (.afdata) из основного и вложенных архивов."""
        print("Копирование файлов спектров (.afdata)...")
        os.makedirs(self.waves_dir, exist_ok=True)
        count = 0

        try:
            with zipfile.ZipFile(zip_path, 'r') as main_zip:
                # 1. Поиск в корне архива
                afdata_main = [f for f in main_zip.namelist() if f.lower().endswith('.afdata')]
                for file_in_zip in afdata_main:
                    count += self._extract_single_file(main_zip, file_in_zip)

                # 2. Поиск во вложенных архивах
                nested_zips = [f for f in main_zip.namelist() if f.lower().endswith('.zip')]
                for nested_zip_name in nested_zips:
                    with main_zip.open(nested_zip_name) as nested_file:
                        nested_zip_bytes = io.BytesIO(nested_file.read())
                        with zipfile.ZipFile(nested_zip_bytes, 'r') as nested_zip:
                            afdata_nested = [f for f in nested_zip.namelist() if f.lower().endswith('.afdata')]
                            for file_in_zip in afdata_nested:
                                count += self._extract_single_file(nested_zip, file_in_zip)

            print(f"    [+] Новых спектров извлечено: {count}")
        except Exception as e:
            print(f"    [!] Ошибка при извлечении файлов: {e}")

    def _extract_single_file(self, zip_obj, file_in_zip) -> int:
        """Хелпер для дедупликации и распаковки одного файла."""
        filename = os.path.basename(file_in_zip)
        if not filename:
            return 0

        target_path = os.path.join(self.waves_dir, filename)
        if not os.path.exists(target_path):
            with zip_obj.open(file_in_zip) as source, open(target_path, "wb") as target:
                shutil.copyfileobj(source, target)
            return 1
        return 0

    def run_full_etl(self, zip_path):
        """Запуск конвейера. Порядок выполнения строгий из-за Foreign Keys."""
        archive_name = os.path.basename(zip_path)

        print(f"\n--- СТАРТ ETL-ПРОЦЕССА ({archive_name}) ---")
        self.sync_dictionaries()
        self.sync_topology()
        self.sync_equipment()
        self.sync_settings_dictionaries()
        self.sync_measurements_safely()
        self.sync_events_and_files()
        self.extract_wave_files(zip_path)
        print("--- ETL-ПРОЦЕСС УСПЕШНО ЗАВЕРШЕН ---\n")