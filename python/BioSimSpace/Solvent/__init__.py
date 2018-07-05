######################################################################
# BioSimSpace: Making biomolecular simulation a breeze!
#
# Copyright: 2017-2018
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
Functionality for solvating molecular systems.
Author: Lester Hedges <lester.hedges@gmail.com>
"""

from BioSimSpace import _gmx_exe, _gromacs_path

from .._SireWrappers import System as _System
from .._SireWrappers import Molecule as _Molecule
from ..Types import Length as _Length

import BioSimSpace.IO as _IO

import os as _os
import re as _re
import shutil as _shutil
import subprocess as _subprocess
import sys as _sys
import tempfile as _tempfile
import warnings as _warnings

if _gmx_exe is None or _gromacs_path is None:
    _warnings.warn("'BioSimSpace.Solvent' is not supported. Please "
        + "install GROMACS: http://www.gromacs.org")

def spc(molecule=None, box=None, shell=None, map={}):
    """Add SPC solvent.

       Keyword arguments:

       molecule -- A molecule, or system of molecules.
       box      -- A list containing the box size in each dimension (in nm).
       shell    -- Thickness of the water shell around the solute.
       map      -- A dictionary that maps system "properties" to their user defined
                   values. This allows the user to refer to properties with their
                   own naming scheme, e.g. { "charge" : "my-charge" }
    """

    if _gmx_exe is None or _gromacs_path is None:
        _warnings.warn("'BioSimSpace.Solvent.spc' is not supported!")
        return None

    # Validate arguments.
    molecule, box, shell = _validate_input(molecule, box, shell, map)

    # Create the solvated system.
    return _solvate(molecule, box, shell, "spc", 3)

def spce(molecule=None, box=None, shell=None, map={}):
    """Add SPC/E solvent.

       Keyword arguments:

       molecule -- A molecule, or system of molecules.
       box      -- A list containing the box size in each dimension (in nm).
       shell    -- Thickness of the water shell around the solute.
       map      -- A dictionary that maps system "properties" to their user defined
                   values. This allows the user to refer to properties with their
                   own naming scheme, e.g. { "charge" : "my-charge" }
    """

    if _gmx_exe is None:
        _warnings.warn("'BioSimSpace.Solvent.spce' is not supported!")
        return None

    # Validate arguments.
    molecule, box, shell = _validate_input(molecule, box, shell, map)

    # Create the solvated system.
    return _solvate(molecule, box, shell, "spce", 3)

def tip3p(molecule=None, box=None, shell=None, map={}):
    """Add TIP3P solvent.

       Keyword arguments:

       molecule -- A molecule, or system of molecules.
       box      -- A list containing the box size in each dimension (in nm).
       shell    -- Thickness of the water shell around the solute.
       map      -- A dictionary that maps system "properties" to their user defined
                   values. This allows the user to refer to properties with their
                   own naming scheme, e.g. { "charge" : "my-charge" }
    """

    if _gmx_exe is None:
        _warnings.warn("'BioSimSpace.Solvent.tip3p' is not supported!")
        return None

    # Validate arguments.
    molecule, box, shell = _validate_input(molecule, box, shell, map)

    # Create the solvated system.
    return _solvate(molecule, box, shell, "tip3p", 3)

def tip4p(molecule=None, box=None, shell=None, map={}):
    """Add TIP4P solvent.

       Keyword arguments:

       molecule -- A molecule, or system of molecules.
       box      -- A list containing the box size in each dimenion (in nm).
       shell    -- Thickness of the water shell around the solute.
       map      -- A dictionary that maps system "properties" to their user defined
                   values. This allows the user to refer to properties with their
                   own naming scheme, e.g. { "charge" : "my-charge" }
    """

    if _gmx_exe is None:
        _warnings.warn("'BioSimSpace.Solvent.tip4p' is not supported!")
        return None

    # Validate arguments.
    molecule, box, shell = _validate_input(molecule, box, shell, map)

    # Return the solvated system.
    return _solvate(molecule, box, shell, "tip4p", 4)

def tip5p(molecule=None, box=None, shell=None, map={}):
    """Add TIP5P solvent.

       Keyword arguments:

       molecule -- A molecule, or system of molecules.
       box      -- A list containing the box size in each dimenion (in nm).
       shell    -- Thickness of the water shell around the solute.
       map      -- A dictionary that maps system "properties" to their user defined
                   values. This allows the user to refer to properties with their
                   own naming scheme, e.g. { "charge" : "my-charge" }
    """

    if _gmx_exe is None:
        _warnings.warn("'BioSimSpace.Solvent.tip5p' is not supported!")
        return None

    # Validate arguments.
    molecule, box, shell = _validate_input(molecule, box, shell, map)

    # Return the solvated system.
    return _solvate(molecule, box, shell, "tip5p", 5)

def _validate_input(molecule, box, shell, map):
    """Internal function to validate function arguments.

       Positional arguments:

       molecule -- A molecule, or system of molecules.
       box      -- A list containing the box size in each dimension (in nm).
       shell    -- Thickness of the water shell around the solute.
       map      -- A dictionary that maps system "properties" to their user defined
                   values. This allows the user to refer to properties with their
                   own naming scheme, e.g. { "charge" : "my-charge" }
    """

    if molecule is not None:
        if type(molecule) is not _Molecule and type(molecule) is not _System:
            raise TypeError("'molecule' must be of type 'BioSimSpace.Molecule' "
                + "or 'BioSimSpace.System'")

        # Try to extract the box dimensions from the system.
        if type(molecule) is _System and box is None:
            try:
                if "space" in map:
                    prop = map["space"]
                else:
                    prop = "space"
                box = system.property(prop).dimensions()
                # Convert to a list of Length objects.
                box = [_Length(box[0], "A"), _Length(box[1], "A"), _Length(box[2], "A")]
            except:
                raise ValueError("The system has no box information. Please use "
                    + "the 'box' keyword argument.")
        else:
            if box is None:
                raise ValueError("Missing 'box' keyword argument!")
    else:
        if box is None:
            raise ValueError("Missing 'box' keyword argument!")

        if shell is not None:
            _warnings.warn("Ignoring 'shell' keyword argument as solute is missing.")
            shell = None

    if box is not None:
        if len(box) != 3:
            raise ValueError("The 'box' must have x, y, and z size information.")
        else:
            if not all(isinstance(x, _Length) for x in box):
                raise ValueError("The box dimensions must be of type 'BioSimSpace.Types.Length'")

    if shell is not None:
        if type(shell) is not _Length:
            raise ValueError("'shell' must must be of type 'BioSimSpace.Types.Length'")

    if type(map) is not dict:
        raise TypeError("'map' must be of type 'dict'")

    # Check that the box is large enough to hold the molecule.
    if molecule is not None and not _check_box_size(molecule, box):
        raise ValueError("The 'box' is not large enough to hold the 'molecule'")

    return (molecule, box, shell)

def _solvate(molecule, box, shell, model, num_point, work_dir=None, map={}):
    """Internal function to add solvent using 'gmx solvate'.

       Positional arguments:

       molecule  -- A molecule, or system of molecules.
       box       -- A list containing the box size in each dimension (in nm).
       shell     -- Thickness of the water shell around the solute.
       model     -- The name of the water model.
       num_point -- The number of points in the model.

       Keyword arguments:

       work_dir -- The working directory for the process.
       map      -- A dictionary that maps system "properties" to their user defined
                   values. This allows the user to refer to properties with their
                   own naming scheme, e.g. { "charge" : "my-charge" }
    """

    # Store the centre of the molecule.
    center = molecule._getAABox().center()

    # Work out the vector from the centre of the molecule to the centre of the
    # water box, converting the distance in each direction to Angstroms.
    vec = []
    for x, y in zip(box, center):
        vec.append(0.5*x.angstroms().magnitude() - y)

    # Translate the molecule. This allows us to create a water box
    # around the molecule.
    molecule.translate(vec)

    # Store the current working directory.
    dir = _os.getcwd()

    # Create a temporary working directory and store the directory name.
    if work_dir is None:
        tmp_dir = _tempfile.TemporaryDirectory()
        work_dir = tmp_dir.name

    # User specified working directory.
    else:
        # Create the directory if it doesn't already exist.
        if not _os.path.isdir(work_dir):
            _os.makedirs(work_dir)

    if work_dir is not None:
        # Change to the working directory for the process.
        # This avoid problems with relative paths.
        _os.chdir(work_dir)

    # Create the gmx command.
    if num_point == 3:
        mod = "spc216"
    else:
        mod = model
    command = "%s solvate -cs %s" % (_gmx_exe, mod)

    if molecule is not None:
        # Write the molecule/system to a GRO files.
        _IO.saveMolecules("input", molecule, "gro87")
        _shutil.copyfile("input.gro87", "input.gro")

        # Update the command.
        command += " -cp input.gro"

        # Add the box information.
        if box is not None:
            command += " -box %f %f %f" % (box[0].nanometers().magnitude(),
                                           box[1].nanometers().magnitude(),
                                           box[2].nanometers().magnitude())

        # Add the shell information.
        if shell is not None:
            command += " -shell %f" % shell.nanometers().magnitude()

    # Just add box information.
    else:
        command += " -box %f %f %f" % (box[0].nanometers().magnitude(),
                                       box[1].nanometers().magnitude(),
                                       box[2].nanometers().magnitude())

    # Add the output file.
    command += " -o output.gro"

    # Run the command.
    proc = _subprocess.run(command, shell=True,
        stdout=_subprocess.PIPE, stderr=_subprocess.PIPE)

    # gmx doesn't return sensible error codes, so we need to check that
    # the expected output was generated.
    if _os.path.isfile("output.gro"):

        # Extract the water lines from the GRO file.
        water_lines = []
        with open("output.gro", "r") as file:
            for line in file:
                if _re.search("SOL", line):
                    water_lines.append(line)

            # Add any box information. This is the last line in the GRO file.
            water_lines.append(line)

        # Write a GRO file that contains only the water atoms.
        if len(water_lines) - 1 > 0:
            with open("water.gro", "w") as file:
                file.write("BioSimSpace %s water box\n" % model.upper())
                file.write("%d\n" % (len(water_lines)-1))

                for line in water_lines:
                    file.write("%s" % line)

        # Create a TOP file for the water model. By default we use the Amber03
        # force field to generate a dummy topology for the water model.
        with open("water.top", "w") as file:
            file.write("; Include AmberO3 force field\n")
            file.write('#include "amber03.ff/forcefield.itp"\n\n')
            file.write("; Include %s water topology\n" % model.upper())
            file.write('#include "amber03.ff/%s.itp"\n\n' % model)
            file.write("[ system ] \n")
            file.write("BioSimSpace %s water box\n\n" % model.upper())
            file.write("[ molecules ] \n")
            file.write(";molecule name    nr.\n")
            file.write("SOL               %d\n" % ((len(water_lines)-1) / num_point))

        # Load the water box.
        water = _IO.readMolecules(["water.gro", "water.top"])

        # Translate the molecule and water back to the original position.
        vec = [-x for x in vec]
        molecule.translate(vec)
        water.translate(vec)

        # Create a new system by adding the water to the original molecule.
        if molecule is not None:
            if type(molecule) is _System:
                system = molecule.addMolecules(water.getMolecules())
            else:
                system = molecule + water.getMolecules()

                if "space" in map:
                    prop = map["space"]
                else:
                    prop = "space"

                # Add the space property from the water system.
                system._sire_system.setProperty(prop, water._sire_system.property(prop))
        else:
            system = water

        # Change back to the original directory.
        if work_dir is not None:
            _os.chdir(dir)

        return system

def _check_box_size(molecule, box):
    """Internal function to check that box is big enough for the molecule.

       Positional arguments:

       molecule -- A molecule, or system of molecules.
       box      -- A list containing the box size in each dimension (in nm).
    """

    # Get the axis-aligned bounding box of the molecule/system.
    aabox = molecule._getAABox()

    # Calculate the box size in each dimension, storing each component as a
    # length in Angstroms.
    mol_box = [_Length(2*x," A") for x in aabox.halfExtents()]

    # Make sure the box is big enough in each dimension.
    for len1, len2 in zip(box, mol_box):
        if len1 < len2:
            return False

    # We made it this far, all dimensions are large enough.
    return True
