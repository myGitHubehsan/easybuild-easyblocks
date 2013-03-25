##
# Copyright 2013 Dmitri Gribenko
#
# This file is triple-licensed under GPLv2 (see below), MIT, and
# BSD three-clause licenses.
#
# This file is part of EasyBuild,
# originally created by the HPC team of Ghent University (http://ugent.be/hpc/en),
# with support of Ghent University (http://ugent.be/hpc),
# the Flemish Supercomputer Centre (VSC) (https://vscentrum.be/nl/en),
# the Hercules foundation (http://www.herculesstichting.be/in_English)
# and the Department of Economy, Science and Innovation (EWI) (http://www.ewi-vlaanderen.be/en).
#
# http://github.com/hpcugent/easybuild
#
# EasyBuild is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation v2.
#
# EasyBuild is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with EasyBuild.  If not, see <http://www.gnu.org/licenses/>.
##
"""
Support for building and installing Clang, implemented as an easyblock.

@author: Dmitri Gribenko (National Technical University of Ukraine "KPI")
"""

import os
import shutil

from easybuild.easyblocks.generic.cmakemake import CMakeMake
from easybuild.tools.filetools import run_cmd, mkdir

class EB_Clang(CMakeMake):
    """
    Support for bootstrapping Clang.
    """

    def __init__(self, *args, **kwargs):
        """Initialize custom class variables for Clang."""

        super(EB_Clang, self).__init__(*args, **kwargs)
        self.llvm_src_dir = None
        self.llvm_obj_dir_stage1 = None
        self.llvm_obj_dir_stage2 = None
        self.llvm_obj_dir_stage3 = None

    def extract_step(self):
        super(EB_Clang, self).extract_step()
        for tmp in self.src:
            if tmp['name'].startswith("llvm-"):
                self.llvm_src_dir = tmp['finalpath']
                break

        if self.llvm_src_dir is None:
            self.log.error("Could not determine LLVM source root (LLVM source was not unpacked?)")

        # Move other directories into the LLVM tree.
        for tmp in self.src:
            if tmp['name'].startswith("clang-"):
                old_path = os.path.join(tmp['finalpath'], 'clang-%s.src' % self.version)
                new_path = os.path.join(self.llvm_src_dir, 'tools', 'clang')
                shutil.move(old_path, new_path)
                tmp['finalpath'] = new_path
                continue
            if tmp['name'].startswith("compiler-rt-"):
                old_path = os.path.join(tmp['finalpath'], 'compiler-rt-%s.src' % self.version)
                new_path = os.path.join(self.llvm_src_dir, 'projects', 'compiler-rt')
                shutil.move(old_path, new_path)
                tmp['finalpath'] = new_path
                continue

    def configure_step(self):
        # Stage 1: configure.
        self.llvm_obj_dir_stage1 = os.path.join(self.builddir, 'llvm.obj.1')
        self.llvm_obj_dir_stage2 = os.path.join(self.builddir, 'llvm.obj.2')
        self.llvm_obj_dir_stage3 = os.path.join(self.builddir, 'llvm.obj.3')
        mkdir(self.llvm_obj_dir_stage1)
        os.chdir(self.llvm_obj_dir_stage1)
        self.cfg['configopts'] += "-DCMAKE_BUILD_TYPE=Release -DLLVM_ENABLE_ASSERTIONS=ON "
        self.cfg['configopts'] += "-DLLVM_TARGETS_TO_BUILD=X86"
        super(EB_Clang, self).configure_step(self.llvm_src_dir)

    def build_with_prev_stage(self, prev_obj, next_obj):
        # Create and enter build directory.
        mkdir(next_obj)
        os.chdir(next_obj)

        # Configure.
        CC = os.path.join(prev_obj, 'bin', 'clang')
        CXX = os.path.join(prev_obj, 'bin', 'clang++')

        options = "-DCMAKE_INSTALL_PREFIX=%s " % self.installdir
        options += "-DCMAKE_C_COMPILER='%s' " % CC
        options += "-DCMAKE_CXX_COMPILER='%s' " % CXX
        options += self.cfg['configopts']

        self.log.info("Configuring")
        run_cmd("cmake %s %s" % (options, self.llvm_src_dir), log_all=True, simple=False)

        paracmd = ""
        if self.cfg['parallel']:
            paracmd = "-j %s" % self.cfg['parallel']

        self.log.info("Building")
        run_cmd("make %s" % paracmd, log_all=True, simple=False)

        self.log.info("Running tests")
        run_cmd("make %s check-all" % paracmd, log_all=True, simple=False)

    def build_step(self):
        # Stage 1: build using system compiler.
        os.chdir(self.llvm_obj_dir_stage1)
        super(EB_Clang, self).build_step()

        # Stage 1: run tests.
        paracmd = ""
        if self.cfg['parallel']:
            paracmd = "-j %s" % self.cfg['parallel']

        run_cmd("make %s check-all" % paracmd, log_all=True, simple=False)

        self.log.info("Building stage 2")
        self.build_with_prev_stage(self.llvm_obj_dir_stage1, self.llvm_obj_dir_stage2)

        self.log.info("Building stage 3")
        self.build_with_prev_stage(self.llvm_obj_dir_stage2, self.llvm_obj_dir_stage3)

    def test_step(self):
        pass

    def install_step(self):
        # Install stage 3 binaries.
        os.chdir(self.llvm_obj_dir_stage3)
        super(EB_Clang, self).install_step()

