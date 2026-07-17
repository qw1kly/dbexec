import pyodbc
import sys


def get_input_with_default(prompt, default_value):
    user_input = input(f"{prompt} [{default_value}]: ").strip()
    return user_input if user_input else default_value


def run_data_quality_tests(server_name, db_name):
    print(f"\n{'=' * 60}")
    print(f" ЗАПУСК ПРОВЕРКИ ЦЕЛОСТНОСТИ И КАЧЕСТВА ДАННЫХ: {db_name}")
    print(f"{'=' * 60}\n")

    try:
        conn = pyodbc.connect(
            r"DRIVER={ODBC Driver 17 for SQL Server};"
            rf"SERVER={server_name};"
            rf"DATABASE={db_name};"
            r"Trusted_Connection=yes;"
        )
        cursor = conn.cursor()
    except Exception as e:
        print(f"[КРИТИЧЕСКАЯ ОШИБКА] Не удалось подключиться к базе: {e}")
        sys.exit(1)

    # Словарь тестов. Ключ 'expected' - ожидаемое значение (0 = ошибок нет)
    tests = {
        "1. Структура: Цеха без предприятий": {
            "sql": "SELECT COUNT(*) FROM TSHOPS s LEFT JOIN TPLANTS p ON s.PLANT_ID = p.PLANT_ID WHERE p.PLANT_ID IS NULL;"
        },
        "2. Структура: Агрегаты без цехов": {
            "sql": "SELECT COUNT(*) FROM TMACHINES m LEFT JOIN TSHOPS s ON m.SHOP_ID = s.SHOP_ID WHERE s.SHOP_ID IS NULL;"
        },
        "3. Структура: Узлы без агрегатов": {
            "sql": "SELECT COUNT(*) FROM TELEMENTS e LEFT JOIN TMACHINES m ON e.MACHINE_ID = m.MACHINE_ID WHERE m.MACHINE_ID IS NULL;"
        },
        "4. Структура: Тревоги без агрегатов": {
            "sql": "SELECT COUNT(*) FROM TMACHINE_EVENTS e LEFT JOIN TMACHINES m ON e.MACHINE_ID = m.MACHINE_ID WHERE m.MACHINE_ID IS NULL;"
        },
        "5. Данные: Измерения без датчика": {
            "sql": "SELECT COUNT(*) FROM TMEASUREMENTS m LEFT JOIN TPOINT p ON m.POINT_ID = p.POINT_ID WHERE p.POINT_ID IS NULL;"
        },
        "6. Данные: Значения без измерения": {
            "sql": "SELECT COUNT(*) FROM TPARAM_VALUES v LEFT JOIN TMEASUREMENTS m ON v.MEASUREMENT_ID = m.MEASUREMENT_ID WHERE m.MEASUREMENT_ID IS NULL;"
        },
        "7. Аномалия: Пустые замеры (без цифр)": {
            "sql": "SELECT COUNT(*) FROM TMEASUREMENTS m LEFT JOIN TPARAM_VALUES v ON m.MEASUREMENT_ID = v.MEASUREMENT_ID WHERE v.PARAM_VALUE_ID IS NULL;"
        },
        "8. Аномалия: Дубликаты по времени": {
            "sql": """
                SELECT COUNT(*) FROM (
                    SELECT POINT_ID, MEASURE_TIME
                    FROM TMEASUREMENTS
                    GROUP BY POINT_ID, MEASURE_TIME
                    HAVING COUNT(*) > 1
                ) AS duplicates;
            """
        }
    }

    errors_found = 0
    warnings_found = 0

    for test_name, test_data in tests.items():
        print(f"Тест: {test_name:<40}", end=" ")
        try:
            cursor.execute(test_data['sql'])
            result = cursor.fetchone()[0]

            if result == 0:
                print("[ OK ]")
            else:
                # Аномалия пустых замеров (№7) не ломает БД, это просто "мусор", поэтому помечаем как WARN
                if "Аномалия: Пустые замеры" in test_name:
                    print(f"[ WARN ] Найдено пустых записей: {result}")
                    warnings_found += 1
                else:
                    print(f"[ ФЕЙЛ ] Найдено нарушений: {result} !!!")
                    errors_found += 1

        except Exception as e:
            print(f"[ ОШИБКА SQL ] -> {e}")
            errors_found += 1

    conn.close()

    print(f"\n{'=' * 60}")
    if errors_found == 0 and warnings_found == 0:
        print(" РЕЗУЛЬТАТ: ИДЕАЛЬНО. База данных имеет 100% целостность.")
    elif errors_found == 0 and warnings_found > 0:
        print(" РЕЗУЛЬТАТ: УДОВЛЕТВОРИТЕЛЬНО. Структура цела, но есть аналитический мусор (WARN).")
    else:
        print(f" РЕЗУЛЬТАТ: ВНИМАНИЕ! Найдено критических ошибок: {errors_found}.")
    print(f"{'=' * 60}\n")


if __name__ == "__main__":
    print("НАСТРОЙКА ПАРАМЕТРОВ ДЛЯ ТЕСТИРОВАНИЯ")
    SERVER_NAME = get_input_with_default("Введите имя SQL сервера", r".\VDE_SQL_SERVER")
    TARGET_DB_NAME = get_input_with_default("Введите имя целевой базы", "Target_base")

    run_data_quality_tests(SERVER_NAME, TARGET_DB_NAME)