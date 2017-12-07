UP_SQL = """
CREATE TABLE afe_static_labels (
  id int(11) NOT NULL auto_increment,
  name varchar(750) default NULL,
  kernel_config varchar(255) default NULL,
  platform tinyint(1) default '0',
  invalid tinyint(1) NOT NULL,
  only_if_needed tinyint(1) NOT NULL,
  atomic_group_id int(11) default NULL,
  PRIMARY KEY (id),
  UNIQUE KEY name (name),
  KEY atomic_group_id (atomic_group_id),
  CONSTRAINT afe_static_labels_idfk_1
  FOREIGN KEY (atomic_group_id)
    REFERENCES afe_atomic_groups (id) ON DELETE NO ACTION
) ENGINE=InnoDB;

CREATE TABLE afe_static_hosts_labels (
  host_id int(11) default NULL,
  label_id int(11) default NULL,
  UNIQUE KEY hosts_labels_both_ids (label_id,host_id),
  KEY hosts_labels_host_id (host_id),
  CONSTRAINT static_hosts_labels_host_id_fk
  FOREIGN KEY (host_id)
    REFERENCES afe_hosts (id) ON DELETE NO ACTION,
  CONSTRAINT static_hosts_labels_label_id_fk
  FOREIGN KEY (label_id)
    REFERENCES afe_static_labels (id) ON DELETE NO ACTION
) ENGINE=InnoDB;
"""

DOWN_SQL = """
DROP TABLE IF EXISTS afe_static_labels;
DROP TABLE IF EXISTS afe_static_hosts_labels;
"""
