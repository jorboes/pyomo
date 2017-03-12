#  _________________________________________________________________________
#
#  Pyomo: Python Optimization Modeling Objects
#  Copyright (c) 2014 Sandia Corporation.
#  Under the terms of Contract DE-AC04-94AL85000 with Sandia Corporation,
#  the U.S. Government retains certain rights in this software.
#  This software is distributed under the BSD License.
#  _________________________________________________________________________

import os
import copy

import pyutilib.services
import pyutilib.misc

import pyomo.util.plugin
from pyomo.opt.base import *
from pyomo.opt.base.solvers import _extract_version
from pyomo.opt.results import *
from pyomo.opt.solver import *

import logging
logger = logging.getLogger('pyomo.solvers')

try:
    unicode
except:
    basestring = str

class IPOPT(SystemCallSolver):
    """
    An interface to the Ipopt optimizer that uses the AMPL Solver Library.
    """

    pyomo.util.plugin.alias('ipopt', doc='The Ipopt NLP solver')

    def __init__(self, **kwds):
        #
        # Call base constructor
        #
        kwds["type"] = "ipopt"
        super(IPOPT, self).__init__(**kwds)
        #
        # Setup valid problem formats, and valid results for each problem format
        # Also set the default problem and results formats.
        #
        self._valid_problem_formats=[ProblemFormat.nl]
        self._valid_result_formats = {}
        self._valid_result_formats[ProblemFormat.nl] = [ResultsFormat.sol]
        self.set_problem_format(ProblemFormat.nl)

        # Note: Undefined capabilities default to 'None'
        self._capabilities = pyutilib.misc.Options()
        self._capabilities.linear = True
        # Should we set this to False? Doing so might cause
        # a headache for some folks.
        self._capabilities.integer = True
        self._capabilities.quadratic_objective = True
        self._capabilities.quadratic_constraint = True
        self._capabilities.sos1 = True
        self._capabilities.sos2 = True

    def _default_results_format(self, prob_format):
        return ResultsFormat.sol

    def _default_executable(self):
        executable = pyutilib.services.registered_executable("ipopt")
        if executable is None:
            logger.warning("Could not locate the 'ipopt' executable, "
                           "which is required for solver %s" % self.name)
            self.enable = False
            return None
        return executable.get_path()

    def _get_version(self):
        """
        Returns a tuple describing the solver executable version.
        """
        solver_exec = self.executable()
        if solver_exec is None:
            return _extract_version('')
        results = pyutilib.subprocess.run( [solver_exec,"-v"], timelimit=1 )
        return _extract_version(results[1])

    def create_command_line(self, executable, problem_files):

        assert(self._problem_format == ProblemFormat.nl)
        assert(self._results_format == ResultsFormat.sol)

        #
        # Define log file
        #
        if self._log_file is None:
            self._log_file = pyutilib.services.TempfileManager.\
                             create_tempfile(suffix="_ipopt.log")

        fname = problem_files[0]
        if '.' in fname:
            tmp = fname.split('.')
            if len(tmp) > 2:
                fname = '.'.join(tmp[:-1])
            else:
                fname = tmp[0]
        self._soln_file = fname+".sol"

        #
        # Define results file (since an external parser is used)
        #
        self._results_file = self._soln_file

        #
        # Define command line
        #
        env=copy.copy(os.environ)

        cmd = [executable, problem_files[0], '-AMPL']
        if self._timer:
            cmd.insert(0, self._timer)

        env_opt = []
        of_opt = []
        ofn_option_used = False
        for key in self.options:
            if key == 'solver':
                continue
            elif key.startswith("OF_"):
                assert len(key) > 3
                of_opt.append((key[3:], self.options[key]))
            else:
                if key == "option_file_name":
                    ofn_option_used = True
                if isinstance(self.options[key], basestring) and ' ' in self.options[key]:
                    env_opt.append(key+"=\""+str(self.options[key])+"\"")
                    cmd.append(str(key)+"="+str(self.options[key]))
                elif key == 'subsolver':
                    env_opt.append("solver="+str(self.options[key]))
                    cmd.append(str(key)+"="+str(self.options[key]))
                else:
                    env_opt.append(key+"="+str(self.options[key]))
                    cmd.append(str(key)+"="+str(self.options[key]))

        if len(of_opt) > 0:
            # If the 'option_file_name' command-line option
            # was used, we don't know if we should overwrite,
            # merge it, or it is was a mistake, so raise an
            # exception. Maybe this can be changed.
            if ofn_option_used:
                raise ValueError(
                    "The 'option_file_name' command-line "
                    "option for Ipopt can not be used "
                    "when specifying options for the "
                    "options file (i.e., options that "
                    "start with 'OF_'")

            # Now check if an 'ipopt.opt' file exists in the
            # current working directory. If so, we need to
            # make it clear that this file will be ignored.
            default_of_name = os.path.join(os.getcwd(), 'ipopt.opt')
            if os.path.exists(default_of_name):
                logger.warning("A file named 'ipopt.opt' exists in "
                               "the current working directory, but "
                               "Ipopt options file options (i.e., "
                               "options that start with 'OF_') were "
                               "provided. The options file '%s' will "
                               "be ignored." % (default_of_name))

            # Now write the new options file
            options_filename = pyutilib.services.TempfileManager.\
                               create_tempfile(suffix="_ipopt.opt")
            with open(options_filename, "w") as f:
                for key, val in of_opt:
                    f.write(key+" "+str(val)+"\n")

            # Now set the command-line option telling Ipopt
            # to use this file
            env_opt.append('option_file_name="'+str(options_filename)+'"')
            cmd.append('option_file_name='+str(options_filename))

        envstr = "%s_options" % self.options.solver
        # Merge with any options coming in through the environment
        env[envstr] = " ".join(env_opt)

        return pyutilib.misc.Bunch(cmd=cmd, log_file=self._log_file, env=env)

pyutilib.services.register_executable(name="ipopt")
