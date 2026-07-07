class Reader:

    def __init__(self, connection):
        self.connection = connection.cursor()


    def _fetch_dicts(self):
        cols = [d[0] for d in self.connection.description]
        return [
            {k: (None if v == '' else v) for k, v in dict(zip(cols, row)).items()}
            for row in self.connection.fetchall()
        ]


    def sourse_info(self):

        '''Таблицы - TMEASUREMENTS, TPLANTS'''

        self.connection.execute(
            'SELECT MIN(MEASURE_TIME) AS period_from,\
                       MAX(MEASURE_TIME) AS period_to,\
                       COUNT(*)          AS data_count\
             FROM TMEASUREMENTS;'
        )

        data = self.connection.fetchone()

        self.connection.execute(
            'SELECT name \
             FROM TPLANTS'
        )

        object_name = self.connection.fetchone()

        return data, object_name

    def aggregate_info(self):

        '''Таблицы - TMACHINES, TMACHINE_MODEL_SETTINGS, TSHOPS, TPLANTS, TSHOP_REPORT_MACHINE'''

        self.connection.execute(
            "SELECT "
            "  m.MACHINE_ID, m.NAME AS machine_name, m.SERIAL_NUMBER, m.NUMBER AS machine_number, "
            "  mm.NAME AS model, mm.MANUFACTURER, "
            "  s.NAME AS shop, p.NAME AS plant, "
            "  rep.RUNHOURS AS run_hours "
            "FROM TMACHINES m "
            "LEFT JOIN TMACHINE_MODEL_SETTINGS mm ON mm.MACHINE_MODEL_SETTING_ID = m.MACHINE_MODEL_SETTING_ID "
            "LEFT JOIN TSHOPS  s ON s.SHOP_ID  = m.SHOP_ID "
            "LEFT JOIN TPLANTS p ON p.PLANT_ID = s.PLANT_ID "
            "LEFT JOIN TSHOP_REPORT_MACHINE rep ON rep.MACHINE_ID = m.MACHINE_ID"
        )
        data = self.connection.fetchall()
        return data

    def element_info(self):

        '''Таблицы - TELEMENTS, TELEMENT_MODEL_IN_MM_SETTINGS, TELEMENT_MODEL_SETTINGS'''

        self.connection.execute("""
            SELECT
                e.ELEMENT_ID              AS element_guid,
                e.MACHINE_ID              AS machine_guid,
                e.SERIAL_NUMBER           AS serial_number,
                emm.NAME                  AS element_position,
                es.NAME                   AS element_model,
                es.MANUFACTURER           AS manufacturer
            FROM TELEMENTS e
            LEFT JOIN TELEMENT_MODEL_IN_MM_SETTINGS emm
                   ON emm.ELEMENT_MODEL_IN_MM_SETTING_ID = e.ELEMENT_MODEL_IN_MM_SETTING_ID
            LEFT JOIN TELEMENT_MODEL_SETTINGS es
                   ON es.ELEMENT_MODEL_SETTING_ID = emm.ELEMENT_MODEL_SETTING_ID
        """)
        cols = [d[0] for d in self.connection.description]
        rows = self.connection.fetchall()
        return [
            {k: (None if v == '' else v) for k, v in dict(zip(cols, row)).items()}
            for row in rows
        ]

    def point_frequency(self):

        '''Частотный диапазон точки. Таблицы - TPOINT, TCHANNEL_SETTINGS,
           TCHANNEL_PARAMETER_LINKS, TWAVE_SETTINGS'''

        self.connection.execute("""
            SELECT DISTINCT
                p.POINT_ID              AS point_guid,
                ps.NAME                 AS point_name,
                w.WAVE_LOW_FREQUENCY    AS freq_min,
                w.WAVE_HIGH_FREQUENCY   AS freq_max,
                w.SAMPLES               AS samples
            FROM TPOINT p
            JOIN TPOINT_SETTINGS ps          ON ps.POINT_SETTING_ID   = p.POINT_SETTING_ID
            JOIN TCHANNEL_SETTINGS ch        ON ch.POINT_SETTING_ID   = p.POINT_SETTING_ID
            JOIN TCHANNEL_PARAMETER_LINKS cl ON cl.CHANNEL_SETTING_ID = ch.CHANNEL_SETTING_ID
            JOIN TWAVE_SETTINGS w            ON w.PARAMETER_SETTING_ID = cl.PARAMETER_SETTING_ID
        """)
        return self._fetch_dicts()

    def point_sensor_count(self):

        '''Кол-во каналов (датчиков) на точку'''

        self.connection.execute("""
            SELECT
                p.POINT_ID AS point_guid,
                COUNT(DISTINCT ch.CHANNEL_SETTING_ID) AS sensor_count
            FROM TPOINT p
            JOIN TCHANNEL_SETTINGS ch ON ch.POINT_SETTING_ID = p.POINT_SETTING_ID
            GROUP BY p.POINT_ID
        """)
        return self._fetch_dicts()



