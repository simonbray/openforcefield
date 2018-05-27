# TODO: Eliminate OpenEye dependencies from forcefield tests

# TODO: Split this file into many test files, potentially distributing tests within each subpackage next to the classes they test

import os
import tempfile
import unittest
from functools import partial
from io import StringIO
from tempfile import TemporaryDirectory

import numpy as np
from numpy.testing import assert_equal

import parmed

from openforcefield.typing.engines.smirnoff import *

from openforcefield.utils import get_testdata_filename, generateTopologyFromOEMol, read_molecules
from openforcefield.utils import check_energy_is_finite, get_energy

from simtk import unit, openmm
from simtk.openmm import app

#=============================================================================================
# CONSTANTS
#=============================================================================================

# These paths should only be found in the test data directories, so we need to use get_testdata_filename()
AlkEthOH_offxml_filename = get_testdata_filename('forcefield/Frosst_AlkEthOH.offxml')
AlkEthOH_molecules_filename = get_testdata_filename('molecules/AlkEthOH-tripos.mol2.gz')
MiniDrugBank_molecules_filename = get_testdata_filename('molecules/MiniDrugBank_tripos.mol2.gz')
chargeincrement_offxml_filename = get_testdata_filename('chargeincrement-test.offxml')
tip3p_molecule_filename = get_testdata_filename(os.path.join('systems', 'monomers', 'tip3p_water.mol2'))

# This is the production form of smirnoff99Frosst that should be found in the data directories
smirnoff99Frosst_offxml_filename = 'smirnoff99Frosst.offxml'
tip3p_offxml_filename = 'tip3p.offxml'

# TODO: Add tests to compare RDKit and OpenEye derived forcefields to make sure they are the same

# TODO: Move forcefields for testing only to a special test data directory, separate from the data/ paths that are automatically searched and populated with production force fields
#
# SMIRNOFF ForceField XML definitions for testing purposes
#

# This is a test forcefield that is not meant for actual use.
# It just tests various capabilities.
ffxml_standard = u"""\
<!-- Header block (optional) -->
<Date>Date: May-September 2016</Date>
<Author>C. I. Bayly, OpenEye Scientific Software and David Mobley, UCI</Author>

<Bonds potential="harmonic" length_unit="angstroms" k_unit="kilocalories_per_mole/angstrom**2">
   <Bond smirks="[#6X4:1]-[#6X4:2]" length="1.526" k="620.0" id="b0001" parent_id="b0001"/> <!-- CT-CT from frcmod.Frosst_AlkEthOH -->
   <Bond smirks="[#6X4:1]-[#1:2]" length="1.090" k="680.0" id="b0002" parent_id="b0002"/> <!-- CT-H_ from frcmod.Frosst_AlkEthOH -->
   <Bond smirks="[#8:1]~[#1:2]" length="1.410" k="640.0" id="b0003" parent_id="b0003"/> <!-- DEBUG O-H -->
   <Bond smirks="[#6X4:1]-[O&amp;X2&amp;H1:2]" length="1.410" k="640.0" id="b0004" parent_id="b0004"/> <!-- CT-OH from frcmod.Frosst_AlkEthOH -->
   <Bond smirks="[#6X4:1]-[O&amp;X2&amp;H0:2]" length="1.370" k="640.0" id="b0005" parent_id="b0005"/> <!--CT-OS from frcmod.Frosst_AlkEthOH -->
   <Bond smirks="[#8X2:1]-[#1:2]" length="0.960" k="1106.0" id="b0006" parent_id="b0003"/> <!-- OH-HO from frcmod.Frosst_AlkEthOH -->
    <Bond smirks="[#6X3:1]!#[#6X3:2]" id="b5" parent_id="b5" k_bondorder1="820.0" k_bondorder2="1098" length_bondorder1="1.45" length_bondorder2="1.35"/> <!-- Christopher Bayly from parm99, Aug 2016 -->
   <Bond smirks="[#6X3:1]-[#1:2]" id="b27" parent_id="b27" k="734.0" length="1.080"/> <!-- Christopher Bayly from par99, Aug 2016 -->
</Bonds>

<Angles potential="harmonic" angle_unit="degrees" k_unit="kilocalories_per_mole/radian**2">
   <Angle smirks="[a,A:1]-[#6X4:2]-[a,A:3]" angle="109.50" k="100.0" id="a0001" parent_id="a0001"/> <!-- consensus matches all X-Csp3-X -->
   <Angle smirks="[*:1]~[#8:2]~[*:3]" angle="113." k="100.0" id="a0001b" parent_id="a0001"/> <!-- consensus matches all X-O-X, such as in water -->
   <Angle smirks="[#1:1]-[#6X4:2]-[#1:3]" angle="109.50" k="70.0" id="a0002" parent_id="a0001"/> <!-- H1-CT-H1 from frcmod.Frosst_AlkEthOH -->
   <Angle smirks="[#6X4:1]-[#6X4:2]-[#6X4:3]" angle="109.50" k="80.0" id="a0003" parent_id="a0001"/> <!-- CT-CT-CT from frcmod.Frosst_AlkEthOH -->
   <Angle smirks="[#8X2:1]-[#6X4:2]-[#8X2:3]" angle="109.50" k="140.0" id="a0004" parent_id="a0001"/> <!-- O_-CT-O_ from frcmod.Frosst_AlkEthOH -->
   <Angle smirks="[#6X4:1]-[#8X2:2]-[#1:3]" angle="108.50" k="110.0" id="a0005" parent_id="a0005"/> <!-- CT-OH-HO from frcmod.Frosst_AlkEthOH -->
   <Angle smirks="[#6X4:1]-[#8X2:2]-[#6X4:3]" angle="109.50" k="120.0" id="a0006" parent_id="a0006"/> <!-- CT-OS-CT from frcmod.Frosst_AlkEthOH -->
   <Angle smirks="[*:1]~[#6X3:2]~[*:3]" angle="120." id="a10" parent_id="a10" k="140.0"/> <!-- Christopher Bayly from parm99, Aug 2016 -->
   <Angle smirks="[#1:1]-[#6X3:2]~[*:3]" angle="120." id="a11" parent_id="a11" k="100.0"/> <!-- Christopher Bayly from parm99, Aug 2016 -->
   <Angle smirks="[#1:1]-[#6X3:2]-[#1:3]" angle="120." id="a12" parent_id="a12" k="70.0"/> <!-- Christopher Bayly from parm99, Aug 2016 -->
</Angles>

<ProperTorsions potential="charmm" phase_unit="degrees" k_unit="kilocalories_per_mole">
   <Proper smirks="[a,A:1]-[#6X4:2]-[#6X4:3]-[a,A:4]" idivf1="9" periodicity1="3" phase1="0.0" k1="1.40" id="t0001" parent_id="t0001"/> <!-- X -CT-CT-X from frcmod.Frosst_AlkEthOH -->
   <Proper smirks="[a,A:1]-[#6X4:2]-[#8X2:3]-[#1:4]" idivf1="3" periodicity1="3" phase1="0.0" k1="0.50" id="t0002" parent_id="t0002"/> <!--X -CT-OH-X from frcmod.Frosst_AlkEthOH -->
   <Proper smirks="[a,A:1]-[#6X4:2]-[#8X2:3]-[!#1:4]" idivf1="3" periodicity1="3" phase1="0.0" k1="1.15" id="t0003" parent_id="t0003"/> <!-- X -CT-OS-X from frcmod.Frosst_AlkEthOH -->
   <Proper smirks="[#1:1]-[#6X4:2]-[#6X4:3]-[#1:4]" idivf1="1" periodicity1="3" phase1="0.0" k1="0.15" id="t0004" parent_id="t0001"/> <!-- HC-CT-CT-HC from frcmod.Frosst_AlkEthOH; note discrepancy with parm@frosst which applies this ONLY to HC-CT-CT-HC and other hydrogens get the generic X -CT-CT-X -->
   <Proper smirks="[#1:1]-[#6X4:2]-[#6X4:3]-[#6X4:4]" idivf1="1" periodicity1="3" phase1="0.0" k1="0.16" id="t0005" parent_id="t0001"/> <!-- HC-CT-CT-CT from frcmod.Frosst_AlkEthOH -->
   <Proper smirks="[#6X4:1]-[#6X4:2]-[#8X2:3]-[#1:4]" idivf1='1' periodicity1="3" phase1="0.0" k1="0.16" idivf2="1" periodicity2="1" phase2="0.0" k2="0.25" id="t0006" parent_id="t0002"/> <!-- HO-OH-CT-CT from frcmod.Frosst_AlkEthOH -->
   <Proper smirks="[#6X4:1]-[#6X4:2]-[#6X4:3]-[#6X4:4]" idivf1="1" periodicity1="3" phase1="0.0" k1="0.18" idivf2="1" periodicity2="2" phase2="180.0" k2="0.25" idivf3="1" periodicity3="1" phase3="180.0" k3="0.20" id="t0007" parent_id="t0001"/> <!-- CT-CT-CT-CT from frcmod.Frosst_AlkEthOH -->
   <Proper smirks="[#6X4:1]-[#6X4:2]-[#8X2:3]-[#6X4:4]" idivf1="1" periodicity1="3" phase1="0.0" k1="0.383" idivf2="1" periodicity2="2" phase2="180.0" k2="0.1" id="t0008" parent_id="t0003"/> <!-- CT-CT-OS-CT from frcmod.Frosst_AlkEthOH -->
   <Proper smirks="[#6X4:1]-[#8X2:2]-[#6X4:3]-[O&amp;X2&amp;H0:4]" idivf1="1" periodicity1="3" phase1="0.0" k1="0.10" idivf2="1" periodicity2="2" phase2="180.0" k2="0.85" idivf3="1" periodicity3="1" phase3="180.0" k3="1.35" id="t0009" parent_id="t0003"/> <!-- CT-OS-CT-OS from frcmod.Frosst_AlkEthOH -->
   <Proper smirks="[#8X2:1]-[#6X4:2]-[#6X4:3]-[#8X2:4]" idivf1="1" periodicity1="3" phase1="0.0" k1="0.144" idivf2="1" periodicity2="2" phase2="0.0" k2="1.175" id="t0010" parent_id="t0001"/> <!-- O_-CT-CT-O_ from frcmod.Frosst_AlkEthOH -->
   <Proper smirks="[#8X2:1]-[#6X4:2]-[#6X4:3]-[#1:4]" idivf1="1" periodicity1="3" phase1="0.0" k1="0.0" idivf2="1" periodicity2="1" phase2="0.0" k2="0.25" id="t0011" parent_id="t0001"/> <!-- H_-CT-CT-O_ from frcmod.Frosst_AlkEthOH; discrepancy with parm@frosst with H2,H3-CT-CT-O_ per C Bayly -->
   <Proper smirks="[#1:1]-[#6X4:2]-[#6X4:3]-[OX2:4]" idivf1="1" periodicity1="3" phase1="0.0" k1="0.0" idivf2="1" periodicity2="1" phase2="0.0" k2="0.25" id="t0012" parent_id="t0001"/> <!-- HC,H1-CT-CT-OH,OS from frcmod.Frosst_AlkEthOH ; note corresponding H2 and H3 params missing so they presumably get generic parameters (another parm@frosst bug) -->
   <Proper smirks="[*:1]~[#6X3:2]-[#6X4:3]~[*:4]" id="t13" idivf1="1" k1="0.000" periodicity1="3" phase1="0.0"/> <!-- parm99 generic, Bayly, Aug 2016 -->
   <Proper smirks="[#1:1]-[#6X4:2]-[#6X3:3]=[#6X3:4]" id="t15" parent_id="t15" idivf1="1" k1="0.380" periodicity1="3" phase1="180.0" phase2="0.0" k2="1.150" periodicity2="1" idivf2="1"/> <!-- parm99, Bayly, Aug 2016 -->
   <Proper smirks="[*:1]~[#6X3:2]-[#6X3:3]~[*:4]" id="t18" parent_id="t18" idivf1="1" k1="1." periodicity1="2" phase1="180.0"/> <!-- parm99 generic, Bayly, Aug 2016 -->
   <Proper smirks="[*:1]~[#6X3:2]:[#6X3:3]~[*:4]" id="t20" parent_id="t20" idivf1="1" k1="3.625" periodicity1="2" phase1="180.0"/> <!-- parm99 generic, Bayly, Aug 2016 -->
   <Proper smirks="[*:1]-[#6X3:2]=[#6X3:3]-[*:4]" id="t21" parent_id="t21" idivf1="1" k1="6." periodicity1="2" phase1="180.0"/> <!-- parm99 generic, Bayly, Aug 2016 -->
</ProperTorsions>

<ImproperTorsions potential="charmm" phase_unit="degrees" k_unit="kilocalories_per_mole">
   <Improper smirks="[a,A:1]~[#6X3:2]([a,A:3])~[OX1:4]" periodicity1="2" phase1="180.0" k1="10.5" id="i0001" parent_id="i0001"/> <!-- X -X -C -O  from frcmod.Frosst_AlkEthOH; none in set but here as format placeholder -->
</ProperTorsions>

<vdW potential="Lennard-Jones-12-6" combining_rules="Loentz-Berthelot" scale12="0.0" scale13="0.0" scale14="0.5" scale15="1" sigma_unit="angstroms" epsilon_unit="kilocalories_per_mole" switch="8.0" cutoff="9.0" long_range_dispersion="isotropic">
   <!-- sigma is in angstroms, epsilon is in kcal/mol -->
   <Atom smirks="[#1:1]" rmin_half="1.4870" epsilon="0.0157" id="n0001" parent_id="n0001"/> <!-- making HC the generic hydrogen -->
   <Atom smirks="[$([#1]-C):1]" rmin_half="1.4870" epsilon="0.0157" id="n0002" parent_id="n0001"/> <!-- HC from frcmod.Frosst_AlkEthOH -->
   <Atom smirks="[$([#1]-C-[#7,#8,F,#16,Cl,Br]):1]" rmin_half="1.3870" epsilon="0.0157" id="n0003" parent_id="n0002"/> <!-- H1 from frcmod.Frosst_AlkEthOH -->
   <Atom smirks="[$([#1]-C(-[#7,#8,F,#16,Cl,Br])-[#7,#8,F,#16,Cl,Br]):1]" rmin_half="1.2870" epsilon="0.0157" id="n0004" parent_id="n0003"/> <!--H2 from frcmod.Frosst_AlkEthOH -->
   <Atom smirks="[$([#1]-C(-[#7,#8,F,#16,Cl,Br])(-[#7,#8,F,#16,Cl,Br])-[#7,#8,F,#16,Cl,Br]):1]" rmin_half="1.1870" epsilon="0.0157" id="n0005" parent_id="n0004"/> <!--H3 from frcmod.Frosst_AlkEthOH -->
   <Atom smirks="[#1$(*-[#8]):1]" rmin_half="0.0000" epsilon="0.0000" id="n0006" parent_id="n0001"/> <!-- HO from frcmod.Frosst_AlkEthOH -->
   <Atom smirks="[#6:1]" rmin_half="1.9080" epsilon="0.1094" id="n0007" parent_id="n0007"/> <!-- making CT the generic carbon -->
   <Atom smirks="[#6X4:1]" rmin_half="1.9080" epsilon="0.1094" id="n0008" parent_id="n0007"/> <!-- CT from frcmod.Frosst_AlkEthOH-->
   <Atom smirks="[#8:1]" rmin_half="1.6837" epsilon="0.1700" id="n0009" parent_id="n0009"/> <!-- making OS the generic oxygen -->
   <Atom smirks="[#8X2:1]" rmin_half="1.6837" epsilon="0.1700" id="n0010" parent_id="n0009"/> <!-- OS from frcmod.Frosst_AlkEthOH -->
   <Atom smirks="[#8X2+0$(*-[#1]):1]" rmin_half="1.7210" epsilon="0.2104" id="n0011" parent_id="n0009"/> <!-- OH from frcmod.Frosst_AlkEthOH -->
</vdW>
"""

