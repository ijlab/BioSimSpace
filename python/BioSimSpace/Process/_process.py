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
Functionality for running simulation processes.
"""

import collections as _collections
import glob as _glob
import os as _os
import pygtail as _pygtail
import timeit as _timeit
import warnings as _warnings
import tempfile as _tempfile
import zipfile as _zipfile

import Sire.Mol as _SireMol

from BioSimSpace import _is_interactive, _is_notebook

from ..Protocol._protocol import Protocol as _Protocol
from .._SireWrappers import System as _System

import BioSimSpace.Types._type as _Type
import BioSimSpace.Units as _Units

if _is_notebook():
    from IPython.display import FileLink as _FileLink

__author__ = "Lester Hedges"
__email_ = "lester.hedges@gmail.com"

__all__ = ["Process"]

class _MultiDict(dict):
    """A multi-valued dictionary."""
    def __setitem__(self, key, value):
        """Add the given value to the list of values for this key."""
        self.setdefault(key, []).append(value)

class Process():
    """Base class for running different biomolecular simulation processes."""

    def __init__(self, system, protocol, name=None, work_dir=None, seed=None, property_map={}):
        """Constructor.

           Parameters
           ----------

           system : :class:`System <BioSimSpace._SireWrappers.System>`
               The molecular system.

           protocol : :class:`Protocol <BioSimSpace.Protocol>`
               The protocol for the process.

           name : str
               The name of the process.

           work_dir : str
               The working directory for the process.

           seed : int
               A random number seed.

           property_map : dict
               A dictionary that maps system "properties" to their user defined
               values. This allows the user to refer to properties with their
               own naming scheme, e.g. { "charge" : "my-charge" }
        """

	# Don't allow user to create an instance of this base class.
        if type(self) is Process:
            raise Exception("<Process> must be subclassed.")

        # Check that the system is valid.
        if type(system) is not _System:
            raise TypeError("'system' must be of type 'BioSimSpace._SireWrappers.System'")

        # Check that the protocol is valid.
        if not isinstance(protocol, _Protocol):
            raise TypeError("'protocol' must be of type 'BioSimSpace.Protocol'")

        # Check that the working directory is valid.
        if work_dir is not None and type(work_dir) is not str:
            raise TypeError("'work_dir' must be of type 'str'")

        # Check that the seed is valid.
        if seed is not None and type(seed) is not int:
            raise TypeError("'seed' must be of type 'int'")

        # Check that the map is valid.
        if type(property_map) is not dict:
            raise TypeError("'property_map' must be of type 'dict'")

        # Set the process to None.
        self._process = None

        # Is the process running interactively? If so, don't block
        # when a get method is called.
        self._is_blocked = not _is_interactive()

        # Whether this process can generate trajectory data.
        # Even if a process can generate a trajectory, whether it does
        # will depend on the chosen protocol.
        self._has_trajectory = False

	# Copy the passed system, protocol, and process name.
        self._system = system._getSireSystem()
        self._protocol = protocol

        # Flag whether the system contains water molecules.
        self._has_water = system.nWaterMolecules() > 0

        # Flag whether the system contains perturbable molecules.
        self._has_perturbable = system.nPerturbableMolecules() > 0

        # Flag that the process isn't queued.
        self._is_queued = False

        # Set the name
        if name is None:
            self._name = None
        else:
            self.setName(name)

        # Set the random number seed.
        if seed is None:
            self._is_seeded = False
            self._seed = None
        else:
            self._is_seeded = True
            self.setSeed(seed)

        # Set the map.
        self._property_map = property_map.copy()

        # Set the timer and running time None.
        self._timer = None
        self._runtime = None

        # Set the command-line string to None
        self._command = None

        # Set the list of input files to None.
        self._input_files = None

        # Create a temporary working directory and store the directory name.
        if work_dir is None:
            self._tmp_dir = _tempfile.TemporaryDirectory()
            self._work_dir = self._tmp_dir.name

        # User specified working directory.
        else:
            # Use full path.
            if work_dir[0] != "/":
                work_dir = _os.getcwd() + "/" + work_dir
            self._work_dir = work_dir

            # Create the directory if it doesn't already exist.
            if not _os.path.isdir(work_dir):
                _os.makedirs(work_dir, exist_ok=True)

        # Files for redirection of stdout and stderr.
        self._stdout_file = "%s/%s.out" % (self._work_dir, name)
        self._stderr_file = "%s/%s.err" % (self._work_dir, name)

        # Initialise the configuration file string list.
        self._config = []

        # Initalise the command-line argument dictionary.
        self._args = _collections.OrderedDict()

        # Clear any existing output in the current working directory
        # and set out stdout/stderr files.
        self._clear_output()

    def __str__(self):
        """Return a human readable string representation of the object."""
        return "<BioSimSpace.Process.%s: system=%s, protocol=%s, exe='%s', name='%s', work_dir='%s', seed=%s>" \
            % (self.__class__.__name__, str(_System(self._system)), self._protocol.__repr__(),
               self._exe, self._name, self._work_dir, self._seed)

    def __repr__(self):
        """Return a string showing how to instantiate the object."""
        return "BioSimSpace.Process.%s(%s, %s, exe='%s', name='%s', work_dir='%s', seed=%s)" \
            % (self.__class__.__name__, str(_System(self._system)), self._protocol.__repr__(),
               self._exe, self._name, self._work_dir, self._seed)

    def _clear_output(self):
        """Reset stdout and stderr."""

        # Create the files. This makes sure that the 'stdout' and 'stderr'
        # methods can be called when the files are empty.
        open(self._stdout_file, "a").close()
        open(self._stderr_file, "a").close()

        # Initialise lists to store the contents of stdout and stderr.
        self._stdout = []
        self._stderr = []

        # Clean up any existing offset files.
        offset_files = _glob.glob("%s/*.offset" % self._work_dir)

        for file in offset_files:
            _os.remove(file)

    def start(self):
        """Start the process.

           Returns
           -------

           process : :class:`Process.Amber <BioSimSpace.Process.Amber>`
               The process object.
        """
        raise NotImplementedError("Derived method 'BioSimSpace.Process.%s.start()' is not implemented!" % self.__class__.__name__)

    def run(self, system=None, protocol=None, autostart=True, restart=False):
        """Create and run a new process.

           Parameters
           ----------

           system : :class:`System <BioSimSpace._SireWrappers.System>`
               The molecular system.

           protocol : :class:`Protocol <BioSimSpace.Protocol>`
               The simulation protocol.

           autostart : bool
               Whether to start the process automatically.

           restart : bool
               Whether to restart the simulation, i.e. use the original system.

           Returns
           -------

           process : :class:`Procees <BioSimSpace.Process>`
               The new process object.
        """

        # Try to get the current system.
        if not restart:
            system = self.getSystem()

        # Use the existing system.
        if system is None:
            system = _System(self._system)

        # Check that the new system is valid.
        else:
            if type(system) is not _System:
                raise TypeError("'system' must be of type 'BioSimSpace._SireWrappers.System'")

        # Use the existing protocol.
        if protocol is None:
            protocol = self._protocol

        # Check that the new protocol is valid.
        else:
            if not isinstance(protocol, _Protocol):
                raise TypeError("'protocol' must be of type 'BioSimSpace.Protocol'")

        # Create the new process.
        process = type(self)(system, protocol)

        # Return the new process object.
        if autostart:
            return process.start()
        else:
            return process

    def getPackageName(self):
        """Return the package name.

           Returns
           -------

           name : str
               The name of the package.
        """
        return self._package_name

    def getName(self):
        """Return the process name.

           Returns:

           name : str
               The name of the process.
        """
        return self._name

    def setName(self, name):
        """Set the process name.

           Parameters
           ----------

           name : str
               The process name.
        """

        if type(name) is not str:
            raise TypeError("'name' must be of type 'str'")
        else:
            self._name = name

    def getSeed(self):
        """Return the random number seed.

           Returns
           -------

           seed : int
               The random number seed.
        """
        return self._seed

    def setSeed(self, seed):
        """Set the random number seed.

           Parameters
           ----------

           seed : int
               The random number seed.
        """

        if type(seed) is not int:
            _warnings.warn("The seed must be an integer. Disabling seeding.")
            self._seed = None
        else:
            self._seed = seed

    def wait(self, max_time=None):
        """Wait for the process to finish.

           Parameters
           ----------

           max_time: :class:`Time <BioSimSpace.Types.Time>`, int, float
               The maximimum time to wait (in minutes).
        """

        # The process isn't running.
        if not self.isRunning():
            return

        if max_time is not None:
            # Convert int to float.
            if type(max_time) is int:
                max_time = float(max_time)

            # BioSimSpace.Types.Time
            if isinstance(max_time, _Type.Type):
                max_time = int(max_time.milliseconds().magnitude())

            # Float.
            elif type(max_time) is float:
                if max_time <= 0:
                    raise ValueError("'max_time' cannot be negative!")

                # Convert the time to milliseconds.
                max_time = int(max_time * 60 * 1000)

            else:
                raise TypeError("'max_time' must be of type 'BioSimSpace.Types.Time' or 'float'.")

            # Wait for the desired amount of time.
            self._process.wait(max_time)

        else:
            # Wait for the process to finish.
            self._process.wait()

    def isQueued(self):
        """Return whether the process is queued.

           Returns
           -------

           is_queued : bool
               Whether the process is queued.
        """
        return self._is_queued

    def isRunning(self):
        """Return whether the process is running.

           Returns
           -------

           is_running : bool
               Whether the process is running.
        """
        try:
            return self._process.isRunning()
        except AttributeError:
            return False

    def isError(self):
        """Return whether the process errored.

           Returns
           -------

           is_error : bool
               Whether the process errored.
        """
        try:
            return self._process.isError()
        except AttributeError:
            return False

    def kill(self):
        """Kill the running process."""
        if not self._process is None and self._process.isRunning():
            self._process.kill()

    def stdout(self, n=10):
        """Print the last n lines of the stdout buffer.

           Parameters
           ----------

           n : int
               The number of lines to print.
        """

        # Ensure that the number of lines is positive.
        if n < 0:
            raise ValueError("The number of lines must be positive!")

        # Append any new lines to the stdout list.
        for line in _pygtail.Pygtail(self._stdout_file):
            self._stdout.append(line.rstrip())

        # Get the current number of lines.
        num_lines = len(self._stdout)

        # Set the line from which to start printing.
        if num_lines < n:
            start = 0
        else:
            start = num_lines - n

        # Print the lines.
        for x in range(start, num_lines):
            print(self._stdout[x])

    def stderr(self, n=10):
        """Print the last n lines of the stderr buffer.

           Parameters
           ----------

           n : int
               The number of lines to print.
        """

        # Ensure that the number of lines is positive.
        if n < 0:
            raise ValueError("The number of lines must be positive!")

        # Append any new lines to the stdout list.
        for line in _pygtail.Pygtail(self._stderr_file):
            self._stderr.append(line.rstrip())

        # Get the current number of lines.
        num_lines = len(self._stderr)

        # Set the line from which to start printing.
        if num_lines < n:
            start = 0
        else:
            start = num_lines - n

        # Print the lines.
        for x in range(start, num_lines):
            print(self._stderr[x])

    def exe(self):
        """Return the executable.

           Returns
           -------

           exe : str
               The path to the executable.
        """
        return self._exe

    def inputFiles(self):
        """Return the list of input files.

           Returns
           -------

           input_files : [str]
               The list of autogenerated input files.
        """
        return self._input_files.copy()

    def workDir(self):
        """Return the working directory.

           Returns
           -------

           work_dir : str
               The path of the working directory.
        """
        return self._work_dir

    def getStdout(self, block="AUTO"):
        """Return the entire stdout for the process as a list of strings.

           Parameters
           ----------

           block : bool
               Whether to block until the process has finished running.

           Returns
           -------

           output : [str]
               The list of stdout strings.
        """

        # Wait for the process to finish.
        if block is True:
            self.wait()
        elif block == "AUTO" and self._is_blocked:
            self.wait()

        # Append any new lines to the stdout list.
        for line in _pygtail.Pygtail(self._stdout_file):
            self._stdout.append(line.rstrip())

        return self._stdout.copy()

    def getStderr(self, block="AUTO"):
        """Return the entire stderr for the process as a list of strings.

           Parameters
           ----------

           block : bool
               Whether to block until the process has finished running.

           Returns
           -------

           error : [str]
               The list of stderror strings.
        """

        # Wait for the process to finish.
        if block is True:
            self.wait()
        elif block == "AUTO" and self._is_blocked:
            self.wait()

        # Append any new lines to the stdout list.
        for line in _pygtail.Pygtail(self._stderr_file):
            self._stderr.append(line.rstrip())

        return self._stderr.copy()

    def getInput(self, name=None, file_link=False):
        """Return a link to a zip file containing the input files used by
           the process.

           Parameters
           ----------

           name : str
               The name of the zip file.

           file_link : bool
               Whether to return a FileLink when working in Jupyter.

           Returns
           -------

           ouput : str, IPython.display.FileLink
               A path, or file link, to an archive of the process input.
        """

        if name is None:
            name = self._name + "_input"
        else:
            if type(name) is not str:
                raise TypeError("'name' must be of type 'str'")

        # Generate the zip file name.
        zipname = "%s.zip" % name

        with _zipfile.ZipFile(zipname, "w") as zip:
            # Loop over all of the file outputs.
            for file in self.inputFiles():
                zip.write(file, arcname=_os.path.basename(file))

        # Return a link to the archive.
        if _is_notebook():
            if file_link:
                return _FileLink(zipname)
            else:
                return zipname
        # Return the path to the archive.
        else:
            return zipname

    def getOutput(self, name=None, block="AUTO", file_link=False):
        """Return a link to a zip file of the working directory.

           Parameters
           ----------

           name : str
               The name of the zip file.

           block : bool
               Whether to block until the process has finished running.

           file_link : bool
               Whether to return a FileLink when working in Jupyter.

           Returns
           -------

           ouput : str, IPython.display.FileLink
               A path, or file link, to an archive of the process output.
        """

        if name is None:
            name = self._name + "_output"
        else:
            if type(name) is not str:
                raise TypeError("'name' must be of type 'str'")

        # Wait for the process to finish.
        if block is True:
            self.wait()
        elif block == "AUTO" and self._is_blocked:
            self.wait()

        # Generate the zip file name.
        zipname = "%s.zip" % name

        # Glob all of the output files.
        output = _glob.glob("%s/*" % self._work_dir)

        with _zipfile.ZipFile(zipname, "w") as zip:
            # Loop over all of the file outputs.
            for file in output:
                zip.write(file, arcname=_os.path.basename(file))

        # Return a link to the archive.
        if _is_notebook():
            if file_link:
                return _FileLink(zipname)
            else:
                return zipname
        # Return the path to the archive.
        else:
            return zipname

    def command(self):
        """Return the command-line string used to run the process.

           Returns
           -------

           command : str
               The command string.
        """
        return self._command

    def getConfig(self):
        """Get the list of configuration file strings.

           Returns
           -------

           config : [str]
               The list of configuration strings.
        """
        return self._config.copy()

    def setConfig(self, config):
        """Set the list of configuration file strings.

           Parameters
           ----------

           config : str, [str]
               The list of configuration strings, or a path to a configuration
               file.
        """

        # Check that the passed configuration is a list of strings.
        if _is_list_of_strings(config):
            self._config = config
            self.writeConfig(self._config_file)

        # The user has passed a path to a file.
        elif _os.path.isfile(config):

            # Clear the existing config.
            self._config = []

            # Read the contents of the file.
            with open(config, "r") as file:
                for line in file:
                    self._config.append(line.rstrip())

            # Write the new configuration file.
            self.writeConfig(self._config_file)

        else:
            raise ValueError("'config' must be a list of strings, or a file path.")

        # Flag that the protocol has been customised.
        self._protocol._setCustomised(True)

    def addToConfig(self, config):
        """Add a string to the configuration list.

           Parameters
           ----------

           config : str, [ str ]
               A configuration string, a list of configuration strings, or a
               path to a configuration file.
        """

        # Append a single string.
        if type(config) is str:
            self._config.append(config)
            self.writeConfig(self._config_file)

        # Extend the list with the additional strings.
        elif _is_list_of_strings(config):
            self._config.extend(config)
            self.writeConfig(self._config_file)

        # A path to a file.
        elif _os.path.isfile(config):

            # Read the contents of the file.
            with open(config, "r") as file:
                for line in file:
                    self._config.append(line)

            # Write the new configuration file.
            self.writeConfig(self._config_file)

        else:
            raise ValueError("'config' must be a string, list of strings, or a file path.")

        # Flag that the protocol has been customised.
        self._protocol._setCustomised(True)

    def resetConfig(self):
        """Reset the configuration parameters."""
        self._generate_config()

        # Write the new configuration file.
        self.writeConfig(self._config_file)

        # Reset the customisation state of the protocol.
        self._protocol._setCustomised(False)

    def writeConfig(self, file):
        """Write the configuration to file.

           Parameters
           ----------

           file : str
               The path to a file.
        """
        if type(file) is not str:
            raise TypeError("'file' must be of type 'str'")

        with open(file, "w") as f:
            for line in self._config:
                f.write("%s\n" % line)

    def getArgs(self):
        """Get the dictionary of command-line arguments.

           Returns
           -------

           args : collections.OrderedDict
               The dictionary of command-line arguments.
        """
        return self._args.copy()

    def getArgString(self):
        """Get the command-line arguments string.

           Returns
           -------

           arg_string : str
               The command-line argument string.
        """
        return " ".join(self.getArgStringList())

    def getArgStringList(self):
        """Convert the argument dictionary into a list of strings.

           Returns
           -------

           arg_string_list : [str]
               The list of command-line arguments.
        """

        # Create an empty list.
        args = []

        # Add the arguments to the list.
        for key, value in self._args.items():
            # Boolean flag.
            if type(value) is bool:
                if value:
                    args.append(str(key))
            else:
                args.append(str(key))
                args.append(str(value))

        return args

    def setArgs(self, args):
        """Set the dictionary of command-line arguments.

           Parameters
           ----------

           args : dict, collections.OrderedDict
               A dictionary of command-line arguments.
        """
        if isinstance(args, _collections.OrderedDict):
            self._args = args

        elif isinstance(args, dict):
            self._args = _collections.OrderedDict(args)

        else:
            raise TypeError("'args' must be of type 'dict' or 'collections.OrderedDict'")

    def setArg(self, arg, value):
        """Set a specific command-line argument.

           For command-line flags, i.e. boolean arguments, the key should
           specify whether the flag is enabled (True) or not (False).

           Parameters
           ----------

           arg : str
               The argument to set.

           value : bool, str
               The value of the argument.
        """

        if type(arg) is not str:
            raise TypeError("'arg' must be of type 'str'.")

        self._args[arg] = value

    def insertArg(self, arg, value, index):
        """Insert a command-line argument at a specific index.

           Parameters
           ----------

           arg : str
               The argument to set.

           value :
               The value of the argument.

           index : int
               The index in the dictionary.
        """

        if type(arg) is not str:
            raise TypeError("'arg' must be of type 'str'.")

        _odict_insert(self._args, arg, value, index)

    def addArgs(self, args):
        """Append additional command-line arguments.

           Parameters
           ----------

           args : dict, collections.OrderedDict
               A dictionary of command line arguments.
        """
        if isinstance(args, dict) or isinstance(args, _collections.OrderedDict):
            for arg, value in args.items():
                self._args[arg] = value
        else:
            raise TypeError("'args' must be of type 'dict' or 'collections.OrderedDict'")

    def deleteArg(self, arg):
        """Delete an argument from the dictionary.

           Parameters
           ----------

           arg : str
               The argument to delete.
        """
        try:
            del self._args[arg]

        except KeyError:
            pass

    def clearArgs(self):
        """Clear all of the command-line arguments."""
        self._args.clear()

    def resetArgs(self):
        """Reset the command-line arguments."""
        self._generate_args()

    def runTime(self):
        """Return the running time for the process (in minutes).

           Returns
           -------

           runtime : :class:`Time <BioSimSpace.Types.Time>`
               The runtime in minutes.
        """

        # The process is still running.
        if self.isRunning():
            self._runtime = (_timeit.default_timer() - self._timer) / 60
            return self._runtime * _Units.Time.minute

        # The process has finished.
        else:
            # Return the runtime and reset the timer.
            if self._timer is not None:
                self._runtime = (_timeit.default_timer() - self._timer) / 60
                self._timer = None
                return self._runtime * _Units.Time.minute

            else:
                # The process hasn't been started.
                if self._runtime is None:
                    return 0 * _Units.Time.minute
                # The process has finished, return the final runtime.
                else:
                    return self._runtime * _Units.Time.minute

    def getSystem(self, block="AUTO"):
        """Get the latest molecular system.

           Parameters
           ----------

           block : bool
               Whether to block until the process has finished running.

           Returns
           -------

           system : :class:`System <BioSimSpace._SireWrappers.System>`
               The latest molecular system.
        """
        raise NotImplementedError("Derived method 'BioSimSpace.Process.%s.getSystem()' is not implemented!" % self.__class__.__name__)

    def getTrajectory(self, block="AUTO"):
        """Return a trajectory object.

           Parameters
           ----------

           block : bool
               Whether to block until the process has finished running.

           Returns
           -------

           trajectory : :class:`Trajectory <BioSimSpace.Trajectory.Trajectory>`
               The latest trajectory object.
        """
        raise NotImplementedError("Derived method 'BioSimSpace.Process.%s.getTrajectory()' is not implemented!" % self.__class__.__name__)

    def _generate_args(self):
        """Generate the dictionary of command-line arguments."""
        self.clearArgs()

def _restrain_backbone(system):
    """Restrain protein backbone atoms.

        Parameters
        ----------

        system : Sire.System.System
            A Sire molecular system.
    """

    # Copy the original system.
    s = system

    # A list of amino acid name abbreviations.
    # Since we only want to restrain atoms in protein backbones, we compare
    # molecule residue names against this list in order to determine whether
    # the molecule is a protein.
    amino_acids = ["ALA", "CYS", "ASP", "GLU", "PHE", "GLY", "HIS", "ILE",
        "LYS", "LEU", "MET", "ASN", "PRO", "GLN", "ARG", "SER", "THR", "SEC",
        "VAL", "TRP", "TYR"]

    # Loop over all molecules by number.
    for n in s.molNums():

        # Extract the molecule and make it editable.
        m = s.molecule(n).edit()

        # Initialise a list of protein residues.
        protein_residues = []

        # Compare each residue name against the amino acid list.
        for res in m.residues():

            # This residue is an amino acid.
            if res.name().value().upper() in amino_acids:
                protein_residues.append(res.index())

        # Loop over all of the protein residues.
        for residx in protein_residues:

            # Loop over all of the atoms in the residue.
            for atom in m.residue(residx).atoms():

                # Try to compare the atom element property against the list of
                # backbone atoms and set the "restrained" property if a match
                # is found.
                try:
                    element = atom.property("element")
                    if element == _SireMol.Element("CA") or \
                       element == _SireMol.Element("N")  or \
                       element == _SireMol.Element("C")  or \
                       element == _SireMol.Element("O"):
                           m = m.atom(atom.index()).setProperty("restrained", 1.0).molecule()

                except:
                    pass

        # Update the system.
        s.update(m.commit())

    # Return the new system.
    return s

def _is_list_of_strings(lst):
    """Check whether the passed argument is a list of strings."""
    if lst and isinstance(lst, list):
        return all(isinstance(elem, str) for elem in lst)
    else:
        return False

def _odict_insert(dct, key, value, index):
    """Insert an item into an ordered dictionary."""

    if type(index) is not int:
        raise TypeError("'index' must be of type 'int'.")

    # Store the original size of the dictionary.
    n = len(dct)

    # Make sure the index is within range.
    if index < 0 or index > n+1:
        raise IndexError("Dictionary index out of range!")

    # Insert the new item at the end.
    dct[key] = value

    # Now loop over the original dict, moving any items
    # beyond 'index' to the end.

    # Index counter
    i = 0

    for item in list(dct):
        i += 1

        if i > n:
            break
        elif i > index:
            dct.move_to_end(item)
