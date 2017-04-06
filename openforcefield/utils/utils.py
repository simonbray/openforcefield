#!/usr/bin/env python

"""
Utility subroutines for open forcefield tools

"""
#=============================================================================================
# GLOBAL IMPORTS
#=============================================================================================

import sys
import string

from optparse import OptionParser # For parsing of command line arguments

import os
import math
import copy
import re
import numpy
import random

import openeye.oechem
import openeye.oeomega
import openeye.oequacpac

from openeye.oechem import *
from openeye.oeomega import *
from openeye.oequacpac import *

from simtk.openmm import app
from simtk.openmm.app import element as elem
from simtk.openmm.app import Topology

import time
from simtk import unit

#=============================================================================================
# UTILITY ROUTINES
#=============================================================================================

def generateTopologyFromOEMol(molecule):
    """
    Generate an OpenMM Topology object from an OEMol molecule.

    Parameters
    ----------
    molecule : openeye.oechem.OEMol
        The molecule from which a Topology object is to be generated.

    Returns
    -------
    topology : simtk.openmm.app.Topology
        The Topology object generated from `molecule`.

    """
    # Create a Topology object with one Chain and one Residue.
    from simtk.openmm.app import Topology
    topology = Topology()
    chain = topology.addChain()
    resname = molecule.GetTitle()
    residue = topology.addResidue(resname, chain)

    # Create atoms in the residue.
    for atom in molecule.GetAtoms():
        name = atom.GetName()
        element = elem.Element.getByAtomicNumber(atom.GetAtomicNum())
        atom = topology.addAtom(name, element, residue)

    # Create bonds.
    atoms = { atom.name : atom for atom in topology.atoms() }
    for bond in molecule.GetBonds():
        topology.addBond(atoms[bond.GetBgn().GetName()], atoms[bond.GetEnd().GetName()])

    return topology

def get_data_filename(relative_path):
    """Get the full path to one of the reference files in testsystems.

    In the source distribution, these files are in ``openforcefield/data/``,
    but on installation, they're moved to somewhere in the user's python
    site-packages directory.

    Parameters
    ----------
    name : str
        Name of the file to load (with respect to the repex folder).

    """

    from pkg_resources import resource_filename
    fn = resource_filename('openforcefield', os.path.join('data', relative_path))

    if not os.path.exists(fn):
        raise ValueError("Sorry! %s does not exist. If you just added it, you'll have to re-install" % fn)

    return fn

def normalize_molecules(molecules):
    """
    Normalize all molecules in specified set.

    ARGUMENTS

    molecules (list of OEMol) - molecules to be normalized (in place)

    """

    # Add explicit hydrogens.
    for molecule in molecules:
        openeye.oechem.OEAddExplicitHydrogens(molecule)

    # Build a conformation for all molecules with Omega.
    print("Building conformations for all molecules...")
    import openeye.oeomega
    omega = openeye.oeomega.OEOmega()
    omega.SetMaxConfs(1)
    omega.SetFromCT(True)
    for molecule in molecules:
        #omega.SetFixMol(molecule)
        omega(molecule)
    end_time = time.time()
    elapsed_time = end_time - start_time
    print("%.3f s elapsed" % elapsed_time)

    # Regularize all molecules through writing as mol2.
    print("Regularizing all molecules...")
    ligand_mol2_dirname  = os.path.dirname(mcmcDbName) + '/mol2'
    if( not os.path.exists( ligand_mol2_dirname ) ):
        os.makedirs(ligand_mol2_dirname)
    ligand_mol2_filename = ligand_mol2_dirname + '/temp' + os.path.basename(mcmcDbName) + '.mol2'
    start_time = time.time()
    omolstream = openeye.oechem.oemolostream(ligand_mol2_filename)
    for molecule in molecules:
        # Write molecule as mol2, changing molecule through normalization.
        openeye.oechem.OEWriteMolecule(omolstream, molecule)
    omolstream.close()
    end_time = time.time()
    elapsed_time = end_time - start_time
    print("%.3f s elapsed" % elapsed_time)

    # Assign AM1-BCC charges.
    print("Assigning AM1-BCC charges...")
    start_time = time.time()
    for molecule in molecules:
        # Assign AM1-BCC charges.
        if molecule.NumAtoms() == 1:
            # Use formal charges for ions.
            OEFormalPartialCharges(molecule)
        else:
            # Assign AM1-BCC charges for multiatom molecules.
            OEAssignPartialCharges(molecule, OECharges_AM1BCC, False) # use explicit hydrogens
        # Check to make sure we ended up with partial charges.
        if OEHasPartialCharges(molecule) == False:
            print("No charges on molecule: '%s'" % molecule.GetTitle())
            print("IUPAC name: %s" % OECreateIUPACName(molecule))
            # TODO: Write molecule out
            # Delete themolecule.
            molecules.remove(molecule)

    end_time = time.time()
    elapsed_time = end_time - start_time
    print("%.3f s elapsed" % elapsed_time)
    print("%d molecules remaining" % len(molecules))

    return