ffxml_chargeincrement = u"""\
  <ChargeIncrementModel number_of_conformers="10" quantum_chemical_method="AM1" partial_charge_method="CM2" increment_unit="elementary_charge">
    <!-- A fractional charge can be moved along a single bond -->
    <ChargeIncrement smirks="[#6X4:1]-[#6X3a:2]" charge1increment="-0.0073" charge2increment="+0.0073"/>
    <ChargeIncrement smirks="[#6X4:1]-[#6X3a:2]-[#7]" charge1increment="+0.0943" charge2increment="-0.0943"/>
    <ChargeIncrement smirks="[#6X4:1]-[#8:2]" charge1increment="-0.0718" charge2increment="+0.0718"/>
    <!--- Alternatively, factional charges can be redistributed among any number of bonded atoms -->
  <ChargeIncrement smirks="[N:1](H:2)(H:3)" charge1increment="+0.02" charge2increment="-0.01" charge3increment="-0.01"/>
</ChargeIncrementModel>
"""

ffxml_constraints = u"""\
<Constraints distance_unit="angstroms">
  <!-- constrain all bonds to hydrogen to their equilibrium bond length -->
  <Constraint smirks="[#1:1]-[*:2]" id="constraint0001"/>
</Constraints>
"""

ffxml_gbsa = u"""\
<GBSA gb_model="OBC1" solvent_dielectric="78.5" solute_dielectric="1" radius_units="nanometers" sa_model="ACE" surface_area_penalty="5.4*calories/mole/angstroms**2" solvent_radius="1.4*angstroms">
  <Atom smirks="[#1:1]" radius="0.12" scale="0.85" id="gb0001"/>
  <Atom smirks="[#6:1]" radius="0.22" scale="0.72" id="gb0002"/>
  <Atom smirks="[#7:1]" radius="0.155" scale="0.79" id="gb0003"/>
  <Atom smirks="[#8:1]" radius="0.15" scale="0.85" id="gb0004"/>
  <Atom smirks="[#9:1]" radius="0.15" scale="0.88" id="gb0005"/>
  <Atom smirks="[#14:1]" radius="0.21" scale="0.8" id="gb0006"/>
  <Atom smirks="[#15:1]" radius="0.185" scale="0.86" id="gb0007"/>
  <Atom smirks="[#16:1]" radius="0.18" scale="0.96" id="gb0008"/>
  <Atom smirks="[#17:1]" radius="0.17" scale="0.8" id="gb0009"/>
</GBSA>
"""

ffxml_contents_gbsa = u"""\
<?xml version="1.0"?>

<SMIRNOFF use_fractional_bondorder="True">

%(ffxml_standard)s
%(ffxml_constraints)s
%(ffxml_gbsa)s

</SMIRNOFF>
""" % globals()

