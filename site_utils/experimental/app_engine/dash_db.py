import logging

from google.appengine.dist import use_library
use_library('django', '1.2')


from google.appengine.ext import db

import filters
import settings
import utils

class BaseModel(db.Model):
  @classmethod
  def PK(cls, id_or_name):
    return db.Key.from_path(cls.__name__, id_or_name)

  @classmethod
  def get(cls, id_or_name):
    return db.get(cls.PK(id_or_name))

  @classmethod
  def create(cls, id_or_name):
    instance = cls(key=cls.PK(id_or_name))
    return instance


class Netbook(BaseModel):
  #PK
  name = property(lambda obj:obj.key().name())
  boards = db.StringListProperty()

  def add_board(self, board_name):
    if board_name not in self.boards:
      self.boards.append(board_name)
      self.boards.sort()

  def viewable(self, email):
    return filters.IsViewable(email, self.name)


class Board(BaseModel):
  #PK
  name = property(lambda obj: obj.key().name())

  netbooks = db.StringListProperty()
  builds = db.StringListProperty()

  def add_netbook(self, netbook_name):
    netbook = Netbook.get(netbook_name)
    if not netbook:
      netbook = Netbook.create(netbook_name)
    netbook.add_board(self.name)
    netbook.put()
    if netbook_name not in self.netbooks:
      self.netbooks.append(netbook_name)
      self.netbooks.sort()


  def add_build(self, build_name):
    if build_name not in self.builds:
      self.builds.append(build_name)
      self.builds.sort(utils.BuildCmp)
      self.builds = self.builds[:settings.MAX_BUILDS]

  def viewable(self, email):
    viewable = False
    for netbook_name in self.netbooks:
      viewable = viewable or filters.IsViewable(email, netbook_name)
    return viewable


class Category(BaseModel):
  #PK
  name = property(lambda obj: obj.key().name())
  is_job_name = db.BooleanProperty()
  test_names = db.StringListProperty()

  def add_test(self, test_name):
    if test_name not in self.test_names:
      self.test_names.append(test_name)
      self.test_names.sort()


class Build(db.Model):
  name = db.StringProperty()
  board = db.StringProperty()

  version = db.StringProperty()
  build_hash = db.StringProperty()
  seq = db.IntegerProperty()

  buildlog_json_url = db.StringProperty()
  buildlog_url = db.StringProperty()
  build_image_url = db.StringProperty()

  build_started_time = db.FloatProperty()
  build_finished_time = db.FloatProperty()
  test_started_time = db.FloatProperty()
  test_finished_time = db.FloatProperty()

  chrome_version = db.StringProperty()
  chrome_svn_number = db.IntegerProperty()

  @classmethod
  def PK(cls, board_name, build_name):
    name = board_name + '$' + build_name
    return db.Key.from_path(cls.__name__, name)

  @classmethod
  def get(cls, board_name, build_name):
    return db.get(cls.PK(board_name, build_name))

  @classmethod
  def create(cls, board_name, build_name):
    instance = cls(key=cls.PK(board_name, build_name))
    instance.name = build_name
    instance.board = board_name
    (instance.version, instance.build_hash, 
        instance.seq) = utils.BuildSplit(build_name)
    return instance

  def get_chrome_version(self):
    return '%s (%s)' % (self.chrome_version, self.chrome_svn_number)


class Job(BaseModel):
  id = property(lambda obj: obj.key().id())

  job_name = db.StringProperty()
  owner = db.StringProperty()
  
  job_created_time = db.FloatProperty()
  job_queued_time = db.FloatProperty()
  job_started_time = db.FloatProperty()
  job_finished_time = db.FloatProperty()

  job_status = db.BooleanProperty()
  completed = db.BooleanProperty()
  aborted = db.BooleanProperty()

  board = db.StringProperty()
  build = db.StringProperty()
  netbook = db.StringProperty()

  passed = db.IntegerProperty()
  total = db.IntegerProperty()


class Test(BaseModel):
  id = property(lambda x: x.key().id())
  job_id = db.IntegerProperty()

  test_name = db.StringProperty()
  job_name = db.StringProperty()
  owner = db.StringProperty()

  status = db.StringProperty()
  hostname = db.StringProperty()
  chrome_version = db.StringProperty()
  test_log_url = db.StringProperty()

  test_started_time = db.FloatProperty()
  test_finished_time = db.FloatProperty()

  board = db.StringProperty()
  build = db.StringProperty()
  netbook = db.StringProperty()

  reason = db.TextProperty()

  def get_test_log_url(self):
    if self.test_log_url:
      return self.test_log_url
    if self.status == 'GOOD':
      suffix = 'DEBUG'
    else:
      suffix = 'ERROR'
    return 'results/%d-%s/group0/%s/%s/debug/%s.%s' %  (self.job_id, self.owner, 
        self.hostname, self.test_name, self.test_name, suffix)


class TestHostKey(db.Model):
  test_id = db.IntegerProperty()
  test_name = db.StringProperty()
  hostkey_name = db.StringProperty()
  hostkey_value = db.StringProperty()

  @classmethod
  def PK(cls, test_id, hostkey_name):
    name = str(test_id) + '$' + hostkey_name
    return db.Key.from_path(cls.__name__, name)

  @classmethod
  def get(cls, test_id, hostkey_name):
    return db.get(key=cls.PK(test_id, hostkey_name))

  @classmethod
  def create(cls, test_id, hostkey_name):
    key = cls.PK(test_id, hostkey_name)
    instance = cls(key=key)
    instance.test_id = test_id
    instance.hostkey_name = hostkey_name
    return instance


class TestPerfKey(db.Model):
  test_id = db.IntegerProperty()
  test_name = db.StringProperty()
  perfkey_name = db.StringProperty()
  values = db.ListProperty(float)

  @classmethod
  def PK(cls, test_id, perfkey_name):
    name = str(test_id) + '$' + perfkey_name
    return db.Key.from_path(cls.__name__, name)

  @classmethod
  def get(cls, test_id, perfkey_name):
    return db.get(key=cls.PK(test_id, perfkey_name))

  @classmethod
  def create(cls, test_id, perfkey_name):
    key = cls.PK(test_id, perfkey_name)
    instance = cls(key=key)
    instance.test_id = test_id
    instance.perfkey_name = perfkey_name
    return instance

  def add_value(self, value):
    self.values.append(value)


class TestName(BaseModel):
  #PK
  name = property(lambda obj:obj.key().name())


class NetbookBoard(db.Model):
  categories = db.StringListProperty()

  @classmethod
  def PK(cls, netbook_name, board_name):
    name = netbook_name + '$' + board_name
    return db.Key.from_path(cls.__name__, name)

  @classmethod
  def get(cls, netbook_name, board_name):
    return db.get(cls.PK(netbook_name, board_name))

  @classmethod
  def create(cls, netbook_name, board_name):
    instance = cls(key=cls.PK(netbook_name, board_name))
    return instance

  def add_category(self, category_name):
    if category_name not in self.categories:
      self.categories.append(category_name)
      self.categories.sort()


# The task queue only accepy payload less or equal to 10K. And apparently our
# data is exceeding that limit. So we have to put the data into datastore in
# order to carry around. That is a lose in performance.
class JobPostTask(BaseModel):
  payload_pb = db.TextProperty()
