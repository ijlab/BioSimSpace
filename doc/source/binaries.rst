.. _ref_binaries:

========
Binaries
========

The self-extracting binary for the 2019.2.0 release of BioSimSpace
can be downloaded from one of the following links:

* Linux: `biosimspace_2019_2_0_linux.run <https://objectstorage.eu-frankfurt-1.oraclecloud.com/n/hugs/b/biosimspace_releases/o/biosimspace_2019_2_0_linux.run>`__
* Mac OS X: `biosimspace_2019_2_0_osx.run <https://objectstorage.eu-frankfurt-1.oraclecloud.com/n/hugs/b/biosimspace_releases/o/biosimspace_2019_2_0_osx.run>`__

The self-extracting binary for the 2019.1.0 release of BioSimSpace
can be downloaded from one of the following links:

* Linux: `biosimspace_2019_1_0_linux.run <https://objectstorage.eu-frankfurt-1.oraclecloud.com/n/hugs/b/biosimspace_releases/o/biosimspace_2019_1_0_linux.run>`__
* Mac OS X: `biosimspace_2019_1_0_osx.run <https://objectstorage.eu-frankfurt-1.oraclecloud.com/n/hugs/b/biosimspace_releases/o/biosimspace_2019_1_0_osx.run>`__

(These are portable X86-64 binaries that should work on any Linux distribution released
since ~2011, or any OS X >= 10.9 [Mavericks, released 2013]. Note that they are compiled
with AVX enabled, so will only work on modern (>2011) X86-64 Intel/AMD processors.)

Once downloaded, the binary can be unpacked as follows, e.g. for the Linux
development package:

.. code-block:: bash

   chmod +x biosimspace_devel_latest_linux.run
   ./biosimspace_devel_latest_linux.run

This will let you choose where to install BioSimSpace. By default, this will be
into ``$HOME/biosimspace.app``.
