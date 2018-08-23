
The purpose of this autotest is to verify that given subset of PPD files work
in ChromeOS. Each PPD file is tested with the following procedure:
1. A printer driver is added to CUPS server.
2. Test documents are printed on the configured printer.
3. Raw output from the CUPS server is intercepted by, so called, FakePrinter.
4. Obtained outputs are verified (see below).
5. The printer driver is removed from CUPS server.
This procedure is repeated for every PPD file. The number of PPD files may be
large (3K+ files). To decrease amount of time needed by the autotest several
PPD files are tested simultaneously in parallel threads. Autotest always run
the procedure for all given PPD files and print a summary report at the end.
If at least one of PPD files fails, whole autotest is finished with failure
(but always all PPD files are processed).

Output verification:
Intercepted output is verified by comparision with the previous results
obtained for the same PPD. We cannot store outputs directly, because their
total size may have hundreds of megabytes. Instead of that short digest is
calculated for each obtained document and it is used for comparision.
A function for digests calculation is in the 'helpers.py' file. Not all
outputs can be tested this way because for some PPD files produced contents
differ between runs. List of PPD files for which we cannot calculate
constant digest is saved in the file digests_blacklist.txt. Files with
expected digests for every test document are stored in the directory "digests".
If a digests for given pair (test document, PPD file) is missing, the test
checks only check if the output is not empty (or not too short).

Parameters:
path_docs - path to directory with test documents (PDF files)
path_ppds - path to directory with PPD files, if not set then all available PPD
            files are downloaded and tested
path_digests - path to directory with files containing digests for
            verification, if not set then outputs are not verified
path_outputs - if set, then all outputs are dumped there (given directory is
            deleted if already exists); also all digests files are recalculated
            and saved in the same directory

Generating new digests:
The following procedure can be used to update digests:
1. Run the test defined in control.all_outputs:
        test_that <device IP>  PrinterPpds_outputs
2. Download generated files with digests to your workstation
        rsync root@<device IP>:/tmp/PrinterPpds_outputs/*.digests <local dir>
3. Replace the files from the "digests" directory and commit changes

Updating the archive with PPD files:
Currently, all tests are based on PPD files stored in local directories. The
autotest can download all PPD files by itself, but we do not use this option
to limit number of possible points of failures. PPD files are stored in the
archive 'ppds_all.tar.xz'. To replace the archive with the current list of
supported PPD files one can use the script 'download_ppds_make_archive.py'.

