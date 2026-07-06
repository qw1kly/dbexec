class Reader:

    def __init__(self, connection):
        self.connection = connection.cursor()


    def sourse_info(self):

        '''БАЗЫ ДАННЫХ - TMEASUREMENTS, TPLANTS'''

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
