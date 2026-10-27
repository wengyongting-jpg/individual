from sql_builder import SQLBuilder
s = SQLBuilder()
print(s.build_sql(["SUB_MODEL_ID", "SUB_MODEL_NAME", "VERSION_ID", "VERSION_NAME", "SALES_QTY", "YM_ID"]))