ffxml_contents_chargeincrement = u"""\
<?xml version="1.0"?>

%(ffxml_standard)s
%(ffxml_constraints)s
%(ffxml_chargeincrement)s

</SMIRNOFF>
""" % globals()

ffxml_contents_noconstraints = u"""\
<?xml version="1.0"?>

<SMIRNOFF use_fractional_bondorder="True">

%(ffxml_standard)s

</SMIRNOFF>
""" % globals()

ffxml_contents = u"""\
<?xml version="1.0"?>

<SMIRNOFF use_fractional_bondorder="True">

%(ffxml_standard)s
%(ffxml_constraints)s

</SMIRNOFF>
""" % globals()

# Set up another, super minimal FF to test that alternate aromaticity
# models implemented properly
ffxml_MDL_contents = u"""\
<?xml version="1.0"?>

<SMIRNOFF version="0.1" aromaticity_model="OEAroModel_MDL">

!-- SMIRKS (SMIRKS Force Field) minimal file, not intended for use -->
  <Date>Date: Sept. 7, 2016</Date>
  <Author>D. L. Mobley, UC Irvine</Author>
  <Bonds potential="harmonic" length_unit="angstroms" k_unit="kilocalories_per_mole/angstrom**2">
    <Bond smirks="[*:1]~[*:2]" id="b1" k="2000.0" length="4.0"/>
    <Bond smirks="[#6X3:1]-[#8X2:2]" id="b16" k="960.0" length="1.240"/>
  </Bonds>
  <Angles potential="harmonic" angle_unit="degrees" k_unit="kilocalories_per_mole/radian**2">
    <Angle smirks="[*:1]~[*:2]~[*:3]" angle="109.5" id="a1" k="160.0"/>
  </Angles>
  <ProperTorsions potential="charmm" phase_unit="degrees" k_unit="kilocalories_per_mole">
    <Proper smirks="[*:1]~[*:2]~[*:3]~[*:4]" id="t1" idivf1="4" k1="3.50" periodicity1="2" phase1="180.0"/>
  </ProperTorsions>
  <ImproperTorsions potential="charmm" phase_unit="degrees" k_unit="kilocalories_per_mole">
    <Improper smirks="[a,A:1]~[#6X3:2]([a,A:3])~[OX1:4]" periodicity1="2" phase1="180.0" k1="10.5" id="i0001" parent_id="i0001"/> <!-- X -X -C -O  from frcmod.Frosst_AlkEthOH; none in set but here as format placeholder -->
  </ImproperTorsions>
  <vdW potential="Lennard-Jones-12-6" combining_rules="Loentz-Berthelot" scale12="0.0" scale13="0.0" scale14="0.5" scale15="1" sigma_unit="angstroms" epsilon_unit="kilocalories_per_mole" switch="8.0" cutoff="9.0" long_range_dispersion="isotropic">
    <Atom smirks="[*:1]" epsilon="0.2100" id="n1" rmin_half="1.6612"/>
    <Atom smirks="[#1:1]" epsilon="0.0157" id="n2" rmin_half="0.6000"/>
  </vdW>

</SMIRNOFF>
"""

#
# Test various components
#

class TestParameterList(unittest.TestCase):
    """Test capabilities of ParameterList for accessing and manipulating SMIRNOFF parameter definitions.
    """

    def test_create(self):
        """Test creation of a parameter list.
        """
        p1 = ParameterType(smirks='[*:1]')
        p2 = ParameterType(smirks='[#1:1]')
        parameters = ParameterList([p1, p2])

    def test_getitem(self):
        """Test ParameterList __getitem__ overloading.
        """
        p1 = ParameterType(smirks='[*:1]')
        p2 = ParameterType(smirks='[#1:1]')
        parameters = ParameterList([p1, p2])
        assert parameters[0] == p1
        assert parameters[1] == p2
        assert parameters[p1.smirks] == p1
        assert parameters[p2.smirks] == p2

    def test_setitem(self):
        """Test ParameterList __setitem__ overloading.
        """
        p1 = ParameterType(smirks='[*:1]')
        p2 = ParameterType(smirks='[#1:1]')
        p3 = ParameterType(smirks='[#7:1]')
        parameters = ParameterList([p1, p2, p3])
        parameters[0].smirks = '[*X4:1]'
        assert p1.smirks == '[*X4:1]'
        parameters['[*X4:1]'].smirks = '[*:1]'
        assert p1.smirks == '[*:1]'

    def test_contains(self):
        """Test ParameterList __contains__ overloading.
        """
        p1 = ParameterType(smirks='[*:1]')
        p2 = ParameterType(smirks='[#1:1]')
        p3 = ParameterType(smirks='[#7:1]')
        parameters = ParameterList([p1, p2])
        assert p1 in parameters
        assert p2 in parameters
        assert p3 not in parameters
        assert p1.smirks in parameters
        assert p2.smirks in parameters
        assert p3.smirks not in parameters

    def test_del(self):
        """Test ParameterList __del__ overloading.
        """
        p1 = ParameterType(smirks='[*:1]')
        p2 = ParameterType(smirks='[#1:1]')
        p3 = ParameterType(smirks='[#7:1]')
        parameters = ParameterList([p1, p2, p3])
        del parameters[2]
        assert len(parameters) == 2
        assert p1 in parameters
        assert p2 in parameters
        assert p3 not in parameters
        del parameters['[#1:1]']
        assert p1 in parameters
        assert p2 not in parameters

