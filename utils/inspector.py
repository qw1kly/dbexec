import pyodbc


def run_advanced_audit():
    print("=== ГЛУБОКИЙ АУДИТ TARGET_BASE ===\n")

    try:
        conn = pyodbc.connect(
            r"DRIVER={ODBC Driver 17 for SQL Server};"
            r"SERVER=.\VDE_SQL_SERVER;"  # Замените на ваше имя сервера, если оно отличается
            r"DATABASE=Target_base;"
            r"Trusted_Connection=yes;"
        )
        cursor = conn.cursor()

        # 1. ГЛОБАЛЬНАЯ СТАТИСТИКА
        print("📊 1. ОБЪЕМ ДАННЫХ (Количество строк в таблицах):")
        tables = [
            'TPLANTS', 'TSHOPS', 'TMACHINES', 'TPOINT',
            'TMEASUREMENTS', 'TPARAM_VALUES', 'TMACHINE_EVENTS', 'TMEASUREMENT_FILES_INFO'
        ]

        for table in tables:
            try:
                cursor.execute(f"SELECT COUNT(*) FROM {table}")
                count = cursor.fetchone()[0]
                print(f"  - {table:<25}: {count:>10} строк")
            except Exception:
                print(f"  - {table:<25}: [Таблица не найдена или пуста]")

            # 2. СРЕЗ РЕАЛЬНЫХ ИЗМЕРЕНИЙ
            print("\n📈 2. ПОСЛЕДНИЕ РЕАЛЬНЫЕ ИЗМЕРЕНИЯ (Срез данных):")
            sql_measurements = """
                SELECT TOP 15
                    pl.NAME AS PlantName,
                    m.NAME AS MachineName,
                    p_set.NAME AS PointName,
                    param_set.NAME AS ParameterName,
                    val.VALUE AS Value,
                    meas.MEASURE_TIME AS MeasureTime
                FROM TMEASUREMENTS meas
                JOIN TPARAM_VALUES val ON meas.MEASUREMENT_ID = val.MEASUREMENT_ID
                -- Словари для красивых названий
                LEFT JOIN TPOINT p ON meas.POINT_ID = p.POINT_ID
                LEFT JOIN TPOINT_SETTINGS p_set ON p.POINT_SETTING_ID = p_set.POINT_SETTING_ID
                LEFT JOIN TPARAMETER_SETTINGS param_set ON meas.PARAMETER_SETTING_ID = param_set.PARAMETER_SETTING_ID
                -- Тянем связи вверх к агрегату и заводу через события
                LEFT JOIN TMACHINE_EVENTS me ON meas.MACHINE_EVENT_ID = me.MACHINE_EVENT_ID
                LEFT JOIN TMACHINES m ON me.MACHINE_ID = m.MACHINE_ID
                LEFT JOIN TSHOPS s ON m.SHOP_ID = s.SHOP_ID
                LEFT JOIN TPLANTS pl ON s.PLANT_ID = pl.PLANT_ID
                ORDER BY meas.MEASURE_TIME DESC
            """
            cursor.execute(sql_measurements)
            rows = cursor.fetchall()

            # Обновленный красивый вывод с учетом новых колонок
            print(
                f"  {'Предприятие':<18} | {'Агрегат':<15} | {'Точка':<15} | {'Параметр':<30} | {'Значение':<10} | {'Дата'}")
            print("  " + "-" * 115)
            for row in rows:
                plant = str(row.PlantName or "Не указан")[:18]
                machine = str(row.MachineName or "Не указан")[:15]
                point = str(row.PointName or "Неизвестно")[:15]
                param = str(row.ParameterName or "Неизвестный параметр")[:30]
                value = round(row.Value, 4) if row.Value is not None else "NULL"
                time = row.MeasureTime.strftime("%Y-%m-%d %H:%M") if row.MeasureTime else "Нет даты"

                print(f"  {plant:<18} | {machine:<15} | {point:<15} | {param:<30} | {value:<10} | {time}")

        # 3. ПРОВЕРКА ФАЙЛОВ СПЕКТРОВ
        print("\n📂 3. ПРИВЯЗКА ФАЙЛОВ СПЕКТРОВ (.afdata):")
        sql_files = """
            SELECT TOP 5
                meas.MEASURE_TIME,
                f.FILENAME
            FROM TMEASUREMENT_FILES_INFO f
            JOIN TMEASUREMENTS meas ON f.MEASUREMENT_ID = meas.MEASUREMENT_ID
            ORDER BY meas.MEASURE_TIME DESC
        """
        cursor.execute(sql_files)
        files = cursor.fetchall()

        if files:
            for f in files:
                time = f.MEASURE_TIME.strftime("%Y-%m-%d %H:%M") if f.MEASURE_TIME else "Нет даты"
                print(f"  - Замер от {time} привязан к файлу: {f.FILENAME}")
        else:
            print("  - Ссылки на файлы не найдены.")

        print("\n===================================\n")

    except Exception as e:
        print(f"[!] Ошибка подключения или выполнения SQL: {e}")
    finally:
        if 'conn' in locals():
            conn.close()


if __name__ == "__main__":
    run_advanced_audit()