UP_SQL = """
ALTER TABLE afe_labels
ADD COLUMN replaced_by_static_label TINYINT(1) DEFAULT FALSE;
"""
DOWN_SQL = """
ALTER TABLE afe_labels DROP COLUMN replaced_by_static_label;
"""
