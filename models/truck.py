class Truck:

    def __init__(self):

        # 车辆容量
        self.capacity = 5.0

        # 当前已收集
        self.load = 0.0

    def reset(self):

        self.load = 0.0

    def can_collect(self,node):

        return (

            self.load

            +

            node.current_volume

            <=

            self.capacity

        )

    def collect(self,node):

        self.load += node.current_volume