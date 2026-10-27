# sql_builder.py
# 作用：根据用户选择的字段自动生成SQL语句
# 核心功能：
# - SQLBuilder类：SQL语句构造器
#   ├── build_sql()：主方法，生成完整SELECT语句
#   ├── _build_select_clause()：构建SELECT部分
#   ├── _build_from_clause()：构建FROM和JOIN部分


from typing import List, Dict, Tuple
import json

import sqlglot

import algorithm as alg


class SQLBuilder:
	"""自动SQL生成器"""
	
	def __init__(self):
		with open('correlation.json', 'r', encoding='utf-8') as f:
			data = json.load(f)  # 先加载整个 JSON 为字典
			self.graph = data["nextarc"]  # 再取其中的 "nextarc" 键
			
			# self.tables = data["tables"] # 如果不需要每次都拓扑排序，则使用此语句
			self.tables = alg.topological_sort(data["nextarc"])
			
			self.table_column = data["table_column"]
		self.count_int = 0  # 用于给连接表起别名
		self.Astables = {}  # 记录连接表的别名
		self.tables1 = []  # 指定表时
		self.column_table = {}
		self.table_schema = []
		self.table_column_list = {}
	
	def build_init_(self, schema):
		self.table_schema = schema
		self.count_int = 0  # 用于给连接表起别名
		self.Astables = {}  # 记录连接表的别名
		self.tables1 = []
		self.column_table = {}
		tb = []
		max_table_name = ""
		max_new_schemas = []
		for i in schema:
			for k, v in self.table_column.items():
				if i in v:
					self.column_table[i] = k
					tb.append(k)
		tb = list(set(tb))
		not_choose_schema = schema.copy()
		
		while len(not_choose_schema) != 0:
			max_cover = -1
			cover = -1
			for tb1 in tb:
				cover, new_schemas = self._count_table_schema(tb1, not_choose_schema)
				if cover > max_cover:
					max_cover = cover
					max_table_name = tb1
					max_new_schemas = new_schemas
			# print(not_choose_schema)
			# print(max_table_name)
			
			tb.remove(max_table_name)
			self.tables1.append(max_table_name)
			[not_choose_schema.remove(i) for i in max_new_schemas]
		# print("字段所在表：",self.tables1)
	
	def build_sql(self, selected_fields: List[str],
	              group_fields=None) -> str:
		"""
        根据选择的字段生成SQL

        Args:
            selected_fields: {'table_name': ['field1', 'field2']}
            conditions: {'table.field': 'value', ...} 可选的查询条件

        Returns:
            生成的SQL语句
            :param selected_fields:
            :param group_fields:
        """
		# 初始化，消除上次遗留
		if group_fields is None:
			group_fields = {}
		self.build_init_(selected_fields)
		# 构建FROM和JOIN子句
		from_clause = self._build_from_clause()
		if len(from_clause) == 0: return "错误，无法同时关联所有字段所在表"
		# 构建SELECT子句
		select_clause = self._build_select_clause(group_fields)
		
		# 组合SQL
		sql = f"SELECT {select_clause}\nFROM {from_clause}"
		
		return sql
	
	def _build_select_clause(self, group_fields: Dict[str, str] = None) -> str:
		"""构建SELECT子句"""
		select_parts = []
		k, v = group_fields.keys(), group_fields.values()
		for field in self.table_schema:
			if field not in k:
				select_parts.append(f"{self.Astables[self.column_table[field]]}.{field}")
		return ", ".join(select_parts)
	
	def _build_from_clause(self) -> str:
		"""
        构建FROM和JOIN子句
        具体算法为：指定指标字段所在表作为连接表，按广度搜索算法再按贪心算法匹配连接的表
        """
		if len(self.tables) == 1:
			return self.tables[0]
		
		# 获取表之间的连接路径
		not_choose_schema = self.table_schema.copy()  # 所有所需字段
		tablesed = []
		ASNAME = {}
		main_table = ""
		# 构建JOIN子句
		for i in self.tables:
			if i in self.tables1:
				main_table = i
				break
		tablesed.append(main_table)
		# print("主表：", main_table)
		self.tables1.remove(main_table)
		not_choose_schema = self._clear_clause(main_table, not_choose_schema)
		ASNAME[main_table] = f"T{self.count_int}"
		from_clause = f"{main_table} {ASNAME[main_table]}"
		self.count_int += 1
		# 左边为已连接表，右边为新连接表
		while len(not_choose_schema) != 0:
			# print(tablesed)
			paths = self._choose_best_join_table(tablesed, not_choose_schema)
			# print("当前路径：",paths)
			if len(paths) == 0: return ""
			for path_index in paths:
				old_table = list(path_index.keys())[0]
				new_table = path_index[old_table]["table_name"]
				tablesed.append(new_table)
				if new_table in self.tables1:
					self.tables1.remove(new_table)
				not_choose_schema = self._clear_clause(new_table, not_choose_schema)
				ASNAME[new_table] = f"T{self.count_int}"
				from_clause += (f"\nLEFT JOIN {new_table} {ASNAME[new_table]} "
				                f"ON {ASNAME[old_table]}.{path_index[old_table]["key"]} "
				                f"= {ASNAME[new_table]}.{path_index[old_table]["next_key"]}")
				if len(not_choose_schema) == 0:
					# 如果字段已全部选完，则提前结束路径
					break
				self.count_int += 1
		self.Astables = ASNAME
		return from_clause
	
	def _clear_clause(self, table_name: str, clauses: List[str]) -> List[str]:
		"""删除在此表中的字段"""
		
		clauses_list = []
		table_column = set(self._get_table_fields(table_name))
		for item in clauses:
			if item in table_column:
				self.column_table[item] = table_name
			else:
				clauses_list.append(item)
		return clauses_list
	
	def _build_where_clause(self, conditions: Dict[str, str]) -> str:
		"""构建WHERE子句"""
		where_parts = []
		for field, value in conditions.items():
			where_parts.append(f"{field} = '{value}'")
		return " AND ".join(where_parts)
	
	def _choose_best_join_table(self, joined_tables: List[str], unacquired_fields: List[str]) -> list[dict]:
		"""
        选择最佳 LEFT JOIN 表：该表能提供最多的未获取字段。
        :param joined_tables: 已连接的表名列表
        :param unjoined_tables: 尚未连接的候选表名列表
        :param unacquired_fields: 用户尚未获取的字段名列表
        :param algorithm: 搜索模式
        :return: 路径列表
        """
		paths = []
		cool_table_name = ""
		# 循环所有未拼接的表，按拓扑序列逆序选表，使用广度搜索算法
		for table in self.tables:
			if table in self.tables1:
				cool_table_name = table
				# print("已连接表", "*" * 5, joined_tables)
				# print("连接表", "*" * 5, self.tables1, cool_table_name)
		if cool_table_name != "":
			self.tables1.remove(cool_table_name)
			paths = alg.find_join_path_to_target(cool_table_name, self.graph, joined_tables)
			return paths
		else:
			return []
	
	def _count_table_schema(self, table_name, unacquired_fields: List[str]) -> Tuple[int, List[str]]:
		"""
            返回值1：该表可新增字段的数量
            返回值2：该表可新增字段名
            """
		table_fields = self.table_column.get(table_name, [])
		# 计算该表能提供的未获取字段
		new_fields = [f for f in table_fields if f in unacquired_fields]
		cover_count = len(new_fields)
		return cover_count, new_fields
	
	def build_insert_sql(self, table: str, data: Dict[str, any]) -> str:
		"""构建INSERT语句"""
		columns = ", ".join(data.keys())
		values = ", ".join([f"'{v}'" if isinstance(v, str) else str(v) for v in data.values()])
		return f"INSERT INTO {table} ({columns}) VALUES ({values})"
	
	def build_update_sql(self, table: str, data: Dict[str, any],
	                     condition: Dict[str, str]) -> str:
		"""构建UPDATE语句"""
		set_clause = ", ".join([f"{k} = '{v}'" if isinstance(v, str) else f"{k} = {v}"
		                        for k, v in data.items()])
		where_clause = " AND ".join([f"{k} = '{v}'" for k, v in condition.items()])
		return f"UPDATE {table} SET {set_clause} WHERE {where_clause}"
	
	def build_delete_sql(self, table: str, condition: Dict[str, str]) -> str:
		"""构建DELETE语句"""
		where_clause = " AND ".join([f"{k} = '{v}'" for k, v in condition.items()])
		return f"DELETE FROM {table} WHERE {where_clause}"
	
	def _get_table_fields(self, table_name: str) -> List[str]:
		"""获取表的字段"""
		
		return self.table_column[table_name]
	
	def check_sql_syntax(self, sql: str, dialect: str = "oracle") -> bool:
		"""
        检查 SQL 语法是否正确
        返回 (是否合法, 错误信息)
        """
		try:
			sqlglot.parse_one(sql, dialect=dialect)
			return True
		except sqlglot.errors.ParseError as e:
			return False
		except Exception as e:
			return False
	
	def _build_group_clause(self, group_fields):
		select_parts = []
		k, v = group_fields.keys(), group_fields.values()
		for field in self.table_schema:
			if field not in k:
				select_parts.append(f"{self.Astables[self.column_table[field]]}.{field}")
		return ", ".join(select_parts)
