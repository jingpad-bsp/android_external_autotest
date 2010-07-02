Power load test now uses a pre-packed extension (extension.crx).
Therefore, changes to the unpacked extension either on client or on server
will not be used.

In order to update extension.crx, use chrome's built in packer. You must close
all chrome windows before running this command.

/opt/google/chrome/chrome --pack-extension=./extension 
--pack-extension-key=./extension.pem --no-message-box

Alternatively, extension developer mode will provide a 
GUI way of doing the same task.

