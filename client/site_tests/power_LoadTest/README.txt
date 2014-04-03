Power load test now uses a pre-packed extension (extension.crx).
Therefore, changes to the unpacked extension either on client or on server
will not be used.

In order to update extension.crx, use chrome's built in packer. You must close
all chrome windows before running this command.

/opt/google/chrome/chrome --pack-extension=./extension \
  --pack-extension-key=./extension.pem --no-message-box


Alternatively, extension developer mode will provide a 
GUI way of doing the same task.

The extension will not automatically begin the test if run manually. Instead,
it will attempt to load localhost:8001/testparams.html, which will not exist
if the test isn't run with autotest.

If running manually, click on the power_LoadTest extension icon to begin the
test with default settings (3600 second test).
