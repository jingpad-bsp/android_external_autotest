import logging
import settings

def GetDefaultNetbookName(email):
  # google users can see everything.
  if email.endswith('@google.com'):
    return settings.DEFAULT_NETBOOK

  # for partners...

  # everyone else will only see CR-48
  return settings.DEFAULT_PUBLIC_NETBOOK

def IsViewable(email, netbook_name):
  # google users can see everything.
  if email.endswith('@google.com'):
    return True

  # for partners...

  # everyone else will only see CR-48
  # convert unicode into str
  logging.info(len(settings.DEFAULT_PUBLIC_NETBOOK))
  logging.info(len(netbook_name))
  logging.info(dir(netbook_name))
  logging.info(dir(settings.DEFAULT_PUBLIC_NETBOOK))
  return str(settings.DEFAULT_PUBLIC_NETBOOK) == str(netbook_name)
