import random
import copy


# ==========================================================
# 多趟 VRP 的染色体表示：
#   基因 = 非仓库节点的索引（1..N-1），加上若干个 0 作为"回仓库"分隔点
#   例如 [3, 1, 0, 5, 2, 0, 4] 拆为:
#     trip1: 0 -> 3 -> 1 -> 0
#     trip2: 0 -> 5 -> 2 -> 0
#     trip3: 0 -> 4 -> 0
#   适应度 = 总行程距离 + 容量违反惩罚 + 趟数惩罚
# ==========================================================


class GAService:
    def __init__(
        self,
        distance_matrix,
        demands,
        capacity,
        population_size=120,
        generations=400,
        crossover_rate=0.85,
        mutation_rate=0.15,
        elite_size=8,
        num_trips_hint=None,
        trip_penalty_weight=2.0,
    ):
        self.distance_matrix = distance_matrix
        # 每个节点的"需求" (m³)
        self.demands = list(demands)
        # 车辆容量 (m³)
        self.capacity = capacity
        self.population_size = population_size
        self.generations = generations
        self.crossover_rate = crossover_rate
        self.mutation_rate = mutation_rate
        self.elite_size = elite_size

        # 非仓库节点的个数
        self.n_customers = len(distance_matrix) - 1

        # 期望的最小趟数 = ceil(总需求 / 容量) —— 用来惩罚"多跑空趟"
        total_demand = sum(self.demands[1:])
        self.min_trips = max(1, -(-int(round(total_demand * 100)) // int(round(capacity * 100))))
        self.num_trips_hint = num_trips_hint or self.min_trips

        # 单趟平均距离上限（粗略估计，用来给罚分一个合理尺度）
        n = len(distance_matrix)
        avg_leg = (
            sum(distance_matrix[i][j] for i in range(n) for j in range(n) if i != j)
            / max(1, n * (n - 1))
        )
        # 容量超出 1.0 等价罚 ~= 5 趟平均距离，趟数超出 1 等价罚 ~= 2 趟平均距离
        self.capacity_penalty_per_unit = 5.0 * max(avg_leg, 1.0) * max(self.num_trips_hint, 1)
        self.trip_penalty_weight = trip_penalty_weight * max(avg_leg, 1.0) * max(self.num_trips_hint, 1)

    # ==========================================================
    # 染色体工具
    # ==========================================================
    def _split_trips(self, chromosome):
        """把含 0 的染色体拆为多趟 (每趟两端不含 0)"""
        trips = []
        current = []
        for gene in chromosome:
            if gene == 0:
                if current:
                    trips.append(current)
                    current = []
            else:
                current.append(gene)
        if current:
            trips.append(current)
        return trips

    def _valid_genes(self):
        return list(range(1, self.n_customers + 1))

    def _count_genes(self, chromosome):
        return sum(1 for g in chromosome if g != 0)

    # ==========================================================
    # 初始化：随机打乱非仓库节点，再随机插入 N-1 个 0
    # （N = num_trips_hint，确保初始种群大概率可行）
    # ==========================================================
    def create_chromosome(self):
        genes = self._valid_genes()
        random.shuffle(genes)
        # 在基因之间随机插入 0
        chrom = []
        for i, g in enumerate(genes):
            chrom.append(g)
            # 在每个基因后面以一定概率插入 0
            if i < len(genes) - 1 and random.random() < 0.5:
                chrom.append(0)
        # 保证至少有 (num_trips_hint - 1) 个 0 分隔点
        needed_zeros = max(0, self.num_trips_hint - 1)
        while chrom.count(0) < needed_zeros:
            # 在两个非 0 之间插入
            positions = [i for i in range(len(chrom)) if chrom[i] != 0]
            if len(positions) < 2:
                break
            i = random.choice(positions[:-1])
            chrom.insert(i + 1, 0)
        return chrom

    def initialize_population(self):
        return [self.create_chromosome() for _ in range(self.population_size)]

    # ==========================================================
    # 评估：总行程 + 容量超载惩罚 + 趟数惩罚
    # ==========================================================
    def evaluate(self, chromosome):
        total_distance = 0.0
        load = 0.0
        capacity_violation = 0.0
        trips_count = 0
        prev = 0  # 从仓库出发

        for gene in chromosome:
            if gene == 0:
                # 回仓库
                total_distance += self.distance_matrix[prev][0]
                prev = 0
                trips_count += 1
                load = 0.0
            else:
                # 如果当前车辆已经超载（容量违反），记录额外惩罚
                demand = self.demands[gene]
                if load + demand > self.capacity:
                    # 强制视为一次"隐式"返回：罚分 + 仍然走下去
                    # (这样仍能惩罚走法不合理，同时不会让适应度爆炸)
                    capacity_violation += (load + demand - self.capacity)
                    # 强制回仓库再出发
                    total_distance += self.distance_matrix[prev][0]
                    total_distance += self.distance_matrix[0][gene]
                    load = demand
                else:
                    total_distance += self.distance_matrix[prev][gene]
                    load += demand
                prev = gene

        # 最后一趟若没以 0 收尾
        if prev != 0:
            total_distance += self.distance_matrix[prev][0]
            trips_count += 1

        # 趟数惩罚：实际趟数 > 期望最小趟数
        extra_trips = max(0, trips_count - self.num_trips_hint)
        trip_penalty = extra_trips * self.trip_penalty_weight

        fitness = total_distance + capacity_violation * self.capacity_penalty_per_unit + trip_penalty
        return fitness, total_distance, capacity_violation, trips_count

    def route_distance(self, chromosome):
        return self.evaluate(chromosome)[1]

    def fitness(self, chromosome):
        return 1.0 / (self.evaluate(chromosome)[0] + 1e-6)

    # ==========================================================
    # 锦标赛选择
    # ==========================================================
    def selection(self, population):
        tournament = random.sample(population, min(5, len(population)))
        tournament.sort(key=lambda c: self.evaluate(c)[0])
        return copy.deepcopy(tournament[0])

    # ==========================================================
    # 交叉：两段式顺序交叉 (OX) + 0 分隔点保留
    #   1) 对"非零基因"做 OX 交叉
    #   2) 随机从两个父代拷贝 (期望个数 - 1) 个 0 到子代
    # ==========================================================
    def crossover(self, parent1, parent2):
        if random.random() > self.crossover_rate:
            return copy.deepcopy(parent1)

        # 1) 抽取每个父代的"非零基因"序列
        g1 = [g for g in parent1 if g != 0]
        g2 = [g for g in parent2 if g != 0]
        if len(g1) < 2:
            return copy.deepcopy(parent1)

        # OX crossover on g1, g2
        start = random.randint(0, len(g1) - 2)
        end = random.randint(start + 1, len(g1) - 1)
        child_genes = list(g1[start:end])
        rest = [g for g in g2 if g not in child_genes]
        # 拼接
        ordered = rest[-start:] + child_genes + rest[:-start] if start > 0 else rest + child_genes
        # 长度对齐 g1
        ordered = ordered[: len(g1)]

        # 2) 决定子代 0 的个数 (允许比父代多/少)
        zeros_target = random.randint(0, max(0, len(g1)))
        zeros_target = max(0, min(zeros_target, len(g1) - 1))

        # 在 ordered 的随机位置之间插入 0
        if zeros_target == 0:
            child = ordered
        else:
            positions = sorted(random.sample(range(1, len(ordered)), zeros_target))
            child = []
            prev_pos = 0
            for p in positions:
                child.extend(ordered[prev_pos:p])
                child.append(0)
                prev_pos = p
            child.extend(ordered[prev_pos:])

        # 兜底：如果误把全部基因吃掉了 (极端情况) 重新来一份
        if self._count_genes(child) != len(g1):
            return copy.deepcopy(parent1)
        return child

    # ==========================================================
    # 变异：四种
    #   a) swap two non-zero genes
    #   b) move one gene to another position
    #   c) insert a 0 (split)
    #   d) remove a 0 (merge two trips)
    # ==========================================================
    def mutate(self, chromosome):
        if random.random() > self.mutation_rate:
            return chromosome

        op = random.random()
        chrom = list(chromosome)
        non_zero_indices = [i for i, g in enumerate(chrom) if g != 0]
        zero_indices = [i for i, g in enumerate(chrom) if g == 0]

        if op < 0.35 and len(non_zero_indices) >= 2:
            # a) swap two non-zero genes
            i, j = random.sample(non_zero_indices, 2)
            chrom[i], chrom[j] = chrom[j], chrom[i]

        elif op < 0.6 and len(non_zero_indices) >= 2:
            # b) move one gene to another position
            i = random.choice(non_zero_indices)
            j = random.choice([k for k in range(len(chrom) + 1) if k != i and k != i + 1])
            gene = chrom.pop(i)
            if j > i:
                j -= 1
            chrom.insert(j, gene)

        elif op < 0.8:
            # c) insert a 0 between two non-zero genes
            if len(non_zero_indices) >= 2:
                pos = random.randint(0, len(non_zero_indices) - 1)
                insert_at = non_zero_indices[pos] + 1
                chrom.insert(insert_at, 0)

        else:
            # d) remove a 0 (but keep at least 0 0s to avoid single-trip collapse)
            if len(zero_indices) > 1:
                i = random.choice(zero_indices)
                chrom.pop(i)

        # 守门员：检查基因完整
        if self._count_genes(chrom) != self.n_customers:
            return chromosome
        return chrom

    # ==========================================================
    # 精英
    # ==========================================================
    def elitism(self, population):
        population.sort(key=lambda c: self.evaluate(c)[0])
        return [copy.deepcopy(c) for c in population[: self.elite_size]]

    # ==========================================================
    # 主循环
    # ==========================================================
    def solve(self):
        population = self.initialize_population()

        best = None
        best_fitness_tuple = None
        history = []

        for generation in range(self.generations):
            # 按 evaluate 排序
            population.sort(key=lambda c: self.evaluate(c)[0])
            current_best = population[0]
            current_eval = self.evaluate(current_best)
            history.append(current_eval[1])  # 仅记录距离 (用于适应度曲线)

            if best is None or current_eval[0] < best_fitness_tuple[0]:
                best = copy.deepcopy(current_best)
                best_fitness_tuple = current_eval

            new_population = []
            new_population.extend(self.elitism(population))

            while len(new_population) < self.population_size:
                p1 = self.selection(population)
                p2 = self.selection(population)
                child = self.crossover(p1, p2)
                child = self.mutate(child)
                new_population.append(child)

            population = new_population

        # 把"最优染色体"展开为完整路径 [0, ..., 0]
        route = [0]
        route.extend(best)
        if best[-1] != 0:
            route.append(0)

        final_eval = self.evaluate(best)
        return {
            "route": route,
            "distance": round(final_eval[1], 2),
            "capacity_violation": round(final_eval[2], 4),
            "trip_count": final_eval[3],
            "history": history,
        }
