import random
import copy


class GAService:
    """
    Algoritmo genético con representación mixta (perm, mask):
      - perm: permutación gigante de nodos cliente (sin separadores de viaje)
      - mask: vector binario que decide si cada nodo se visita (1) o no (0)

    Decodificación:
      1) Filtrar perm por mask=1
      2) Aplicar Split (camino mínimo en DAG) para dividir en viajes factibles por capacidad
      3) Aplicar mejora local 2-opt intra-ruta (primera mejora)
      4) Volver a aplicar Split
    """

    def __init__(
        self,
        distance_matrix,
        demands,
        capacity,
        population_size=120,
        generations=200,
        crossover_rate=0.9,
        mutation_rate=0.3,
        elite_size=2,
        bit_flip_rate=0.05,
        tournament_size=5,
        no_improve_limit=40,
        lambda_penalty=8.0,
        mandatory_threshold=0.60,
    ):
        self.distance_matrix = distance_matrix
        self.demands = list(demands)
        self.capacity = float(capacity)

        self.population_size = int(population_size)
        self.generations = int(generations)
        self.crossover_rate = float(crossover_rate)
        self.mutation_rate = float(mutation_rate)
        self.elite_size = int(elite_size)
        self.bit_flip_rate = float(bit_flip_rate)
        self.tournament_size = int(tournament_size)
        self.no_improve_limit = int(no_improve_limit)
        self.lambda_penalty = float(lambda_penalty)

        # Índices internos de clientes: 1..n_customers (0 es depósito)
        self.n_customers = len(distance_matrix) - 1
        self.customer_ids = list(range(1, self.n_customers + 1))

        # Conjunto obligatorio M: v_i >= 0.60 m³
        self.mandatory_ids = {
            i for i in self.customer_ids
            if self.demands[i] >= mandatory_threshold
        }

    # ==========================================================
    # Inicialización e integridad
    # ==========================================================
    def _random_individual(self):
        perm = self.customer_ids[:]
        random.shuffle(perm)

        mask = [0] * self.n_customers
        for idx, node_id in enumerate(self.customer_ids):
            if node_id in self.mandatory_ids:
                mask[idx] = 1
            else:
                mask[idx] = 1 if random.random() < 0.5 else 0

        # Garantizar al menos un nodo visitado
        if sum(mask) == 0 and self.n_customers > 0:
            force_id = random.choice(self.customer_ids)
            mask[force_id - 1] = 1

        return {"perm": perm, "mask": mask}

    def initialize_population(self):
        return [self._random_individual() for _ in range(self.population_size)]

    def _enforce_mask_rules(self, mask):
        fixed = list(mask)
        for node_id in self.mandatory_ids:
            fixed[node_id - 1] = 1
        if sum(fixed) == 0 and self.n_customers > 0:
            fixed[random.randint(0, self.n_customers - 1)] = 1
        return fixed

    # ==========================================================
    # Split (DAG shortest path): giant tour -> viajes factibles
    # ==========================================================
    def _split(self, selected_perm):
        """
        Devuelve (trips, total_distance).
        trips: lista de viajes, cada viaje como [0, ..., 0]
        """
        m = len(selected_perm)
        if m == 0:
            return [], 0.0

        # dp[j] = coste mínimo para cubrir selected_perm[0:j]
        inf = float("inf")
        dp = [inf] * (m + 1)
        prev = [-1] * (m + 1)
        dp[0] = 0.0

        for i in range(m):
            if dp[i] >= inf:
                continue

            load = 0.0
            route_cost = 0.0
            last = 0  # depósito

            # Probar arco DAG i->j (j>i), donde bloque [i, j) es un viaje
            for j in range(i + 1, m + 1):
                node = selected_perm[j - 1]
                demand = self.demands[node]
                load += demand
                if load > self.capacity + 1e-9:
                    break

                route_cost += self.distance_matrix[last][node]
                last = node
                trip_cost = route_cost + self.distance_matrix[last][0]

                cand = dp[i] + trip_cost
                if cand < dp[j]:
                    dp[j] = cand
                    prev[j] = i

        # Si no hay factible (caso extremo), cada nodo en viaje individual
        if prev[m] == -1:
            trips = []
            total = 0.0
            for node in selected_perm:
                trip = [0, node, 0]
                trips.append(trip)
                total += self.distance_matrix[0][node] + self.distance_matrix[node][0]
            return trips, total

        # Reconstrucción de segmentos
        segments = []
        cur = m
        while cur > 0:
            i = prev[cur]
            segments.append((i, cur))
            cur = i
        segments.reverse()

        trips = []
        total = 0.0
        for i, j in segments:
            nodes = selected_perm[i:j]
            trip = [0] + nodes + [0]
            trips.append(trip)

            d = 0.0
            for a in range(len(trip) - 1):
                d += self.distance_matrix[trip[a]][trip[a + 1]]
            total += d

        return trips, total

    # ==========================================================
    # Búsqueda local: 2-opt intra-ruta (primera mejora)
    # ==========================================================
    def _route_distance(self, route):
        d = 0.0
        for i in range(len(route) - 1):
            d += self.distance_matrix[route[i]][route[i + 1]]
        return d

    def _two_opt_first_improvement(self, trip):
        """trip formato [0, ..., 0]. Solo optimiza parte interna."""
        if len(trip) <= 4:
            return trip

        best = trip[:]
        improved = True
        while improved:
            improved = False
            n = len(best)
            for i in range(1, n - 2):
                for j in range(i + 1, n - 1):
                    if j - i == 1:
                        continue
                    cand = best[:i] + best[i:j][::-1] + best[j:]
                    if self._route_distance(cand) + 1e-9 < self._route_distance(best):
                        best = cand
                        improved = True
                        break
                if improved:
                    break
        return best

    def _apply_local_search(self, trips):
        improved = [self._two_opt_first_improvement(t) for t in trips]
        # Reconstruir giant tour (sin depósitos) y volver a Split
        merged = []
        for t in improved:
            merged.extend(t[1:-1])
        return self._split(merged)

    # ==========================================================
    # Evaluación
    # ==========================================================
    def evaluate(self, individual):
        perm = individual["perm"]
        mask = self._enforce_mask_rules(individual["mask"])

        # Subconjunto visitado según mask (ordenado por perm)
        selected = [node for node in perm if mask[node - 1] == 1]

        # Split + LS + Split
        trips, dist0 = self._split(selected)
        trips, dist = self._apply_local_search(trips)

        # Penalización por nodos no visitados
        unserved_volume = 0.0
        for node_id in self.customer_ids:
            if mask[node_id - 1] == 0:
                unserved_volume += self.demands[node_id]

        objective = dist + self.lambda_penalty * unserved_volume

        return {
            "objective": objective,
            "distance": dist,
            "trip_count": len(trips),
            "unserved_volume": round(unserved_volume, 4),
            "trips": trips,
            "selected": selected,
            "mask": mask,
        }

    # ==========================================================
    # Selección, cruce, mutación
    # ==========================================================
    def _tournament_select(self, population, eval_cache):
        cand = random.sample(population, min(self.tournament_size, len(population)))
        cand.sort(key=lambda ind: eval_cache[id(ind)]["objective"])
        return copy.deepcopy(cand[0])

    def _ox_crossover_perm(self, p1, p2):
        n = len(p1)
        if n <= 2:
            return p1[:]

        a = random.randint(0, n - 2)
        b = random.randint(a + 1, n - 1)

        child = [None] * n
        child[a:b] = p1[a:b]

        fill_vals = [x for x in p2 if x not in child[a:b]]
        k = 0
        for i in range(n):
            if child[i] is None:
                child[i] = fill_vals[k]
                k += 1
        return child

    def _crossover(self, ind1, ind2):
        if random.random() > self.crossover_rate:
            return copy.deepcopy(ind1)

        child_perm = self._ox_crossover_perm(ind1["perm"], ind2["perm"])

        # mask por herencia uniforme
        child_mask = []
        for g1, g2 in zip(ind1["mask"], ind2["mask"]):
            child_mask.append(g1 if random.random() < 0.5 else g2)
        child_mask = self._enforce_mask_rules(child_mask)

        return {"perm": child_perm, "mask": child_mask}

    def _mutate_perm(self, perm):
        n = len(perm)
        if n < 2:
            return perm

        op = random.random()

        # 1) intercambio
        if op < 1 / 3:
            i, j = random.sample(range(n), 2)
            perm[i], perm[j] = perm[j], perm[i]

        # 2) inserción
        elif op < 2 / 3:
            i, j = random.sample(range(n), 2)
            gene = perm.pop(i)
            perm.insert(j, gene)

        # 3) inversión
        else:
            i = random.randint(0, n - 2)
            j = random.randint(i + 1, n - 1)
            perm[i:j + 1] = reversed(perm[i:j + 1])

        return perm

    def _mutate(self, individual):
        if random.random() > self.mutation_rate:
            return individual

        child = copy.deepcopy(individual)

        # mutación sobre perm
        child["perm"] = self._mutate_perm(child["perm"])

        # bit-flip sobre mask (excepto obligatorios)
        for node_id in self.customer_ids:
            idx = node_id - 1
            if node_id in self.mandatory_ids:
                continue
            if random.random() < self.bit_flip_rate:
                child["mask"][idx] = 1 - child["mask"][idx]

        child["mask"] = self._enforce_mask_rules(child["mask"])
        return child

    # ==========================================================
    # Conversión de viajes -> ruta con separadores 0 (compatibilidad API actual)
    # ==========================================================
    @staticmethod
    def _trips_to_route(trips):
        if not trips:
            return [0, 0]

        chromosome = []
        for t_idx, trip in enumerate(trips):
            chromosome.extend(trip[1:-1])
            if t_idx < len(trips) - 1:
                chromosome.append(0)

        route = [0] + chromosome
        if route[-1] != 0:
            route.append(0)
        return route

    # ==========================================================
    # Bucle principal
    # ==========================================================
    def solve(self):
        if self.n_customers <= 0:
            return {
                "route": [0, 0],
                "distance": 0.0,
                "trip_count": 0,
                "history": [],
                "unserved_volume": 0.0,
                "selected_count": 0,
            }

        population = self.initialize_population()

        best = None
        best_eval = None
        history = []
        stall = 0

        for _ in range(self.generations):
            eval_cache = {id(ind): self.evaluate(ind) for ind in population}
            population.sort(key=lambda ind: eval_cache[id(ind)]["objective"])

            curr = population[0]
            curr_eval = eval_cache[id(curr)]
            history.append(round(curr_eval["distance"], 4))

            if best_eval is None or curr_eval["objective"] + 1e-9 < best_eval["objective"]:
                best = copy.deepcopy(curr)
                best_eval = curr_eval
                stall = 0
            else:
                stall += 1

            if stall >= self.no_improve_limit:
                break

            new_population = [copy.deepcopy(population[i]) for i in range(min(self.elite_size, len(population)))]

            while len(new_population) < self.population_size:
                p1 = self._tournament_select(population, eval_cache)
                p2 = self._tournament_select(population, eval_cache)
                child = self._crossover(p1, p2)
                child = self._mutate(child)
                new_population.append(child)

            population = new_population

        # Reevaluar best por seguridad
        best_eval = self.evaluate(best)
        route = self._trips_to_route(best_eval["trips"])

        return {
            "route": route,
            "distance": round(best_eval["distance"], 2),
            "trip_count": best_eval["trip_count"],
            "history": history,
            "unserved_volume": best_eval["unserved_volume"],
            "selected_count": len(best_eval["selected"]),
            "objective": round(best_eval["objective"], 4),
        }
