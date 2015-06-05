ADD_FOREIGN_KEY_CASADE= """
ALTER TABLE tko_tests
ADD CONSTRAINT invalidates_test_idx_fk FOREIGN KEY
(`invalidates_test_idx`) REFERENCES `tko_tests`(`test_idx`)
ON DELETE CASCADE;
"""

ADD_FOREIGN_KEY_NO_ACTION = """
ALTER TABLE tko_tests
ADD CONSTRAINT invalidates_test_idx_fk FOREIGN KEY
(`invalidates_test_idx`) REFERENCES `tko_tests`(`test_idx`)
ON DELETE NO ACTION;
"""

DROP_FOREIGN_KEY = """
ALTER TABLE tko_tests DROP FOREIGN KEY `invalidates_test_idx_fk`;
"""


def migrate_up(manager):
    """Pick up the changes.

    @param manager: A MigrationManager object.

    """
    manager.execute(DROP_FOREIGN_KEY)
    manager.execute(ADD_FOREIGN_KEY_CASADE)


def migrate_down(manager):
    """Drop the changes.

    @param manager: A MigrationManager object.

    """
    manager.execute(DROP_FOREIGN_KEY)
    manager.execute(ADD_FOREIGN_KEY_NO_ACTION)