class TestForceField(unittest.TestCase):
    """Test capabilities of ForceField and its Python API.
    """

    # TODO: Can we refine `forcefield.get_handler()` and `hander.add_parameter()` interface?

    def create_forcefield_via_api(self):
        """Create a minimal ForceField via the API and test object data model is correctly populated.
        """
        # Create a ForceField
        forcefield = ForceField(version='1.0', aromaticity_model="MDL")
        # Add bonds
        handler = forcefield.get_handler('Bonds', potential="harmonic") # TODO: I don't like this API for adding parameter blocks; can we do better?
        length_unit = unit.angstroms
        k_unit = unit.kilocalories_per_mole/unit.angstrom
        handler.add_parameter(smirks="[#6X4:1]-[#6X4:2]", length=1.526*length_unit, k=620.0*k_unit) # TODO: Should the API automagically handle the case where parameters are provided as strings?
        handler.add_parameter(smirks="[#6X4:1]-[#1:2]", length=1.090*length_unit, k=680.0*k_unit)
        assert_equal(forcefield.forces['Bonds'].parameters[0].length, 1.526*length_unit)
        assert_equal(forcefield.forces['Bonds'].parameters[1].k, 680.0*length_unit)
        assert_equal(forcefield.forces['Bonds'].parameters["[#6X4:1]-[#1:2]"].length, 1.090*length_unit)
        # Add angles
        handler = forcefield.get_handler('Angles', potential="harmonic")
        angle_unit = unit.degrees
        k_unit = unit.kilocalories_per_mole/unit.radian**2
        handler.add_parameter(smirks="[a,A:1]-[#6X4:2]-[a,A:3]", angle=109.50*angle_unit, k=100.0*k_unit)
        handler.add_parameter(smirks="[#1:1]-[#6X4:2]-[#1:3]", angle=109.50*angle_unit, k=70.0*k_unit)
        assert_equal(forcefield.forces['Angles'].parameters[0].angle, 109.50*angle_unit)
        assert_equal(forcefield.forces['Angles'].parameters[0].k, 100.0*k_unit)
        # Add proper torsions
        handler = forcefield.get_handler('ProperTorsions', potential="charmm")
        phase_unit = unit.degrees
        k_unit = unit.kilocalories_per_mole
        handler.add_parameter(smirks="[a,A:1]-[#6X4:2]-[#6X4:3]-[a,A:4]", idivf1=9, periodicity1=3, phase1=0.0*phase_unit, k1=1.40*k_unit)
        handler.add_parameter(smirks="[#6X4:1]-[#6X4:2]-[#8X2:3]-[#6X4:4]", idivf1=1, periodicity1=3, phase1=0.0*phase_unit, k1=0.383*k_unit, idivf2=1, periodicity2=2, phase2=180.0*phase_unit, k2=0.1*k_unit)
        assert hasattr(forcefield.forces['ProperTorsions'].parameters[0], 'k1')
        assert not hasattr(forcefield.forces['ProperTorsions'].parameters[0], 'k2')
        assert hasattr(forcefield.forces['ProperTorsions'].parameters[1], 'k1')
        assert hasattr(forcefield.forces['ProperTorsions'].parameters[2], 'k2')
        assert_equal(forcefield.forces['ProperTorsions'].parameters["[#6X4:1]-[#6X4:2]-[#8X2:3]-[#6X4:4]"].idivf1, 1)
        assert_equal(forcefield.forces['ProperTorsions'].parameters["[#6X4:1]-[#6X4:2]-[#8X2:3]-[#6X4:4]"].periodicity1, 3)
        assert_equal(forcefield.forces['ProperTorsions'].parameters["[#6X4:1]-[#6X4:2]-[#8X2:3]-[#6X4:4]"].phase1, 0.0*phase_unit)
        assert_equal(forcefield.forces['ProperTorsions'].parameters["[#6X4:1]-[#6X4:2]-[#8X2:3]-[#6X4:4]"].k1, 0.383*k_unit)
        assert_equal(forcefield.forces['ProperTorsions'].parameters["[#6X4:1]-[#6X4:2]-[#8X2:3]-[#6X4:4]"].idivf2, 1)
        assert_equal(forcefield.forces['ProperTorsions'].parameters["[#6X4:1]-[#6X4:2]-[#8X2:3]-[#6X4:4]"].periodicity2, 2)
        assert_equal(forcefield.forces['ProperTorsions'].parameters["[#6X4:1]-[#6X4:2]-[#8X2:3]-[#6X4:4]"].phase2, 180.0*phase_unit)
        assert_equal(forcefield.forces['ProperTorsions'].parameters["[#6X4:1]-[#6X4:2]-[#8X2:3]-[#6X4:4]"].k3, 0.1*k_unit)
        # Add improper torsions
        handler = forcefield.get_handler('ImproperTorsions', potential="charmm", default_idivf="auto")
        phase_unit = unit.degrees
        k_unit = unit.kilocalories_per_mole
        handler.add_parameter(smirks="[*:1]~[#6X3:2](=[#7X2,#7X3+1:3])~[#7:4]", k1=10.5*k_unit, periodicity1=2, phase1=180.0*phase_unit)
        assert_equal(forcefield.forces['ImproperTorsions'].parameters[0].k1, 10.5*k_unit)
        assert_equal(forcefield.forces['ImproperTorsions'].parameters[0].periodicity1, 2)
        assert_equal(forcefield.forces['ImproperTorsions'].parameters[0].phase1, 180.0*phase_unit)
        # Add vdW
        handler = forcefield.get_handler('vdW', potential="Lennard-Jones-12-6", combining_rules="Loentz-Berthelot", switch=8.0*unit.angstroms, cutoff=9.0*unit.angstroms, long_range_dispersion="isotropic")
        sigma_unit = unit.angstroms
        epsilon_unit = unit.kilocalories_per_mole
        handler.add_parameter(smirks="[#1:1]", sigma=1.4870*sigma_unit, epsilon=0.0157*epsilon_unit)
        handler.add_parameter(smirks="[#1:1]-[#6]", sigma=1.4870*sigma_unit, epsilon=0.0157*epsilon_unit)
        assert_equal(forcefield.forces['vdW'].parameters[0].sigma, 1.4870*sigma_unit)
        assert_equal(forcefield.forces['vdW'].parameters[0].epsilon, 0.0157*epsilon_unit)
        # Add ChargeIncrementModel
        handler = forcefield.get_handler('ChargeIncrementModel', number_of_conformers=10, quantum_chemical_method="AM1", partial_charge_method="CM2")
        charge_unit = unit.elementary_charge
        handler.add_parameter(smirks="[#6X4:1]-[#6X3a:2]", charge1increment=-0.0073*charge_unit, charge2increment=+0.0073*charge_unit)
        handler.add_parameter(smirks="[N:1](H:2)(H:3)", charge1increment=+0.02*charge_unit, charge2increment=-0.01*charge_unit, charge3increment=-0.01*charge_unit)
        assert_equal(forcefield.forces['ChargeIncrementModel'].parameters[0].smirks, "[#6X4:1]-[#6X3a:2]")
        assert_equal(forcefield.forces['ChargeIncrementModel'].parameters["[N:1](H:2)(H:3)"].charge1increment, +0.02*charge_unit)
        # Add LibraryCharges
        handler = forcefield.get_handler('LibraryCharges')
        charge_unit = unit.elementary_charge
        handler.add_parameter(name="TIP3P", smirks="[#1:1]-[#8X2H2+0:2]-[#1:3]", charge1=+0.417*charge_unit, charge2=-0.834*charge_unit, charge3=+0.417*charge_unit)
        assert_equal(forcefield.forces['LibraryCharges'].parameters[0].name, 'TIP3P')
        assert_equal(forcefield.forces['LibraryCharges'].parameters[0].charge1, +0.417*charge_unit)
        assert_equal(forcefield.forces['LibraryCharges'].parameters[0].charge2, -0.834*charge_unit)
        assert_equal(forcefield.forces['LibraryCharges'].parameters[0].charge3, +0.417*charge_unit)
        assert not hasattr(forcefield.forces['LibraryCharges'].parameters[0], 'charge4')

        return forcefield

    def test_create(self):
        """Test creating a ForceFied via the Python API.
        """
        forcefield = create_forcefield_via_api()

    def test_modify(self):
        """Test modifying a ForceField via the Python API.
        """
        forcefield = create_forcefield_via_api()
        # Modify some parameters
        forcefield.forces['Bonds'].parameters[0].k *= 1.1
        forcefield.forces['Bonds'].parameters[1].length += 0.01 * unit.nanometers
        forcefield.forces['Bonds'].parameters["#6X4:1]-[#1:2]"].smirks += "~[#7]"
        assert "#6X4:1]-[#1:2]" not in forcefield.forces['Bonds'].parameters
        assert "#6X4:1]-[#1:2]~[#7]" in forcefield.forces['Bonds'].parameters

    def test_delete_parameters(self):
        forcefield = create_forcefield_via_api()
        # Delete some parameters
        forcefield.forces['Bonds'].parameters[0].k *= 1.1
        forcefield.forces['Bonds'].parameters[1].length += 0.01 * unit.nanometers
        forcefield.forces['Bonds'].parameters["#6X4:1]-[#1:2]"].smirks += "~[#7]"
        assert "#6X4:1]-[#1:2]" not in forcefield.forces['Bonds'].parameters
        assert "#6X4:1]-[#1:2]~[#7]" in forcefield.forces['Bonds'].parameters


class TestXMLForceField(unittest.TestCase):
    """Test capabilities of the XML reader/writer for ForceField.
    """

    def test_attached_units():
        from openforcefield.typing.engines.smirnoff.io import _extract_attached_units, _attach_units
        # Test extraction of units
        force_attrib = OrderedDict([
            ('potential', "Lennard-Jones-12-6"),
            ('combining_rules', "Loentz-Berthelot"),
            ('scale12', "0.0"), ('scale13', "0.0"), ('scale14', "0.5"),
            ('sigma_unit', "angstroms"), ('epsilon_unit', "kilocalories_per_mole"),
            ('switch', "8.0*angstroms"), ('cutoff', "9.0*angstroms"),
            ('long_range_dispersion', "isotropic"),
            ])
        stripped_attrib, attached_units = _extract_attached_units(force_attrib)
        assert_equal(list(stripped_attrib.keys()), ['potential', 'combining_rules', 'scale12', 'scale13', 'scale14', 'switch', 'cutoff', 'long_range_dispersion'])
        assert_equal(list(stripped_attrib.values()), ["Lennard-Jones-12-6", "Loentz-Berthelot", "0.0", "0.0", "0.5", "8.0*angstroms", "9.0*angstroms", "isotropic"])
        assert_equal(list(attached_units.keys()), ['sigma', 'epsilon'])
        assert_equal(list(attached_units.values()), [unit.angstroms, unit.kilocalories_per_mole])
        # Test attachment of units
        parameter_attrib = OrderedDict([
            ('smirks', "[#1:1]"),
            ('sigma', "1.4870"),
            ('epsilon', "0.0157"),
        ])
        unit_bearing_attrib = _attach_units(parameter_attrib, attached_units)
        assert_equal(list(unit_bearing_attrib.keys()), ['smirks', 'sigma', 'epsilon'])
        assert_equal(list(unit_bearing_attrib.values()), ["[#1:1]", 1.4870*unit.angstroms, 0.0157*unit.kilocalories_per_mole])

    #
    # Tests for ForceField construction from XML files (.offxml)
    #

    def test_create_from_offxml():
        """Test creation of aa SMIRNOFF ForceField object from offxml files.
        """
        # These offxml files are located in package data path, which is automatically installed and searched
        filenames = [smirnoff99Frosst_offxml_filename, tip3p_offxml_filename]
        # Create a forcefield from a single offxml
        forcefield = ForceField(filenames[0])
        # Create a forcefield from multiple offxml files
        forcefield = ForceField(filenames)
        # A generator should work as well
        forcefield = ForceField(iter(filenames))

    def test_create_from_url():
        """Test creation of a SMIRNOFF ForceField object from URLs
        """
        urls = [
            'https://raw.githubusercontent.com/openforcefield/openforcefield/master/openforcefield/data/forcefield/smirnoff99Frosst.offxml',
            'https://raw.githubusercontent.com/openforcefield/openforcefield/master/openforcefield/data/forcefield/tip3p.offxml'
            ]
        # Test creation with smirnoff99frosst URL
        forcefield = ForceField(urls[0])
        # Test creation with multiple URLs
        forcefield = ForceField(urls)
        # A generator should work as well
        forcefield = ForceField(iter(urls))

    def test_create_from_strings():
        """Test creation of a SMIRNOFF ForceField object from strings
        """
        # Test creation with one string
        forcefield = ForceField(ffxml_contents)
        # Test creation with list of strings
        forcefield = ForceField([ffxml_standard, ffxml_constraints])
        # Test creation with concatenated XML files
        forcefield = ForceField(ffxml_standard + ffxml_constraints)
        # Test creation from other combinations
        forcefield = ForceField(ffxml_contents_gbsa)
        forcefield = ForceField(ffxml_contents_chargeincrement)
        forcefield = ForceField(ffxml_contents_noconstraints)

    def test_create_gbsa():
        """Test reading of ffxml files with GBSA support.
        """
        gbsa_offxml_filename = get_testdata_filename('Frosst_AlkEthOH_GBSA.offxml')
        forcefield = ForceField(gbsa_offxml_filename)

    #
    # Tests for ForceField writing to XML files
    #

    def test_save(self):
        """Test writing and reading of SMIRNOFF in XML format.
        """
        forcefield = ForceField(smirnoff99Frosst_offxml_filename)
        # Write XML to a file
        with TemporaryDirectory() as tmpdir:
            offxml_tmpfile = os.path.join(tmpdir, 'forcefield.offxml')
            forcefield.save(offxml_tmpfile)
            forcefield2 = ForceField(offxml_tmpfile)
            assert_forcefields_equal(cls.forcefield, forcefield2, "ForceField written to .offxml does not match original ForceField")

    def test_to_xml(self):
        forcefield = ForceField(smirnoff99Frosst_offxml_filename)
        # Retrieve XML as a string
        xml = forcefield.to_xml()
        # Restore ForceField from XML
        forcefield2 = ForceField(xml)
        assert_forcefields_equal(cls.forcefield, forcefield2, "ForceField serialized to XML does not match original ForceField")

    def test_deep_copy(self):
        forcefield = ForceField(smirnoff99Frosst_offxml_filename)
        # Deep copy
        forcefield2 = copy.deepcopy(cls.forcefield)
        assert_forcefields_equal(cls.forcefield, forcefield2, "ForceField deep copy does not match original ForceField")

    def test_serialize(self):
        forcefield = ForceField(smirnoff99Frosst_offxml_filename)
        # Serialize/deserialize
        serialized_forcefield = cls.forcefield.__getstate__()
        forcefield2 = ForceField.__setstate__(serialized_forcefield)
        assert_forcefields_equal(cls.forcefield, forcefield2, "Deserialized serialized ForceField does not match original ForceField")

