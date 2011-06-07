def make_ssh_command(user='root', port=22, opts='', hosts_file=None,
                     connect_timeout=None, alive_interval=None):
    """Override default make_ssh_command to use options tuned for Chrome OS.

    Tuning changes:
      - ConnectTimeout=10; maximum of 10 seconds allowed for an SSH connection
      failure.

      - ServerAliveInterval=60; which causes SSH to ping connection every
      60 seconds. In conjunction with ServerAliveCountMax ensures that if the
      connection dies, Autotest will bail out quickly.

      - ServerAliveCountMax=1; only allow a single keep alive failure.

      - UserKnownHostsFile=/dev/null; we don't care about the keys. Host keys
      change with every new installation, don't waste memory/space saving them.
    """
    base_command = ('/usr/bin/ssh -a -x %s -o StrictHostKeyChecking=no'
                    ' -o UserKnownHostsFile=/dev/null -o BatchMode=yes'
                    ' -o ConnectTimeout=10 -o ServerAliveInterval=60'
                    ' -o ServerAliveCountMax=1 -l %s -p %d')
    return base_command % (opts, user, port)
