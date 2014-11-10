UP_SQL = """
ALTER TABLE tko_iteration_perf_value
MODIFY higher_is_better BOOLEAN DEFAULT NULL;
"""

DOWN_SQL = """
ALTER TABLE tko_iteration_perf_value
MODIFY higher_is_better BOOLEAN NOT NULL DEFAULT TRUE;
"""
