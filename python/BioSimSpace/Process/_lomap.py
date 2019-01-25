######################################################################
# BioSimSpace: Making biomolecular simulation a breeze!
#
# Copyright: 2017-2019
#
# Authors: Lester Hedges <lester.hedges@gmail.com>
#
# BioSimSpace is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 2 of the License, or
# (at your option) any later version.
#
# BioSimSpace is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with BioSimSpace. If not, see <http://www.gnu.org/licenses/>.
#####################################################################

"""
A thin wrapper around Sire.Mol. This is an internal package and should
not be directly exposed to the user.
Author: Lester Hedges <lester.hedges@gmail.com>
Author: Antonia Mey <antonia.mey@ed.ac.uk>
"""


import Sire.Base as _SireBase

from . import _task
from BioSimSpace._Exceptions import MissingSoftwareError as _MissingSoftwareError
from BioSimSpace._SireWrappers import Molecule as _Molecule

import BioSimSpace.IO as _IO

import os as _os


__all__=['Lomap']


try:
    _lomap_exe = _sb.findExe("lomap").absoluteFilePath()
except:
    _lomap_exe = None


class Lomap(_task.Task):

    def __init__(self, molecules, name='Lomap', work_dir=None, autostart=False):
        """Constructor
        
           Parameters
           ----------
           
           molecules : str, [ BioSimSpace._SireWrapper.Molecule ]
               String containing direcotry path, or list of moelcules generated with BioSimSpace
        
           name : str
               The name of the task.
           
           work_dir : str
               The working directory for the task.
           
           autostart : bool
               Whether to immediately start the task.
        """

        
        if _lomap_exe is None:
            raise _MissingSoftwareError("Lomap is not installed, please use: `pip install lomap` to install it")
        super().__init__(name=name, work_dir=work_dir, autostart=autostart)


        # Test if molcules is a string and that string is directory
        if type(molecules) is str:
            if not _os.path.isdir(molecules):
                raise IOError("Molecules directory %s does not exit!" % molecules)
            else:
                self._isdir = True
        
        elif type(molecules) is list and all(isinstance(x, _Molecule) for x in molecules):
           self._isdir = False

        else:
            # TODO: expand error string
            raise TypeError("`molecules` must be a directory or list of `BioSimSpace._SireWrappers.Molecule`")
        self._molecules = molecules


    def _run(self):
        
        print (self._isdir)
        # Write molecules to file for Lomap to read them
        if not self._isdir:
            for i,molecule in enumerate(self._molecules):
                # Here we need some information on where they came from so we can trace id/filename etc

                # TODO mayb name them other than by molecule list index?
                _IO.saveMolecules('%s/mol_%03d' % (self._work_dir,i), molecule, 'mol2')
        return 'blub'
