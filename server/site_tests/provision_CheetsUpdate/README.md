# Android presubmit code locations

## Uprevs

The files here are copied from Android tree, for example
https://googleplex-android.googlesource.com/platform/tools/vendor/google_prebuilts/arc/+/master/push_to_device.py

There are several other prebuilds that needs to be maintained too.

## Testing your changes

In order to test your changes, run the test locally.  Copy push_to_device.py
from Android and obtain prebuilt and run:

```shell
$ ./push_to_device.py --use-prebuilt-file ~/cheets_arm-img-4801564.zip --simg2img /usr/bin/simg2img --mksquashfs-path ./mksquashfs IP --loglevel DEBUG
```

Or run the autotest with:

```shell
(chroot) test_that IP provision_CheetsUpdate --args='value=git_nyc-mr1-arc/cheets_arm-user/4801564 -b kevin
```

## Updating

After you submit your changes, [Chrome OS lab deputy will push it to
prod](https://sites.google.com/a/google.com/chromeos/for-team-members/infrastructure/chromeos-admin/push-to-prod).
Send a heads up.