def read_molecules(filename, verbose=True):
    """
    Read molecules from an OpenEye-supported file.

    Parameters
    ----------
    filename : str
        Filename from which molecules are to be read (e.g. mol2, sdf)

    Returns
    -------
    molecules : list of OEMol
        List of molecules read from file

    """

    if not os.path.exists(filename):
        built_in = get_data_filename('molecules/%s' % filename)
        if not os.path.exists(built_in):
            raise Exception("File '%s' not found." % filename)
        filename = built_in

    if verbose: print("Loading molecules from '%s'..." % filename)
    start_time = time.time()
    molecules = list()
    input_molstream = oemolistream(filename)

    from openeye import oechem
    flavor = oechem.OEIFlavor_Generic_Default | oechem.OEIFlavor_MOL2_Default | oechem.OEIFlavor_MOL2_Forcefield
    input_molstream.SetFlavor(oechem.OEFormat_MOL2, flavor)

    molecule = OECreateOEGraphMol()
    while OEReadMolecule(input_molstream, molecule):
        # If molecule has no title, try getting SD 'name' tag
        if molecule.GetTitle() == '':
            name = OEGetSDData(molecule, 'name').strip()
            molecule.SetTitle(name)
        # Append to list.
        molecule_copy = OEMol(molecule)
        molecules.append(molecule_copy)
    input_molstream.close()
    if verbose: print("%d molecules read" % len(molecules))
    end_time = time.time()
    elapsed_time = end_time - start_time
    if verbose: print("%.3f s elapsed" % elapsed_time)

    return molecules

def setPositionsInOEMol(molecule, positions):
    """Set the positions in an OEMol using a position array with units from simtk.unit, i.e. from OpenMM. Atoms must have same order.

    Arguments:
    ---------
    molecule : OEMol
        OpenEye molecule
    positions : Nx3 array
        Unit-bearing via simtk.unit Nx3 array of coordinates
    """
    if molecule.NumAtoms() != len(positions): raise ValueError("Number of atoms in molecule does not match length of position array.")
    pos_unitless = positions/unit.angstroms

    coordlist = []
    for idx in range(len(pos_unitless)):
        for j in range(3):
            coordlist.append( pos_unitless[idx][j])
    molecule.SetCoords(OEFloatArray(coordlist))

def extractPositionsFromOEMol(molecule):
    """Get the positions from an OEMol and return in a position array with units via simtk.unit, i.e. foramtted for OpenMM.
    Adapted from choderalab/openmoltools test function extractPositionsFromOEMOL

    Arguments:
    ----------
    molecule : OEMol
        OpenEye molecule

    Returns:
    --------
    positions : Nx3 array
        Unit-bearing via simtk.unit Nx3 array of coordinates
    """

    positions = unit.Quantity(numpy.zeros([molecule.NumAtoms(), 3], numpy.float32), unit.angstroms)
    coords = molecule.GetCoords()
    for index in range(molecule.NumAtoms()):
        positions[index,:] = unit.Quantity(coords[index], unit.angstroms)
    return positions