class TestApplyForceField(unittest.TestCase):
    """Test the use of ForceField to parameterize Topology objects.
    """

    def check_system_creation_from_molecule(self, forcefield, molecule):
        """
        Generate a System from the given OEMol and SMIRNOFF forcefield and check that its energy is finite.

        Parameters
        ----------
        forcefield : openforcefield.typing.engines.smirnoff.ForceField
            SMIRNOFF forcefield object
        molecule : openforcefield.topology.Molecule
            Molecule to test (which must have coordinates)

        """
        topology = Topology.from_molecules(molecule)
        system = forcefield.create_system(topology)
        check_energy_is_finite(system, molecule.positions)

    def check_system_creation_from_topology(forcefield, topology, positions):
        """
        Generate a System from the given topology, OEMols matching the contents of the topology, and SMIRNOFF forcefield and check that its energy is finite.

        Parameters
        ----------
        forcefield : ForceField
            SMIRNOFF forcefield
        topology : openforcefield.topology.Topology
            Topology for which System should be constructed
        positions : simtk.unit.Quantity with dimension (natoms,3) with units of length
            Positions of all particles

        """
        system = forcefield.create_system(topology)
        check_energy_is_finite(system, positions)

    def check_parameter_assignment(self, offxml_filename=smirnoff99Frosst_offxml_filename, molecules_filename=AlkEthOH_molecules_filename):
        """Test parameter assignment using specified forcefield on all molecules from specified source.

        Parameters
        ----------
        offxml_filename : str, optional, default='smirnoff99Frosst.offxml'
            Filename from which SMIRNOFF .offxml XML file is to be loaded.
        molecules_filename : str, optional, default='molecules/AlkEthOH-tripos.mol2.gz
            Filename from which molecule identities and positions are to be loaded.
        """
        forcefield = ForceField(offxml_filename)
        for molecule in openforcefield.topology.Molecule.from_file(molecules_filename):
            f = partial(check_system_creation_from_molecule, forcefield, molecule)
            f.description ='Testing {} parameter assignment using molecule {}'.format(offxml_filename, molecule.name)
            yield f

    def test_AlkEthOH_smirnoff99Frosst(self):
        """Test parameter assignment using smirnoff99Frosst on AlkEthOH.
        """
        check_parameter_assignment(offxml_filename=smirnoff99Frosst_offxml_filename, molecules_filename=AlkEthOH_molecules_filename)

    def test_MiniDrugBank_smirnoff99Frosst(self):
        """Test parameter assignment using smirnoff99Frosst on MiniDrugBank.
        """
        check_parameter_assignment(offxml_filename=smirnoff99Frosst_offxml_filename, molecules_filename=MiniDrugBank_molecules_filename)

    def test_electrostatics_options(self):
        """Test parameter assignment using smirnoff99Frosst on laromustine with various long-range electrostatics options.
        """
        molecules_filename = get_testdata_filename('molecules/laromustine_tripos.mol2')
        molecule = openforcefield.topology.Molecule.from_file(molecules_filename)
        forcefield = ForceField([smirnoff99Frosst_offxml_filename, chargeincrement_offxml_filename])
        for method in ['PME', 'reaction-field', 'Coulomb']:
            # Change electrostatics method
            forcefield.forces['Electrostatics'].method = method
            f = partial(check_system_creation_from_molecule, forcefield, molecule)
            f.description ='Testing {} parameter assignment using molecule {}'.format(offxml_filename, molecule.name)
            yield f

    def test_chargeincrement(self):
        """Test parameter assignment using smirnoff99Frosst on laromustine with ChargeIncrementModel.
        """
        molecules_filename = get_testdata_filename('molecules/laromustine_tripos.mol2')
        molecule = openforcefield.topology.Molecule.from_file(molecules_filename)
        forcefield = ForceField(['smirnoff99Frosst.offxml', 'chargeincrement-test'])
        check_system_creation_from_molecule(forcefield, molecule)

    def test_create_system_molecules_parmatfrosst_gbsa(self):
        """Test creation of a System object from small molecules to test parm@frosst forcefield with GBSA support.
        """
        molecules_filename = get_testdata_filename('molecules/AlkEthOH-tripos.mol2.gz')
        check_parameter_assignment(offxml_filename='Frosst_AlkEthOH_GBSA.offxml', molecules_filename=molecules_filename)

    def test_mixed_solvent_boxes(self):
        """Test creation of System from boxes of mixed solvents.
        """
        forcefield = ForceField('smirnoff99frosst.offxml')
        # Read unique molecules represented in these systems
        monomers = ['water', 'cyclohexane', 'ethanol', 'propane', 'methane', 'butanol']
        filenames = [ get_testdata_filename(os.path.join('systems', 'monomers', monomer + '.sdf')) for monomer in monomers ]
        unique_molecules = [ openforcefield.topology.Molecule.from_file(filename) for filename in filenames ]
        if verbose: print('%d reference molecules loaded' % len(molecules))

        # Create Topology objects for systems
        boxes = ['ethanol_water.pdb',  'cyclohexane_water.pdb',
            'cyclohexane_ethanol_0.4_0.6.pdb', 'propane_methane_butanol_0.2_0.3_0.5.pdb']
        from simtk.openmm.app import PDBFile
        for box in boxes:
            filename = get_testdata_filename(os.path.join('systems', 'packmol_boxes', box))
            pdbfile = PDBFile(filename)
            topology = Topology.from_openmm_topology(pdbfile.topology, unique_molecules)
            f = partial(check_system_creation_from_topology, forcefield, topology, pdbfile.positions)
            f.description = 'Test application of smirnoff99Frosst parameters to %s' % (box)
            yield f

