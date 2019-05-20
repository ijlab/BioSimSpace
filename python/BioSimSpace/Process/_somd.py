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
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with BioSimSpace. If not, see <http://www.gnu.org/licenses/>.
#####################################################################

"""
Functionality for running simulations with SOMD.
"""

import math as _math
import os as _os
import pygtail as _pygtail
import timeit as _timeit
import warnings as _warnings

import Sire.Base as _SireBase
import Sire.IO as _SireIO

from . import _process
from .._Exceptions import IncompatibleError as _IncompatibleError
from .._Exceptions import MissingSoftwareError as _MissingSoftwareError
from .._SireWrappers import System as _System
from ..Trajectory import Trajectory as _Trajectory

import BioSimSpace.Protocol as _Protocol
import BioSimSpace._Utils as _Utils

__author__ = "Lester Hedges"
__email_ = "lester.hedges@gmail.com"

__all__ = ["Somd"]

class Somd(_process.Process):
    """A class for running simulations using SOMD."""

    # Dictionary of platforms and their OpenMM keyword.
    _platforms = { "CPU"    : "CPU",
                   "CUDA"   : "CUDA",
                   "OPENCL" : "OpenCL" }

    def __init__(self, system, protocol, exe=None, name="somd",
            platform="CPU", work_dir=None, seed=None, property_map={}):
        """Constructor.

           Parameters
           ----------

           system : :class:`System <BioSimSpace._SireWrappers.System>`
               The molecular system.

           protocol : :class:`Protocol <BioSimSpace.Protocol>`
               The protocol for the SOMD process.

           exe : str
               The full path to the SOMD executable.

           name : str
               The name of the process.

           platform : str
               The platform for the simulation: "CPU", "CUDA", or "OPENCL".

           work_dir :
               The working directory for the process.

           seed : int
               A random number seed.

           property_map : dict
               A dictionary that maps system "properties" to their user defined
               values. This allows the user to refer to properties with their
               own naming scheme, e.g. { "charge" : "my-charge" }
        """

        # Call the base class constructor.
        super().__init__(system, protocol, name, work_dir, seed, property_map)

        # Set the package name.
        self._package_name = "SOMD"

        # This process can generate trajectory data.
        self._has_trajectory = True

        if type(platform) is not str:
            raise TypeError("'platform' must be of type 'str'.")
        else:
            # Strip all whitespace and convert to upper case.
            platform = platform.replace(" ", "").upper()

            # Check for platform support.
            if platform not in self._platforms:
                raise ValueError("Supported platforms are: %s" % self._platforms.keys())
            else:
                self._platform = self._platforms[platform]

        # If the path to the executable wasn't specified, then use the bundled SOMD
        # executable.
        if exe is None:
            # Generate the name of the SOMD exe.
            if type(self._protocol) is _Protocol.FreeEnergy:
                somd_exe = _SireBase.getBinDir() + "/somd-freenrg"
            else:
                somd_exe = _SireBase.getBinDir() + "/somd"
            if not _os.path.isfile(somd_exe):
                raise _MissingSoftwareError("'Cannot find SOMD executable in expected location: '%s'" % somd_exe)
            else:
                self._exe = somd_exe
        else:
            # Make sure executable exists.
            if _os.path.isfile(exe):
                self._exe = exe
            else:
                raise IOError("SOMD executable doesn't exist: '%s'" % exe)

        # The names of the input files.
        self._rst_file = "%s/%s.rst7" % (self._work_dir, name)
        self._top_file = "%s/%s.prm7" % (self._work_dir, name)

        # The name of the trajectory file.
        self._traj_file = "%s/traj000000001.dcd" % self._work_dir

        # Set the path for the SOMD configuration file.
        self._config_file = "%s/%s.cfg" % (self._work_dir, name)

        # Set the path for the perturbation file.
        self._pert_file = "%s/%s.pert" % (self._work_dir, name)

        # Set the path for the gradient file and create the gradient list.
        self._gradient_file = "%s/gradients.dat" % self._work_dir
        self._gradients = []

        # Create the list of input files.
        self._input_files = [self._config_file, self._rst_file, self._top_file]

        # Now set up the working directory for the process.
        self._setup()

    def __str__(self):
        """Return a human readable string representation of the object."""
        return "<BioSimSpace.Process.%s: system=%s, protocol=%s, exe='%s', name='%s', platform='%s', work_dir='%s' seed=%s>" \
            % (self.__class__.__name__, str(_System(self._system)), self._protocol.__repr__(),
               self._exe, self._name, self._platform, self._work_dir, self._seed)

    def __repr__(self):
        """Return a string showing how to instantiate the object."""
        return "BioSimSpace.Process.%s(%s, %s, exe='%s', name='%s', platform='%s', work_dir='%s', seed=%s)" \
            % (self.__class__.__name__, str(_System(self._system)), self._protocol.__repr__(),
               self._exe, self._name, self._platform, self._work_dir, self._seed)

    def _setup(self):
        """Setup the input files and working directory ready for simulation."""

        # Create the input files...

        # First create a copy of the system.
        system = _System(self._system)

        # If the we are performing a free energy simulation, then check that
        # the system contains a single perturbable molecule. If so, then create
        # and write a perturbation file to the work directory.
        if type(self._protocol) is _Protocol.FreeEnergy:
            if system.nPerturbableMolecules() == 1:
                # Extract the perturbable molecule.
                pert_mol = system.getPerturbableMolecules()[0]

                # Write the perturbation file and get the molecule corresponding
                # to the lambda = 0 state.
                pert_mol = pert_mol._toPertFile(self._pert_file, property_map=self._property_map)
                self._input_files.append(self._pert_file)

                # Remove the perturbable molecule.
                system._sire_system.remove(pert_mol.number())

                # Recreate the system, putting the perturbable molecule with
                # renamed properties first.
                updated_system = _System(pert_mol) + _System(system)

                # Copy across all of the properties from the orginal system.
                for prop in system._sire_system.propertyKeys():
                    updated_system._sire_system.setProperty(prop, system._sire_system.property(prop))

                # Copy the updated system object across.
                system = updated_system

            else:
                raise ValueError("'BioSimSpace.Protocol.FreeEnergy' requires a single "
                                 "perturbable molecule. The system has %d" \
                                  % system.nPerturbableMolecules())

        # RST file (coordinates).
        try:
            rst = _SireIO.AmberRst7(system._sire_system, self._property_map)
            rst.writeToFile(self._rst_file)
        except:
            raise IOError("Failed to write system to 'RST7' format.") from None

        # PRM file (topology).
        try:
            prm = _SireIO.AmberPrm(system._sire_system, self._property_map)
            prm.writeToFile(self._top_file)
        except:
            raise IOError("Failed to write system to 'PRM7' format.") from None

        # Generate the SOMD configuration file.
        # Skip if the user has passed a custom config.
        if type(self._protocol) is _Protocol.Custom:
            self.setConfig(self._protocol.getConfig())
        else:
            self._generate_config()
        self.writeConfig(self._config_file)

        # Generate the dictionary of command-line arguments.
        self._generate_args()

        # Return the list of input files.
        return self._input_files

    def _generate_config(self):
        """Generate SOMD configuration file strings."""

        # Clear the existing configuration list.
        self._config = []

        # Check whether the system contains periodic box information.
        # For now, well not attempt to generate a box if the system property
        # is missing. If no box is present, we'll assume a non-periodic simulation.
        if "space" in self._system.propertyKeys():
            has_box = True
        else:
            _warnings.warn("No simulation box found. Assuming gas phase simulation.")
            has_box = False

        # Work out the GPU device ID.
        if self._platform == "CUDA":
            if "CUDA_VISIBLE_DEVICES" in _os.environ:
                try:
                    # Get the ID of the first available device.
                    #gpu_id = int(_os.environ.get("CUDA_VISIBLE_DEVICES").split(",")[0])
                    gpu_id = 0
                except:
                    raise EnvironmentError("'CUDA' platform is selected but cannot parse "
                                           "'CUDA_VISIBLE_DEVICES' environment variable!")
            else:
                raise EnvironmentError("'CUDA' platform selected but 'CUDA_VISIBLE_DEVICES' "
                                       "environment variable is unset.")

        # While the configuration parameters below share a lot of overlap,
        # we choose the keep them separate so that the user can modify options
        # for a given protocol in a single place.

        # Add configuration variables for a minimisation simulation.
        if type(self._protocol) is _Protocol.Minimisation:
            if self._platform == "CUDA":
                self.addToConfig("gpu = %d" % gpu_id)                   # GPU device ID.
            self.addToConfig("minimise = True")                         # Minimisation simulation.
            self.addToConfig("minimise maximum iterations = %d"         # Maximum number of steps.
                % self._protocol.getSteps())
            self.addToConfig("minimise tolerance = 1")                  # Convergence tolerance.
            self.addToConfig("ncycles = 1")                             # Perform a single SOMD cycle.
            self.addToConfig("nmoves = 1")                              # Perform a single MD move.
            self.addToConfig("save coordinates = True")                 # Save molecular coordinates.
            if not has_box or not self._has_water:
                self.addToConfig("cutoff type = cutoffnonperiodic")     # No periodic box.
            else:
                self.addToConfig("cutoff type = cutoffperiodic")        # Periodic box.
            self.addToConfig("cutoff distance = 10 angstrom")           # Non-bonded cut-off.

        # In the following protocols we save coordinates every cycle, which is
        # 100 MD steps (moves) in length (this is for consistency with other
        # MD drivers). Note that SOMD only saves coordinates to a DCD
        # trajectory file, so it's impossible to decouple the frequency of
        # recording configurations and trajectory frames, i.e. the number of
        # trajectory frames specified in the protocol is disregarded. This also
        # means that we lose the ability to use the user "property map" when
        # reading configurations from the trajectory.

        # Add configuration variables for an equilibration simulation.
        elif type(self._protocol) is _Protocol.Equilibration:
            # Only constant temperature equilibration simulations are supported.
            if not self._protocol.isConstantTemp():
                raise _IncompatibleError("SOMD only supports constant temperature equilibration.")

            # Backbone restraints aren't supported.
            if self._protocol.isRestrained():
                raise _IncompatibleError("SOMD doesn't support backbone atom restraints.")

            # Work out the number of cycles. (10000 MD steps per cycle.)
            ncycles = _math.ceil((self._protocol.getRunTime() / self._protocol.getTimeStep()) / 10000)

            # Convert the timestep to femtoseconds.
            timestep = self._protocol.getTimeStep().femtoseconds().magnitude()

            # Convert the temperature to Kelvin.
            temperature = self._protocol.getStartTemperature().kelvin().magnitude()

            if self._platform == "CUDA":
                self.addToConfig("gpu = %d" % gpu_id)                   # GPU device ID.
            self.addToConfig("ncycles = %d" % ncycles)                  # The number of SOMD cycles.
            self.addToConfig("nmoves = 10000")                          # Perform 10000 MD moves per cycle.
            self.addToConfig("save coordinates = True")                 # Save molecular coordinates.
            self.addToConfig("buffered coordinates frequency = 500")    # Save coordinates every 500 steps.
            self.addToConfig("timestep = %.2f femtosecond" % timestep)  # Integration time step.
            self.addToConfig("thermostat = True")                       # Turn on the thermostat.
            self.addToConfig("temperature = %.2f kelvin" % temperature) # System temperature.
            if self._protocol.getPressure() is None:
                self.addToConfig("barostat = False")                    # Disable barostat (constant volume).
            else:
                if self._has_water and has_box:
                    self.addToConfig("barostat = True")                 # Enable barostat.
                    self.addToConfig("pressure = %.5f atm"              # Presure in atmosphere.
                        % self._protocol.getPressure().atm().magnitude())
                else:
                    self.addToConfig("barostat = False")                # Disable barostat (constant volume).
            if self._has_water:
                self.addToConfig("reaction field dielectric = 78.3")    # Solvated box.
            else:
                self.addToConfig("reaction field dielectric = 82.0")    # Vacuum.
            if not has_box or not self._has_water:
                self.addToConfig("cutoff type = cutoffnonperiodic")     # No periodic box.
            else:
                self.addToConfig("cutoff type = cutoffperiodic")        # Periodic box.
            self.addToConfig("cutoff distance = 10 angstrom")           # Non-bonded cut-off.
            if self._is_seeded:
                self.addToConfig("random seed = %d" % self._seed)       # Random number seed.

        # Add configuration variables for a production simulation.
        elif type(self._protocol) is _Protocol.Production:

            # Work out the number of cycles. (10000 MD steps per cycle.)
            ncycles = _math.ceil((self._protocol.getRunTime() / self._protocol.getTimeStep()) / 10000)

            # Convert the timestep to femtoseconds.
            timestep = self._protocol.getTimeStep().femtoseconds().magnitude()

            # Convert the temperature to Kelvin.
            temperature = self._protocol.getTemperature().kelvin().magnitude()

            if self._platform == "CUDA":
                self.addToConfig("gpu = %d" % gpu_id)                   # GPU device ID.
            self.addToConfig("ncycles = %d" % ncycles)                  # The number of SOMD cycles.
            self.addToConfig("nmoves = 10000")                          # Perform 10000 MD moves per cycle.
            self.addToConfig("save coordinates = True")                 # Save molecular coordinates.
            self.addToConfig("buffered coordinates frequency = 500")    # Save coordinates every 500 steps.
            self.addToConfig("timestep = %.2f femtosecond" % timestep)  # Integration time step.
            self.addToConfig("thermostat = True")                       # Turn on the thermostat.
            self.addToConfig("temperature = %.2f kelvin" % temperature) # System temperature.
            if self._protocol.getPressure() is None:
                self.addToConfig("barostat = False")                    # Disable barostat (constant volume).
            else:
                if self._has_water and has_box:
                    self.addToConfig("barostat = True")                 # Enable barostat.
                    self.addToConfig("pressure = %.5f atm"              # Presure in atmosphere.
                        % self._protocol.getPressure().atm().magnitude())
                else:
                    self.addToConfig("barostat = False")                # Disable barostat (constant volume).
            if self._has_water:
                self.addToConfig("reaction field dielectric = 78.3")    # Solvated box.
            else:
                self.addToConfig("reaction field dielectric = 82.0")    # Vacuum.
            if not has_box or not self._has_water:
                self.addToConfig("cutoff type = cutoffnonperiodic")     # No periodic box.
            else:
                self.addToConfig("cutoff type = cutoffperiodic")        # Periodic box.
            self.addToConfig("cutoff distance = 10 angstrom")           # Non-bonded cut-off.
            if self._is_seeded:
                self.addToConfig("random seed = %d" % self._seed)       # Random number seed.

        # Add configuration variables for a free energy simulation.
        elif type(self._protocol) is _Protocol.FreeEnergy:

            # Work out the number of cycles. (10000 MD steps per cycle.)
            ncycles = _math.ceil((self._protocol.getRunTime() / self._protocol.getTimeStep()) / 10000)

            # Convert the timestep to femtoseconds.
            timestep = self._protocol.getTimeStep().femtoseconds().magnitude()

            # Convert the temperature to Kelvin.
            temperature = self._protocol.getTemperature().kelvin().magnitude()

            if self._platform == "CUDA":
                self.addToConfig("gpu = %d" % gpu_id)                   # GPU device ID.
            self.addToConfig("ncycles = %d" % ncycles)                  # The number of SOMD cycles.
            self.addToConfig("nmoves = 10000")                          # Perform 10000 MD moves per cycle.
            self.addToConfig("energy frequency = 100")                  # Frequency of free energy gradient evaluation.
            self.addToConfig("save coordinates = True")                 # Save molecular coordinates.
            self.addToConfig("buffered coordinates frequency = 500")    # Save coordinates every 500 steps.
            self.addToConfig("timestep = %.2f femtosecond" % timestep)  # Integration time step.
            self.addToConfig("thermostat = True")                       # Turn on the thermostat.
            self.addToConfig("temperature = %.2f kelvin" % temperature) # System temperature.
            if self._protocol.getPressure() is None:
                self.addToConfig("barostat = False")                    # Disable barostat (constant volume).
            else:
                if self._has_water and has_box:
                    self.addToConfig("barostat = True")                 # Enable barostat.
                    self.addToConfig("pressure = %.5f atm"              # Presure in atmosphere.
                        % self._protocol.getPressure().atm().magnitude())
                else:
                    self.addToConfig("barostat = False")                # Disable barostat (constant volume).
            if self._has_water:
                self.addToConfig("reaction field dielectric = 78.3")    # Solvated box.
            else:
                self.addToConfig("reaction field dielectric = 82.0")    # Vacuum.
            if not has_box or not self._has_water:
                self.addToConfig("cutoff type = cutoffnonperiodic")     # No periodic box.
            else:
                self.addToConfig("cutoff type = cutoffperiodic")        # Periodic box.
            self.addToConfig("cutoff distance = 10 angstrom")           # Non-bonded cut-off.
            if self._is_seeded:
                self.addToConfig("random seed = %d" % self._seed)       # Random number seed.
            self.addToConfig("constraint = hbonds-notperturbed")        # Handle hydrogen perturbations.
            self.addToConfig("minimise = True")                         # Perform a minimisation.
            self.addToConfig("equilibrate = False")                     # Don't equilibrate.
                                                                        # The lambda value array.
            self.addToConfig("lambda array = %s" \
                % ", ".join([str(x) for x in self._protocol.getLambdaValues()]))
            self.addToConfig("lambda_val = %s" \
                % self._protocol.getLambda())                           # The value of lambda.

        else:
            raise _IncompatibleError("Unsupported protocol: '%s'" % self._protocol.__class__.__name__)

        # Flag that this isn't a custom protocol.
        self._protocol._setCustomised(False)

    def _generate_args(self):
        """Generate the dictionary of command-line arguments."""

        # Clear the existing arguments.
        self.clearArgs()

        # Add the default arguments.
        self.setArg("-c", "%s.rst7" % self._name)                       # Coordinate restart file.
        self.setArg("-t", "%s.prm7" % self._name)                       # Topology file.
        if type(self._protocol) is _Protocol.FreeEnergy:
            self.setArg("-m", "%s.pert" % self._name)                   # Perturbation file.
        self.setArg("-C", "%s.cfg" % self._name)                        # Config file.
        self.setArg("-p", self._platform)                               # Simulation platform.

    def start(self):
        """Start the SOMD process.

           Returns
           -------

           process : :class:`Process.Somd <BioSimSpace.Process.Somd>`
               A handle to the running process.
        """

        # The process is currently queued.
        if self.isQueued():
            return

        # Process is already running.
        if self._process is not None:
            if self._process.isRunning():
                return

        # Clear any existing output.
        self._clear_output()

        # Run the process in the working directory.
        with _Utils.cd(self._work_dir):

            # Create the arguments string list.
            args = self.getArgStringList()

            # Write the command-line process to a README.txt file.
            with open("README.txt", "w") as f:

                # Set the command-line string.
                self._command = "%s " % self._exe + self.getArgString()

                # Write the command to file.
                f.write("# SOMD was run with the following command:\n")
                f.write("%s\n" % self._command)

            # Start the timer.
            self._timer = _timeit.default_timer()

            # Start the simulation.
            self._process = _SireBase.Process.run(self._exe, args,
                "%s.out"  % self._name, "%s.out"  % self._name)

            # SOMD uses the stdout stream for all output.
            with open(_os.path.basename(self._stderr_file), "w") as f:
                f.write("All output has been redirected to the stdout stream!\n")

        return self

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

        # Get the trajectory object.
        traj = self.getTrajectory(block=block)

        # Try to get the latest frame from the trajectory.
        try:
            new_system = traj.getFrames()[-1]

            # Since SOMD requires specific residue and water naming we copy the
            # coordinates back into the original system.
            old_system = _System(self._system)
            old_system._updateCoordinates(new_system)

            return old_system

        except:
            return None

    def getCurrentSystem(self):
        """Get the latest molecular system.

           Returns
           -------

           system : :class:`System <BioSimSpace._SireWrappers.System>`
               The latest molecular system.
        """
        return self.getSystem(block=False)

    def getTrajectory(self, block="AUTO"):
        """Return a trajectory object.

           Parameters
           ----------

           block : bool
               Whether to block until the process has finished running.

           Returns
           -------

           trajectory : :class:`Trajectory <BioSimSpace.Trajectory.trajectory>`
               The latest trajectory object.
        """

        # Wait for the process to finish.
        if block is True:
            self.wait()
        elif block == "AUTO" and self._is_blocked:
            self.wait()

        try:
            return _Trajectory(process=self)

        except:
            return None

    def getTime(self, time_series=False, block="AUTO"):
        """Get the time (in nanoseconds).

           Parameters
           ----------

           time_series : bool
               Whether to return a list of time series records.

           block : bool
               Whether to block until the process has finished running.

           Returns
           -------

           time : :class:`Time <BioSimSpace.Types.Time>`
               The current simulation time in nanoseconds.
        """

        # No time records for minimisation protocols.
        if type(self._protocol) is _Protocol.Minimisation:
            return None

        # Get the number of trajectory frames.
        num_frames = self.getTrajectory(block=block).nFrames()

        if num_frames == 0:
            return None

        # Create the list of time records. (Frames are saved every 100 MD steps.)
        try:
            times = [(100 * self._protocol.getTimeStep().nanoseconds()) * x for x in range(1, num_frames + 1)]
        except:
            return None

        if time_series:
            return times
        else:
            return times[-1]

    def getCurrentTime(self, time_series=False):
        """Get the current time (in nanoseconds).

           Parameters
           ----------

           time_series : bool
               Whether to return a list of time series records.

           Returns
           -------

           time : :class:`Time <BioSimSpace.Types.Time>`
               The current simulation time in nanoseconds.
        """
        return self.getTime(time_series, block=False)

    def getGradient(self, time_series=False, block="AUTO"):
        """Get the free energy gradient.

           Parameters
           ----------

           time_series : bool
               Whether to return a list of time series records.

           block : bool
               Whether to block until the process has finished running.

           Returns
           -------

           gradient : float
               The free energy gradient.
        """

        # Wait for the process to finish.
        if block is True:
            self.wait()
        elif block == "AUTO" and self._is_blocked:
            self.wait()

        # No gradient file.
        if not _os.path.isfile(self._gradient_file):
            return None

        # Append any new lines to the gradients list.
        for line in _pygtail.Pygtail(self._gradient_file):
            # Ignore comments.
            if line[0] != "#":
                self._gradients.append(float(line.rstrip().split()[-1]))

        if len(self._gradients) == 0:
            return None

        if time_series:
            return self._gradients
        else:
            return self._gradients[-1]

    def getCurrentGradient(self, time_series=False):
        """Get the current free energy gradient.

           Parameters
           ----------

           time_series : bool
               Whether to return a list of time series records.

           Returns
           -------

           gradient : float
               The current free energy gradient.
        """
        return self.getGradient(time_series, block=False)

    def _clear_output(self):
        """Reset stdout and stderr."""

        # Call the base class method.
        super()._clear_output()

        # Delete any restart and trajectory files in the working directory.

        file = "%s/sim_restart.s3" % self._work_dir
        if _os.path.isfile(file):
            _os.remove(file)

        file = "%s/SYSTEM.s3" % self._work_dir
        if _os.path.isfile(file):
            _os.remove(file)

        file = "%s/traj000000001.dcd" % self._work_dir
        if _os.path.isfile(file):
            _os.remove(file)

        # Additional files for free energy simulations.
        if type(self._protocol) is _Protocol.FreeEnergy:

            file = "%s/gradients.dat" % self._work_dir
            if _os.path.isfile(file):
                _os.remove(file)

            file = "%s/simfile.dat" % self._work_dir
            if _os.path.isfile(file):
                _os.remove(file)
