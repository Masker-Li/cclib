# This file is part of cclib (http://cclib.sf.net), a library for parsing
# and interpreting the results of computational chemistry packages.
#
# Copyright (C) 2008-2014, the cclib development team
#
# The library is free software, distributed under the terms of
# the GNU Lesser General Public version 2.1 or later. You should have
# received a copy of the license along with cclib. You can also access
# the full license online at http://www.gnu.org/copyleft/lgpl.html.


import re

import numpy

from . import logfileparser
from . import utils


class NWChem(logfileparser.Logfile):
    """An NWChem log file."""

    def __init__(self, *args, **kwargs):

        # Call the __init__ method of the superclass
        super(NWChem, self).__init__(logname="NWChem", *args, **kwargs)
        
    def __str__(self):
        """Return a string representation of the object."""
        return "NWChem log file %s" % (self.filename)

    def __repr__(self):
        """Return a representation of the object."""
        return 'NWChem("%s")' % (self.filename)
    
    def normalisesym(self, label):
        """Use standard symmetry labels instead of NWChem labels.

        To normalise:
        (1) If label is one of [SG, PI, PHI, DLTA], replace by [sigma, pi, phi, delta]
        (2) replace any G or U by their lowercase equivalent

        >>> sym = NWChem("dummyfile").normalisesym
        >>> labels = ['A1', 'AG', 'A1G', "SG", "PI", "PHI", "DLTA", 'DLTU', 'SGG']
        >>> map(sym, labels)
        ['A1', 'Ag', 'A1g', 'sigma', 'pi', 'phi', 'delta', 'delta.u', 'sigma.g']
        """
        # FIXME if necessary
        return label

    def before_parsing(self):

        # Set any global variables for the parser here
        pass

    def set_scalar(self, name, value, check=True):
        if hasattr(self, name):
            if check:
                assert getattr(self, name) == value
        else:
            setattr(self, name, value)

    def extract(self, inputfile, line):
        """Extract information from the file object inputfile."""

        # This is printed in the input module, so should always be the first coordinates,
        # and contains many basic information we want to parse as well.
        if line.strip() == 'Geometry "geometry" -> ""':

            dashes = next(inputfile)
            blank = next(inputfile)
            concerning_units = next(inputfile)
            blank = next(inputfile)
            header = next(inputfile)
            dashes = next(inputfile)

            if not hasattr(self, 'atomcoords'):
                self.atomcoords = []

            line = next(inputfile)
            coords = []
            atomnos = []
            while line.strip():
                # The column labeled 'tag' is usually empty, but I'm not sure whether it can have spaces,
                # so for now assume that it can and that there will be seven columns in that case.
                if len(line.split()) == 6:
                    index, atomname, nuclear, x, y, z = line.split()
                else:
                    index, atomname, tag, nuclear, x, y, z = line.split()
                coords.append(list(map(float, [x,y,z])))
                atomnos.append(int(float(nuclear)))
                line = next(inputfile)
            self.atomcoords.append(coords)
            if hasattr(self, 'atomnos'):
                assert atomnos == self.atomnos
            else:
                self.atomnos = atomnos

        # If the geometry is printed in XYZ format, it will have the number of atoms.
        if line[12:31] == "XYZ format geometry":

            dashes = next(inputfile)
            natom = int(next(inputfile).strip())
            if hasattr(self, "natom"):
                assert self.natom == natom
            else:
                self.natom = natom

        if line.strip() == "NWChem SCF Module":
            dashes = next(inputfile)
            blank = next(inputfile)
            blank = next(inputfile)
            title = next(inputfile)
            blank = next(inputfile)
            blank = next(inputfile)
            blank = next(inputfile)
            line = next(inputfile)
            while line.strip():
                if line[2:8] == "charge":
                    self.charge = int(float(line.split()[-1]))
                if line[2:13] == "open shells":
                    unpaired = int(line.split()[-1])
                    self.mult = 2*unpaired + 1
                if line[2:7] == "atoms":
                    natom = int(line.split()[-1])
                    if hasattr(self, 'natom'):
                        assert self.natom == natom
                    else:
                        self.natom = natom
                if line[2:11] == "functions":
                    functions = int(line.split()[-1])
                    self.nbasis = functions
                line = next(inputfile)

        if line.strip() == "General Information":
            while line.strip():
                if "No. of atoms" in line:
                    self.set_scalar('natom', int(line.split()[-1]))
                if "Charge" in line:
                    self.set_scalar('charge', int(line.split()[-1]))
                if "Spin multiplicity" in line:
                    self.set_scalar('mult', int(line.split()[-1]))
                line = next(inputfile)

        if "Total SCF energy" in line:
            if not hasattr(self, "scfenergies"):
                self.scfenergies = []
            energy = float(line.split()[-1])
            energy = utils.convertor(energy, "hartree", "eV")
            self.scfenergies.append(energy)

        if "Final Molecular Orbital Analysis" in line:
            if not hasattr(self, "moenergies"):
                self.moenergies = []
            dashes = next(inputfile)
            blank = next(inputfile)

            energies = []
            line = next(inputfile)
            homo = 0
            while line[:7] == " Vector":
                nvector = int(line[7:12])
                if "Occ=2.0" in line:
                    homo = nvector-1
                if len(energies) == 0 and nvector > 1:
                    for i in range(1,nvector):
                        energies.append(None)
                energy = float(line[34:].replace('D','E'))
                energy = utils.convertor(energy, "hartree", "eV")
                energies.append(energy)
                line = next(inputfile)
                if "MO Center" in line:
                    line = next(inputfile)
                if "Bfn." in line:
                    line = next(inputfile)
                if "-----" in line:
                    line = next(inputfile)
                while line.strip():
                    line = next(inputfile)
                line = next(inputfile)
            self.moenergies.append(energies)
            if hasattr(self, 'nmo'):
                assert self.nmo == nmo
            else:
                self.nmo = nvector
            if not hasattr(self, 'homos'):
                self.homos = []
            self.homos.append(homo)

        if line.strip() == "Final MO vectors":

            dashes = next(inputfile)
            blank = next(inputfile)
            blank = next(inputfile)

            # the columns are MOs, columns AOs, but I'm guessing the order of this array
            array_info = next(inputfile)
            size = array_info.split('[')[1].split(']')[0]
            nbasis = int(size.split(',')[0].split(':')[1])
            nmo = int(size.split(',')[1].split(':')[1])
            if hasattr(self, 'nbasis'):
                assert self.nbasis == nbasis
            else:
                self.nbasis = nbasis
            if hasattr(self, 'nmo'):
                assert self.nmo == nmo
            else:
                self.nmo = nmo
            
            blank = next(inputfile)
            mocoeffs = []
            while len(mocoeffs) < self.nmo:
                nmos = list(map(int,next(inputfile).split()))
                assert len(mocoeffs) == nmos[0]-1
                for n in nmos:
                    mocoeffs.append([])
                dashes = next(inputfile)
                for nb in range(nbasis):                
                    line = next(inputfile)
                    index = int(line.split()[0])
                    assert index == nb+1
                    coefficients = list(map(float,line.split()[1:]))
                    assert len(coefficients) == len(nmos)
                    for i,c in enumerate(coefficients):
                        mocoeffs[nmos[i]-1].append(c)
                blank = next(inputfile)
            self.mocoeffs = [mocoeffs]

        if line.strip() == "Mulliken analysis of the total density":

            if not hasattr(self, "atomcharges"):
                self.atomcharges = {}

            dashes = next(inputfile)
            blank = next(inputfile)
            header = next(inputfile)
            dashes = next(inputfile)

            charges = []
            line = next(inputfile)
            while line.strip():
                index, atomname, nuclear, atom = line.split()[:4]
                shells = line.split()[4:]
                charges.append(float(atom)-float(nuclear))
                line = next(inputfile)
            self.atomcharges['mulliken'] = charges


if __name__ == "__main__":
    import doctest, nwchemparser
    doctest.testmod(nwchemparser, verbose=False)