class TestForceFieldEnergies(unittest.TestCase):
    """Compare SMIRNOFF energies with AMBER.
    """

    def compare_system_energies(self, topology0, topology1, system0, system1, positions0, positions1=None, label0="AMBER system", label1="SMIRNOFF system", verbose=True, skip_assert=False, skip_improper=False):
        """
        Given two OpenMM systems, check that their energies and component-wise
        energies are consistent, and return these. The same positions will be used
        for both systems unless a second set of positions is provided.

        Parameters
        ----------
        topology0 : OpenMM Topology
            Topology of first system
        topology1 : OpenMM Topology
            Topology of second system
        system0 : OpenMM System
            First system for comparison (usually from AMBER)
        system1 : OpenMM System
            Second system for comparison (usually from SMIRNOFF)
        positions0 : simtk.unit.Quantity wrapped
            Positions to use for energy evaluation comparison
        positions1 (optional) : simtk.unit.Quantity wrapped (optional)
            Positions to use for second OpenMM system; original positions are used
            if this is not provided
        label0 (optional) : str
            String labeling system0 for output. Default, "AMBER system"
        label1 (optional) : str
            String labeling system1 for output. Default, "SMIRNOFF system"
        verbose (optional) : bool
            Print out info on energies, True/False (default True)
        skip_assert (optional) : bool
            Skip assertion that energies must be equal within specified tolerance. Default False.
        skip_improper (optional) : bool
            Skip detailed checking of force terms on impropers (helpful here if comparing with AMBER force fields using different definitions of impropers.) Default False.

        Returns
        ----------
            groups0 : dict
                As returned by openmoltools.system_checker.check_energy_groups,
                a dictionary with keys "bond", "angle", "nb", "torsion" and values
                corresponding to the energies of these components for the first simulation object
            groups1 : dict
                As returned by openmoltools.system_checker.check_energy_groups,
                a dictionary with keys "bond", "angle", "nb", "torsion" and values
                corresponding to the energies of these components for the second simulation object
            energy0 : simtk.unit.Quantity
                Energy of first system
            energy1 : simtk.unit.Quantity
                Energy of second system

        TO DO:
            Allow energy extraction/comparison of terms specified by particular
            SMARTS queries i.e. for specific bond, angle, or torsional terms.
        """

        # Create integrator
        timestep = 1.0 * unit.femtoseconds
        integrator0 = simtk.openmm.VerletIntegrator( timestep )
        integrator1 = simtk.openmm.VerletIntegrator( timestep )

        # Grab second positions
        if positions1 == None:
            positions1 = copy.deepcopy( positions0 )

        # Create simulations
        platform = simtk.openmm.Platform.getPlatformByName("Reference")

        simulation0 = app.Simulation( topology0, system0, integrator0, platform = platform )
        simulation0.context.setPositions(positions0)
        simulation1 = app.Simulation( topology1, system1, integrator1, platform = platform )
        simulation1.context.setPositions(positions1)

        # Print what torsions were found if verbose
        if verbose:
            # Build list of atoms for debugging info
            atoms0 = [ atom for atom in simulation0.topology.atoms() ]
            atoms1 = [ atom for atom in simulation1.topology.atoms() ]
            # Loop over first system and print torsion info
            for force in simulation0.system.getForces():
                if type(force) == mm.PeriodicTorsionForce:
                    print("Num (type) \t Num (type) \t Num (type) \t Num (type) \t per \t phase \t k0")
                    for k in range(force.getNumTorsions()):
                        i0, i1, i2, i3, per, phase, k0 = force.getTorsionParameters(k)
                        print("%3s (%3s)- %3s (%3s)- \t %s (%3s)- \t %3s (%3s)- \t %f \t %f \t %f " % (i0, atoms0[i0].name, i1, atoms0[i1].name, i2, atoms0[i2].name, i3, atoms0[i3].name, per, phase/unit.degree, k0/unit.kilojoule_per_mole) )
            for force in simulation1.system.getForces():
                if type(force) == mm.PeriodicTorsionForce:
                    print("Num (type) \t Num (type) \t Num (type) \t Num (type) \t per \t phase \t k0")
                    for k in range(force.getNumTorsions()):
                        i0, i1, i2, i3, per, phase, k0 = force.getTorsionParameters(k)
                        print("%3s (%3s)- %3s (%3s)- %3s (%3s)- %3s (%3s) - %f \t %f \t %f " % (i0, atoms1[i0].name, i1, atoms1[i1].name, i2, atoms1[i2].name, i3, atoms1[i3].name, per, phase/unit.degree, k0/unit.kilojoule_per_mole) )

        # Do energy comparison, print info if desired
        syscheck = system_checker.SystemChecker( simulation0, simulation1 )
        if not skip_assert:
            # Only check force terms if we want to make sure energies are identical
            syscheck.check_force_parameters(skipImpropers = skip_improper)
        groups0, groups1 = syscheck.check_energy_groups(skip_assert = skip_assert)
        energy0, energy1 = syscheck.check_energies(skip_assert = skip_assert)
        if verbose:
            print("Energy of %s: " % label0, energy0 )
            print("Energy of %s: " % label1, energy1 )
            print("\nComponents of %s:" % label0 )
            for key in groups0.keys():
                print("%s: " % key, groups0[key] )
            print("\nComponents of %s:" % label1 )
            for key in groups1.keys():
                print("%s: " % key, groups1[key] )

        # Return
        return groups0, groups1, energy0, energy1

    def test_smirnoff_energies_vs_parmatfrosst(self):
        """Test evaluation of energies from parm@frosst ffxml files versus energies of equivalent systems.
        """
        prefix = 'AlkEthOH_'
        molecule_names = [ 'r118', 'r12', 'c1161', 'r0', 'c100', 'c38', 'c1266' ]

        # Load special parm@frosst with parm99/parm@frosst bugs re-added for testing
        forcefield = ForceField( get_testdata_filename('forcefield/Frosst_AlkEthOH_parmAtFrosst.offxml') )

        # Loop over molecules, load OEMols and prep for comparison/do comparison
        for molecule_name in molecule_names:
            filename_prefix = os.path.join('molecules', prefix + molecule_name )

            # Create OpenMM System from AMBER prmtop/inpcrd
            prmtop = app.AmberPrmtopFile(get_testdata_filename( filename_prefix+'.top'))
            inpcrd = app.AmberInpcrdFile(get_testdata_filename( filename_prefix+'.crd'))
            openmm_topology = prmtop.topology
            amber_system = prmtop.createSystem(nonbondedMethod=app.NoCutoff, constraints=None, implicitSolvent=None)
            positions = inpcrd.getPositions()

            # Create openforcefield Topology
            unique_molecules = Molecule.from_file(get_testdata_filename( filename_prefix+'.mol2'))
            openforcefield_topology = Topology.from_openmm(prmtop.topology, unique_molecules)
            smirnoff_system = forcefield.create_system(openforcefield_topology)

            # Compare energies
            compare_system_energies(openmm_topology, openmm_topology, amber_system, smirnoff_system, positions, verbose=True, skip_assert=False, skip_improper=False)

    def test_partial_bondorder(verbose = False):
        """Test energies of a molecule which activates partial bond order code."""
        # Create benzene molecule
        molecule = Molecule.from_iupac('benzene')
        topology = molecule.to_topology()

        # Load forcefield
        ff = ForceField(ffxml_contents_noconstraints)

        # Set up once using AM1BCC charges
        # TODO: Use OECharges_AM1BCCSym charges
        system = ff.create_system(topology)

        # Check that energy is what it ought to be -- the partial bond order
        # for benzene makes the energy a bit higher than it would be without it
        energy = get_energy(system, positions)
        if energy < 7.50 or energy > 7.60:
            raise Exception("Partial bond order code seems to have issues, as energy for benzene is outside of tolerance in tests.")

        # Set up once also without asking for charges
        # TODO: Don't create charges
        system = ff.create_system(topology)
        energy = get_energy(system, positions)
        # Energy is lower with user supplied charges (which in this case are zero)
        if energy < 4.00 or energy > 6.0:
            raise Exception("Partial bond order code seems to have issues when run with user-provided charges, as energy for benzene is out of tolerance in tests.")

    def test_improper(verbose = False):
        """Test implement of impropers on benzene."""
        # Create benzene molecule
        molecule = Molecule.from_iupac('benzene')
        topology = molecule.to_topology()

        # Load forcefield
        ff = ForceField(get_testdata_filename('forcefield/benzene_minimal.offxml'))

        # Load AMBER files and compare
        inpcrd = get_testdata_filename('molecules/benzene.crd')
        prmtop = get_testdata_filename('molecules/benzene.top')
        g0, g1, e0, e1 = compare_molecule_energies(prmtop, inpcrd, ff, mol, skip_assert=True)

        # Check that torsional energies the same to 1 in 10^6
        rel_error = np.abs((g0['torsion']-g1['torsion'])/ g0['torsion'])
        if rel_error > 6e-3: #Note that this will not be tiny because we use three-fold impropers and they use a single improper
            raise Exception("Improper torsion energy for benzene differs too much (relative error %.4g) between AMBER and SMIRNOFF." % rel_error )

class TestForceFieldLabeling(unittest.TestCase):
    """Tests for labeling parameter types in molecules
    """
    def test_label_molecules(self):
        """Test labeling/getting stats on labeling molecules"""
        molecules = read_molecules(get_testdata_filename('molecules/AlkEthOH-tripos.mol2.gz'), verbose=verbose)
        ffxml = get_testdata_filename('forcefield/Frosst_AlkEthOH.offxml')
        get_molecule_parameterIDs(molecules, ffxml)

    def test_molecule_labeling(self):
        """Test using labelMolecules to see which parameters applied to a molecule
        """
        from openforcefield.topology.testsystems import SMILESTopology
        topology = SMILESTopology('CCC')
        forcefield = ForceField(get_testdata_filename('forcefield/Frosst_AlkEthOH.offxml'))
        labels = forcefield.label_molecules(topology)[0]

        # Check that force terms aren't empty
        for forcename in ['Bonds', 'Angles', 'ProperTorsions', 'ImproperTorsions', 'vdW', 'Electrostatics']:
            if not forcename in labels:
                raise Exception("No force term assigned for {}.".format(forcename))

class TestExceptionHandling(unittest.TestCase):
    """Tests for exception handling for incomplete parameterization
    """
    def test_parameter_completeness_check(self):
        """Test that proper exceptions are raised if a force field fails to assign parameters to valence terms in a molecule.
        """
        from openforcefield.topology.testsystems import SMILESTopology
        topology = SMILESTopology('CCC')

        offxml_filename = get_testdata_filename('forcefield/Frosst_AlkEthOH.offxml')

        # Test vdW error checking by wiping out required parameter
        parameter_edits = [
            ('vdW', '[#136:1]'),
            ('Bonds', '[#136:1]~[*:2]'),
            ('Angles', '[#136:1]~[*:2]~[*:3]'),
            ('ProperTorsions', '[#136:1]~[*:2]~[*:3]~[*:4]'),
            ]
        for (tag, smirks) in parameter_edits:
            forcefield = ForceField(offxml_filename)
            forcefield.forces[tag].parameters[0].smirks = smirks
            with self.assertRaises(Exception):
                system = forcefield.create_system(topology)

