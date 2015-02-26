UP_SQL = """
SET @group_id = (SELECT id FROM auth_group WHERE name = 'Basic Admin');
INSERT IGNORE INTO auth_group_permissions (group_id, permission_id)
SELECT @group_id, id FROM auth_permission WHERE codename IN (
 'add_hostattribute', 'change_hostattribute', 'delete_hostattribute');
"""

DOWN_SQL="""
"""
