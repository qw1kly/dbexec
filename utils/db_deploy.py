import pyodbc

class Deploy:

    def __init__(self, bak_path, db_name='tmpDatabase', data_dir = r"D:\SQLwork"):
        self.bak_path = bak_path
        self.db_name = db_name
        self.data_dir = data_dir
        self.current_connection = None

    def restore_db(self):

        server = r"."

        bak_path = self.bak_path
        db_name = self.db_name
        data_dir = self.data_dir

        conn = pyodbc.connect(
            r"DRIVER={SQL Server};"
            f"SERVER={server};"
            r"DATABASE=master;"
            r"Trusted_Connection=yes;",
            autocommit=True,
        )
        conn.timeout = 0
        cur = conn.cursor()

        cur.execute("RESTORE FILELISTONLY FROM DISK = ?", bak_path)
        moves = []
        for row in cur.fetchall():
            logical = row.LogicalName
            ext = "mdf" if row.Type == "D" else "ldf"
            target = f"{data_dir}\\{db_name}_{logical}.{ext}"
            moves.append(f"MOVE N'{logical}' TO N'{target}'")

        sql = f"RESTORE DATABASE [{db_name}] FROM DISK = ? WITH {', '.join(moves)}, REPLACE"
        cur.execute(sql, bak_path)
        while cur.nextset():
            pass

        self.current_connection = conn

    def drop_db(self):
        if not self.current_connection:
            raise RuntimeError('Соединение не найдено')
        cur = self.current_connection.cursor()
        cur.execute(f"ALTER DATABASE [{self.db_name}] SET SINGLE_USER WITH ROLLBACK IMMEDIATE")
        cur.execute(f"DROP DATABASE [{self.db_name}]")
        self.current_connection.close()
        self.current_connection = None

    def connect_to_restored(self):
        server = r"."
        conn = pyodbc.connect(
            r"DRIVER={SQL Server};"
            rf"SERVER={server};"
            rf"DATABASE={self.db_name};"
            r"Trusted_Connection=yes;",
            autocommit=True,
        )
        return conn