#
# TODO: Finish updating the tests below this line
#

# TODO: Is there any way to make this test not depend on OpenEye?
@requires_openeye_licenses
def test_improper_pyramidal(verbose = False):
    """Test implement of impropers on ammonia."""
    from openeye import oeomega
    from openeye import oequacpac
    from oeommtools.utils import oemol_to_openmmTop, openmmTop_to_oemol
    from openforcefield.utils import get_testdata_filename, extractPositionsFromOEMol
    # Prepare ammonia
    mol = oechem.OEMol()
    oechem.OESmilesToMol(mol, 'N')
    oechem.OEAddExplicitHydrogens(mol)
    omega = oeomega.OEOmega()
    omega.SetMaxConfs(100)
    omega.SetIncludeInput(False)
    omega.SetStrictStereo(False)
    # Generate charges
    chargeEngine = oequacpac.OEAM1BCCCharges()
    status = omega(mol)
    oequacpac.OEAssignCharges(mol, chargeEngine)
    # Assign atom names
    oechem.OETriposAtomTypes(mol)
    oechem.OETriposAtomNames(mol)
    # Set up minimization
    ff = ForceField(get_testdata_filename('forcefield/ammonia_minimal.offxml'))
    topology, positions = oemol_to_openmmTop(mol)
    system = ff.createSystem(topology, [mol], verbose=verbose)
    positions = extractPositionsFromOEMol(mol)
    integrator = openmm.VerletIntegrator(2.0*unit.femtoseconds)
    simulation = app.Simulation(topology, system, integrator)
    simulation.context.setPositions(positions)
    # Minimize energy
    simulation.minimizeEnergy()
    state = simulation.context.getState(getEnergy=True, getPositions=True)
    energy = state.getPotentialEnergy() / unit.kilocalories_per_mole
    newpositions = state.getPositions()
    outmol = openmmTop_to_oemol(topology, state.getPositions())
    # Sum angles around the N atom
    for atom in outmol.GetAtoms(oechem.OEIsInvertibleNitrogen()):
        aidx = atom.GetIdx()
        nbors = list(atom.GetAtoms())
        ang1 = math.degrees(oechem.OEGetAngle(outmol, nbors[0],atom,nbors[1]))
        ang2 = math.degrees(oechem.OEGetAngle(outmol, nbors[1],atom,nbors[2]))
        ang3 = math.degrees(oechem.OEGetAngle(outmol, nbors[2],atom,nbors[0]))
    ang_sum = math.fsum([ang1,ang2,ang3])
    # Check that sum of angles around N is within 1 degree of 353.5
    if abs(ang_sum-353.5) > 1.0:
        raise Exception("Improper torsion for ammonia differs too much from reference partly pyramidal geometry."
        "The reference case has a sum of H-N-H angles (3x) at 353.5 degrees; the test case has a sum of {}.".format(ang_sum))

def test_MDL_aromaticity(verbose=False):
    """Test support for alternate aromaticity models."""
    ffxml = StringIO(ffxml_MDL_contents)
    ff = ForceField(ffxml)
    from openeye import oechem
    mol = oechem.OEMol()
    oechem.OEParseSmiles(mol, 'c12c(cccc1)occ2')
    oechem.OEAddExplicitHydrogens(mol)

    labels=ff.labelMolecules( [mol], verbose = True)
    # The bond 6-7 should get the b16 parameter iff the MDL model is working, otherwise it will pick up just the generic
    details = labels[0]['HarmonicBondGenerator']
    found = False
    for (atom_indices, pid, smirks) in details:
        if pid == 'b16' and atom_indices==[6,7]:
            found = True
    if not found: raise Exception("Didn't find right param.")

def test_change_parameters(verbose=False):
    """Test modification of forcefield parameters."""
    from openeye import oechem
    # Load simple OEMol
    ifs = oechem.oemolistream(get_testdata_filename('molecules/AlkEthOH_c100.mol2'))
    mol = oechem.OEMol()
    flavor = oechem.OEIFlavor_Generic_Default | oechem.OEIFlavor_MOL2_Default | oechem.OEIFlavor_MOL2_Forcefield
    ifs.SetFlavor( oechem.OEFormat_MOL2, flavor)
    oechem.OEReadMolecule(ifs, mol )
    oechem.OETriposAtomNames(mol)

    # Load forcefield file
    ffxml = get_testdata_filename('forcefield/Frosst_AlkEthOH.offxml')
    ff = ForceField(ffxml)

    topology = generateTopologyFromOEMol(mol)
    # Create initial system
    system = ff.createSystem(topology, [mol], verbose=verbose)
    # Get initial energy before parameter modification
    positions = positions_from_oemol(mol)
    old_energy = get_energy(system, positions)

    # Get params for an angle
    params = ff.getParameter(smirks='[a,A:1]-[#6X4:2]-[a,A:3]')
    # Modify params
    params['k']='0.0'
    ff.setParameter(params, smirks='[a,A:1]-[#6X4:2]-[a,A:3]')
    # Write params
    ff.writeFile( tempfile.TemporaryFile(suffix='.offxml') )
    # Make sure params changed energy! (Test whether they get rebuilt on system creation)
    system=ff.createSystem(topology, [mol], verbose=verbose)
    energy=get_energy(system, positions)
    if verbose:
        print("New energy/old energy:", energy, old_energy)
    if np.abs(energy-old_energy)<0.1:
        raise Exception("Error: Parameter modification did not change energy.")

class TestForceFieldExport(unittest.TestCase):
    """Test the ability to export ForceField-parameterized systems to other major simulation packages.
    """

    @staticmethod
    def get_mixture_tesystem(packmol_boxname, monomers):
        """Retrieve test system information for specified packmol mixed-component box and monomers.

        Parameters
        ----------
        packmol_boxname : str
            Prefix of PDB file to be retrieved from systems/packmolboxes in test data directory
        monomers : list of str
            List of monomer names within packmol box

        Returns
        -------
        topology : openforcefield.topology.Topology
            Topology for the packmol box
        positions : simtk.unit.Quantity with dimension (nparticles,3) with units compatible with angstroms
            Positions corresponding to particles in ``topology``
        """
        pdb_filename = get_testdata_filename(os.path.join('systems', 'packmol_boxes', packmol_boxname + '.pdb'))
        pdbfile = app.PDBFile(pdb_filename)

        mol2_filenames = [ get_testdata_filename(os.path.join('systems', 'monomers', monomer + '.mol2')) for monomer in monomers ]
        molecules = Molecule.from_file(mol2_filenames)

        topology = Topology.from_openmm(pdbfile.topology, unique_molecules=molecules)
        positions = pdbfile.positions

        return topology, positions

    def test_amber_roundtrip(self):
        """Save a System (a mixture) to AMBER, read back in, verify yields same energy and force terms."""
        forcefield = ForceField(AlkEthOH_offxml_filename)
        topology, positions = get_mixture_testsystem('cyclohexane_ethanol_0.4_0.6', ['ethanol', 'cyclohexane'])
        system = forcefield.create_system(pdbfile.topology, mols)
        openmm_topology = topology.to_openmm()

        # TODO: Can we provide a way to more directly export to AMBER?
        from openforcefield.utils import save_system_to_amber
        with TemporaryDirectory() as tmpdir:
            # Write AMBER prmtop, inpcrd
            prmtop_filename = os.path.join(tmpdir, 'output.prmtop')
            inpcrd_filename = os.path.join(tmpdir, 'output.inpcrd')
            save_system_to_amber(openmm_topology, system, positions, prmtop_filename, inpcrd_filename)

            # Read back in and cross-check energies
            structure = parmed.load_file(prmtop, inpcrd) # TODO: Is this a structure or prmtop object in ParmEd?
            # TODO: Make sure the SMIRNOFF systems is also created with no cutoff, no constraints, and no implicit solvent
            amber_system = structure.createSystem(nonbondedMethod=app.NoCutoff, constraints=None, implicitSolvent=None)
            groups0, groups1, energy0, energy1 = compare_system_energies(openmm_topology, openmm_topology, amber_system, system, positions, verbose=False)

    def test_gromacs_roundtrip(self):
        """Save a System (a mixture) to gromacs, read back in, verify yields same energy and force terms."""
        forcefield = ForceField(AlkEthOH_offxml_filename)
        topology, positions = get_mixture_testsystem('cyclohexane_ethanol_0.4_0.6', ['ethanol', 'cyclohexane'])
        system = forcefield.create_system(pdbfile.topology, mols)
        openmm_topology = topology.to_openmm()

        # TODO: Can we provide a way to more directly export to gromacs?
        from openforcefield.utils import save_system_to_amber
        with TemporaryDirectory() as tmpdir:
            # Write gromacs .gro and .top files
            gro_filename = os.path.join(tmpdir, 'output.gro')
            top_filename = os.path.join(tmpdir, 'output.top')
            save_system_to_gromacs(openmm_topology, system, positions, top_filename, gro_filename)

            # Read back in and cross-check energies
            top = parmed.load_file(top_filename)
            gro = parmed.load_file(gro_filename)
            # TODO: Make sure the SMIRNOFF systems is also created with no cutoff, no constraints, and no implicit solvent
            gromacs_system = top.createSystem(nonbondedMethod=app.NoCutoff, constraints=None, implicitSolvent=None)
            groups0, groups1, energy0, energy1 = compare_system_energies(openmm_topology, openmm_topology, gromacs_system, system, positions, verbose=False)

