
from collections import defaultdict, deque
from typing import List, Dict, Any

def find_join_path_to_target(
    target_table: str,
    relations: Dict[str, List[Dict[str, str]]],
    connected_tables: List[str]
) -> List[Dict[str, Dict[str, str]]]:
    """
    从已连接表出发，通过 BFS 找到到达指定目标表的最短路径。

    :param target_table: 目标表名（必须属于 unconnected_tables）
    :param relations: 关联关系字典，格式为 { "源表": [ {"table_name": "目标表", "next_key": "目标主键", "key": "源表外键"}, ... ] }
    :param connected_tables: 已连接的表名列表（起点集合）
    :param unconnected_tables: 尚未连接的表名列表（仅用于校验，可忽略）
    :return: 路径列表，格式为 [ {"表1": {"table_name": "表2", "next_key": "表2主键", "key": "表1关联键"}}, ... ]
             如果目标已连接或不可达，返回空列表 []
    """
    # 如果目标表已经在已连接列表中，无需再连接
    if target_table in connected_tables:
        return []

    # BFS 初始化
    queue = deque(connected_tables)
    visited = set(connected_tables)
    # parent 记录每个节点的父节点以及对应的边信息
    # 格式: { "子表": ( "父表", {"父表": {"table_name": "子表", "next_key": "...", "key": "..."}} ) }
    parent = {}

    # BFS 搜索
    while queue:
        current = queue.popleft()
        # 如果当前节点就是目标，回溯路径
        if current == target_table:
            path = []
            node = current
            while node in parent:
                parent_node, edge_info = parent[node]
                path.append(edge_info)
                node = parent_node
            path.reverse()   # 从起点到目标顺序
            return path

        # 扩展邻居（从当前表出发的所有关联）
        for rel in relations.get(current, []):
            neighbor = rel["table_name"]
            if neighbor not in visited:
                visited.add(neighbor)
                queue.append(neighbor)
                # 记录父节点和边信息（边信息就是标准格式）
                edge_info = {current: {"table_name": neighbor, "next_key": rel["next_key"], "key": rel["key"]}}
                parent[neighbor] = (current, edge_info)

    # 目标不可达
    return []

def topological_sort(relations: Dict[str, List[Dict[str, Any]]]) -> List[str]:
    """
    对表关系进行拓扑排序（基于入度选择源点）。

    :param relations: 表关系字典，格式为 { "源表": [ {"table_name": "目标表", ...}, ... ] }
    :return: 拓扑排序后的表名列表（若存在环则抛出异常）
    """
    # 1. 收集所有顶点（表名）
    vertices = set()
    for src, targets in relations.items():
        vertices.add(src)
        for edge in targets:
            vertices.add(edge["table_name"])

    # 2. 构建邻接表并计算入度
    adj = defaultdict(list)
    indegree = {v: 0 for v in vertices}

    for src, targets in relations.items():
        for edge in targets:
            dst = edge["table_name"]
            adj[src].append(dst)
            indegree[dst] += 1

    # 3. 初始化队列，将所有入度为 0 的顶点入队
    queue = deque([v for v in vertices if indegree[v] == 0])
    result = []

    # 4. 执行拓扑排序
    while queue:
        u = queue.popleft()
        result.append(u)
        for v in adj[u]:
            indegree[v] -= 1
            if indegree[v] == 0:
                queue.append(v)

    # 5. 检查是否有环（未访问到的顶点数 > 0）
    if len(result) != len(vertices):
        raise ValueError("图中存在环路，无法进行拓扑排序")

    return result