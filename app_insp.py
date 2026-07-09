import os
import sys
import threading
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

# Импортируем ваши готовые модули
from utils.db_deploy import Deploy
from utils.zipfounder import extract_bak
from worker.writer import Writer


class TextRedirector:
    """Класс для перехвата print() и вывода их в текстовое поле GUI"""

    def __init__(self, widget, tag="stdout"):
        self.widget = widget
        self.tag = tag

    def write(self, str):
        self.widget.configure(state='normal')
        self.widget.insert(tk.END, str, (self.tag,))
        self.widget.see(tk.END)
        self.widget.configure(state='disabled')

    def flush(self):
        pass


class ETLApplication(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Data Engine: ВиброДизайнер-Эксперт")
        self.geometry("850x650")
        self.configure(padx=20, pady=20)

        # Настройка стиля
        style = ttk.Style(self)
        style.theme_use('clam')

        self.create_widgets()

        # Перенаправляем системный вывод (print) в наше окно логов
        sys.stdout = TextRedirector(self.log_text)
        sys.stderr = TextRedirector(self.log_text, "stderr")

    def create_widgets(self):
        # --- Блок настроек ---
        settings_frame = ttk.LabelFrame(self, text=" Настройки подключения и путей ", padding=(15, 15))
        settings_frame.pack(fill=tk.X, pady=(0, 20))

        # 1. Сервер
        ttk.Label(settings_frame, text="SQL Server:").grid(row=0, column=0, sticky=tk.W, pady=5)
        self.server_entry = ttk.Entry(settings_frame, width=30)
        self.server_entry.insert(0, r".\VDE_SQL_SERVER")
        self.server_entry.grid(row=0, column=1, pady=5, padx=10, sticky=tk.W)

        # 2. Имя целевой базы
        ttk.Label(settings_frame, text="Целевая БД (Target):").grid(row=0, column=2, sticky=tk.W, pady=5)
        self.target_db_entry = ttk.Entry(settings_frame, width=25)
        self.target_db_entry.insert(0, "Target_base")
        self.target_db_entry.grid(row=0, column=3, pady=5, padx=10, sticky=tk.W)

        # 3. Папка с архивами (ZIP)
        ttk.Label(settings_frame, text="Папка с .zip архивами:").grid(row=1, column=0, sticky=tk.W, pady=5)
        self.zip_dir_var = tk.StringVar(value=os.path.abspath('bak_files'))
        ttk.Entry(settings_frame, textvariable=self.zip_dir_var, width=50).grid(row=1, column=1, columnspan=2, pady=5,
                                                                                padx=10)
        ttk.Button(settings_frame, text="Обзор...", command=self.browse_zip_dir).grid(row=1, column=3, pady=5,
                                                                                      sticky=tk.W)

        # 4. Папка для волн (waves)
        ttk.Label(settings_frame, text="Папка для спектров:").grid(row=2, column=0, sticky=tk.W, pady=5)
        self.waves_dir_var = tk.StringVar(value=r"C:\SQLwork\waves")
        ttk.Entry(settings_frame, textvariable=self.waves_dir_var, width=50).grid(row=2, column=1, columnspan=2, pady=5,
                                                                                  padx=10)
        ttk.Button(settings_frame, text="Обзор...", command=self.browse_waves_dir).grid(row=2, column=3, pady=5,
                                                                                        sticky=tk.W)

        # --- Кнопка запуска ---
        self.start_btn = tk.Button(
            self, text="ЗАПУСТИТЬ ИНТЕГРАЦИЮ ДАННЫХ",
            bg="#2e7d32", fg="white", font=("Arial", 12, "bold"),
            height=2, command=self.start_etl_thread
        )
        self.start_btn.pack(fill=tk.X, pady=(0, 20))

        # --- Окно логов ---
        log_frame = ttk.LabelFrame(self, text=" Консоль выполнения (Логи) ", padding=(10, 10))
        log_frame.pack(fill=tk.BOTH, expand=True)

        self.log_text = tk.Text(log_frame, wrap=tk.WORD, bg="#1e1e1e", fg="#00ff00", font=("Consolas", 10))
        self.log_text.tag_config("stderr", foreground="red")
        self.log_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        scrollbar = ttk.Scrollbar(log_frame, command=self.log_text.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.log_text.config(yscrollcommand=scrollbar.set)
        self.log_text.configure(state='disabled')

    def browse_zip_dir(self):
        dir_path = filedialog.askdirectory(title="Выберите папку с архивами .zip")
        if dir_path:
            self.zip_dir_var.set(dir_path)

    def browse_waves_dir(self):
        dir_path = filedialog.askdirectory(title="Выберите папку для извлечения спектров (.afdata)")
        if dir_path:
            self.waves_dir_var.set(dir_path)

    def start_etl_thread(self):
        """Запускаем ETL в отдельном потоке, чтобы GUI не зависал"""
        self.start_btn.config(state=tk.DISABLED, bg="gray")
        self.log_text.configure(state='normal')
        self.log_text.delete(1.0, tk.END)  # Очистка логов перед новым запуском
        self.log_text.configure(state='disabled')

        thread = threading.Thread(target=self.run_etl_process)
        thread.daemon = True
        thread.start()

    def run_etl_process(self):
        """Основная логика конвейера (перенос из старого main.py)"""
        zip_dir = self.zip_dir_var.get()
        target_db = self.target_db_entry.get()
        work_dir = os.path.dirname(self.waves_dir_var.get())  # Корень рабочей папки

        print(f"Инициализация конвейера...\nДиректория архивов: {zip_dir}\n")

        try:
            # Получаем все zip файлы в указанной директории
            dbs = [f for f in os.listdir(zip_dir) if f.lower().endswith('.zip')]

            if not dbs:
                print("[!] В указанной папке не найдено .zip архивов.")
                self.reset_ui()
                return

            for zip_name in dbs:
                zip_path = os.path.join(zip_dir, zip_name)
                print(f"{'=' * 50}\nОбработка архива: {zip_name}\n{'=' * 50}")

                # 1. Распаковка .bak
                print("Извлечение базы данных из архива...")
                bak_path = extract_bak(zip_path, work_dir)

                # 2. Развертывание временной базы
                print("Развертывание на SQL Server...")
                current_db = Deploy(bak_path)
                current_db.restore_db()
                data_conn = current_db.connect_to_restored()

                # 3. Запуск ETL конвейера
                writer = Writer(data_conn, source_db_name=current_db.db_name, target_db_name=target_db)
                # Передаем путь к папке waves напрямую в writer
                writer.waves_dir = self.waves_dir_var.get()
                writer.run_full_etl(zip_path)

                # 4. Очистка мусора
                print("Удаление временной базы и файлов...")
                data_conn.close()
                current_db.drop_db()
                if os.path.exists(bak_path):
                    os.remove(bak_path)
                print(f"[+] Обработка {zip_name} полностью завершена.\n")

            print("\nВСЕ АРХИВЫ УСПЕШНО ОБРАБОТАНЫ! 🎉")
            messagebox.showinfo("Успех", "Интеграция всех баз данных завершена!")

        except Exception as e:
            print(f"\n[КРИТИЧЕСКАЯ ОШИБКА]: {e}")
            messagebox.showerror("Ошибка", f"Произошла ошибка в процессе ETL:\n{e}")

        finally:
            self.reset_ui()

    def reset_ui(self):
        """Возвращаем кнопку в активное состояние"""
        self.start_btn.config(state=tk.NORMAL, bg="#2e7d32")


if __name__ == "__main__":
    app = ETLApplication()
    app.mainloop()