class TestSolventSupport(unittest.TestCase):
    """Test support for rigid solvents like TIP3P.
    """
    def test_tip3p_constraints(self):
        """Test that TIP3P distance costraints are correctly applied."""
        # Specify TIP3P constraint distances
        tip3p_oh_distance = 0.9572  # angstrom
        tip3p_hoh_angle = 104.52  # angle
        tip3p_hh_distance = tip3p_oh_distance * np.sin(np.radians(tip3p_hoh_angle/2)) * 2
        expected_distances = [tip3p_oh_distance, tip3p_oh_distance, tip3p_hh_distance]

        # Load TIP3P molecule
        molecule = Molecule.from_file(tip3p_molecule_filename)

        # Extract topology and positions
        topology = Topology.from_molecules(molecule)
        positions = molecule.positions

        # Create OpenMM System
        ff = ForceField(tip3p_offxml_filename)
        system = ff.create_system(topology)

        # Run dynamics.
        integrator = openmm.VerletIntegrator(2.0*unit.femtoseconds)
        context = openmm.Context(system, integrator)
        context.setPositions(positions)
        integrator.step(50)

        # Ensure constrained distances are correct
        state = context.getState(getPositions=True)
        new_positions = state.getPositions(asNumpy=True) / unit.angstroms
        distances = []
        for atom_1, atom_2 in [(0, 1), (0, 2), (1, 2)]:  # pair of atoms O-H1, O-H2, H1-H2
            distances.append(np.linalg.norm(new_positions[atom_1] - new_positions[atom_2]))
        err_msg = 'expected distances [O-H1, O-H2, H1-H2]: {} A, new distances: {} A'
        assert np.allclose(expected_distances, distances), err_msg.format(expected_distances, distances)

    def test_tip3p_solvated_molecule_energy():
        """Check the energy of a TIP3P solvated molecule is the same with SMIRNOFF and OpenMM.

        This test makes also use of defining the force field with multiple FFXML files,
        and test the energy of mixture systems (i.e. molecule plus water).

        """
        # TODO remove this function when ParmEd#868 is fixed
        def add_water_bonds(system):
            """Hack to make tip3p waters work with ParmEd Structure.createSystem.

            Bond parameters need to be specified even when constrained.
            """
            k_tip3p = 462750.4*unit.kilojoule_per_mole/unit.nanometers**2
            length_tip3p = 0.09572*unit.nanometers
            for force in system.getForces():
                if isinstance(force, openmm.HarmonicBondForce):
                    force.addBond(particle1=0, particle2=1, length=length_tip3p, k=k_tip3p)
                    force.addBond(particle1=0, particle2=2, length=length_tip3p, k=k_tip3p)

        monomers_dir = get_testdata_filename(os.path.join('systems', 'monomers'))

        # Load TIP3P molecule
        tip3p_molecule = Molecule.from_file(tip3p_molecule_filename)
        tip3p_positions = tip3p_molecule.positions

        # Extract topology and positions
        top3p_topology = Topology.from_molecules(molecule)

        # Create OpenMM System
        tip3p_forcefield = ForceField(tip3p_offxml_filename)
        tip3p_openmm_system = tip3p_forcefield.create_system(tip3p_topology)

        # TODO remove this line when ParmEd#868 is fixed
        # Hack to make tip3p waters work with ParmEd Structure.createSystem.
        add_water_bonds(tip3p_openmm_system)

        tip3p_openmm_structure = parmed.openmm.topsystem.load_topology(
            topology.to_openmm(), tip3p_openmm_system, tip3p_positions)

        smirnoff_forcefield = ForceField(smirnoff99Frosst_offxml_filename)

        for monomer in ['ethanol', 'methane']:
            # Load molecule
            other_molecule_filepath = os.path.join(monomers_dir, monomer + '.mol2')
            other_molecule = Molecule.from_file(other_molecule_filepath)

            # Create ParmEd Structure
            other_molecule_structure = smirnoff_forcefield.create_structure(other_molecule.to_topology(), other_molecule.positions)

            # Merge molecule and OpenMM TIP3P water
            combined_structure = tip3p_openmm_structure + other_molecule_structure
            #structure.positions = np.append(tip3p_molecule.positions, molecule.positions, axis=0) # TODO: This doesn't seem necessary since positions are correctly concatenated already
            system = combined_structure.createSystem()
            energy_openmm = get_energy(system, combined_structure.positions)

            # Test the creation of system with multiple force field files.
            ff = ForceField(smirnoff_offxml_filename, tip3p_offxml_filename)
            combined_topology = Topology.from_molecules([tip3p_molecule, molecule])
            system = ff.create_system(topology)

            # TODO remove this line when ParmEd#868 is fixed
            # Add bonds to match ParmEd hack above.
            add_water_bonds(system)

            energy_smirnoff = get_energy(system, structure.positions)

            # The energies of the systems must be the same.
            assert np.isclose(energy_openmm, energy_smirnoff), 'OpenMM: {}, SMIRNOFF: {}'.format(
                energy_openmm, energy_smirnoff)

def test_component_combination():
    """Test that a system still yields the same energy after building it again out of its components."""

    # We've had issues where subsequent instances of a molecule might have zero charges
    # Here we'll try to catch this (and also explicitly check the charges) by re-building
    # a system out of its components

    forcefield = ForceField(get_testdata_filename('forcefield/Frosst_AlkEthOH.offxml'))
    filename = get_testdata_filename(os.path.join('systems', 'packmol_boxes', 'cyclohexane_ethanol_0.4_0.6.pdb'))
    from simtk.openmm.app import PDBFile
    pdbfile = PDBFile(filename)
    mol2files = [get_testdata_filename(os.path.join('systems', 'monomers', 'ethanol.mol2')), get_testdata_filename(os.path.join('systems', 'monomers', 'cyclohexane.mol2'))]

    flavor = oechem.OEIFlavor_Generic_Default | oechem.OEIFlavor_MOL2_Default | oechem.OEIFlavor_MOL2_Forcefield
    mols = []
    mol = oechem.OEMol()
    for mol2file in mol2files:
        ifs = oechem.oemolistream(mol2file)
        ifs.SetFlavor( oechem.OEFormat_MOL2, flavor)
        mol = oechem.OEGraphMol()
        while oechem.OEReadMolecule(ifs, mol):
            oechem.OETriposAtomNames(mol)
            mols.append(oechem.OEGraphMol(mol))

    # setup system
    system = forcefield.createSystem( pdbfile.topology, mols, chargeMethod = 'OECharges_AM1BCCSym')

    # Make parmed structure
    structure = parmed.openmm.topsystem.load_topology( pdbfile.topology, system, pdbfile.positions)

    # Split the system, then re-compose it out of its components
    tmp = structure.split()
    strs, nums = [], []
    for s, n in tmp:
        strs.append(s)
        nums.append(n)
    nums = [ len(n) for n in nums]

    # Re-compose system from components
    new_structure = strs[0]*nums[0]
    for idx in range(1,len(nums)):
        new_structure += strs[idx]*nums[idx]
    # Swap in coordinates again
    new_structure.positions = structure.positions

    # Create System
    newsys = new_structure.createSystem(nonbondedMethod= app.NoCutoff, constraints = None, implicitSolvent = None)

    # Cross check energies
    groups0, groups1, energy0, energy1 = compare_system_energies( pdbfile.topology, pdbfile.topology, system, newsys, pdbfile.positions, verbose = False)

    # Also check that that the number of components is equal to the number I expect
    if not len(nums)==2:
        print("Error: Test system has incorrect number of components.")
        raise Exception('Incorrect number of components in cyclohexane/ethanol test system.')

    # Also check that none of residues have zero charge
    for resnr in range(len(structure.residues)):
        abscharges = [ abs(structure.residues[resnr].atoms[idx].charge) for idx in range(len(structure.residues[resnr].atoms))]
        if sum(abscharges)==0:
            raise Exception('Error: Residue %s in cyclohexane-ethanol test system has a charge of zero, which is incorrect.' % resnr)

def test_merge_system():
    """Test merging of a system created from AMBER and another created from SMIRNOFF."""

    #Create System from AMBER
    prefix = os.path.join('systems', 'amber', 'cyclohexane_ethanol_0.4_0.6')
    prmtop = get_testdata_filename( prefix+'.prmtop')
    incrd = get_testdata_filename( prefix+'.inpcrd')

    from openforcefield.typing.engines.smirnoff import create_system_from_amber
    topology0, system0, positions0 = create_system_from_amber( prmtop, incrd )

    from openeye import oechem
    # Load simple OEMol
    ifs = oechem.oemolistream(get_testdata_filename('molecules/AlkEthOH_c100.mol2'))
    mol = oechem.OEMol()
    flavor = oechem.OEIFlavor_Generic_Default | oechem.OEIFlavor_MOL2_Default | oechem.OEIFlavor_MOL2_Forcefield
    ifs.SetFlavor( oechem.OEFormat_MOL2, flavor)
    oechem.OEReadMolecule(ifs, mol)
    oechem.OETriposAtomNames(mol)

    # Load forcefield file
    forcefield = ForceField(AlkEthOH_offxml_filename)
    topology1, system1, positions1 = create_system_from_molecule(forcefield, mol)

    merge_system( topology0, topology1, system0, system1, positions0, positions1, verbose=True )



if __name__ == '__main__':
    #test_smirks()
    test_merge_system()
