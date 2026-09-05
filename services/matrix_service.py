import pandas as pd


class MatrixService:

    def __init__(self):

        self.distance_file = "data/matriz_distancias.xlsx"

        self.time_file = "data/matriz_tiempos.xlsx"

        self.distance_matrix = None

        self.time_matrix = None

    def load(self):

        self.distance_matrix = pd.read_excel(
            self.distance_file,
            index_col=0
        )

        self.time_matrix = pd.read_excel(
            self.time_file,
            index_col=0
        )

    def get_distance_matrix(self):

        return self.distance_matrix

    def get_time_matrix(self):

        return self.time_matrix

    def distance(self, from_node, to_node):

        return int(
        self.distance_matrix.iloc[from_node, to_node]
        )

    def travel_time(self, from_node, to_node):

        return int(
        self.time_matrix.iloc[from_node, to_node]
        )