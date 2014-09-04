#pylint: disable-msg=C0111
import common
import logging, os
from autotest_lib.client.common_lib import logging_config

class ShardLoggingConfig(logging_config.LoggingConfig):
    """Logging configuration for the shard client."""

    def configure_logging(self, verbose=False):
        super(ShardLoggingConfig, self).configure_logging(
                                                  use_console=self.use_console,
                                                  verbose=verbose)
