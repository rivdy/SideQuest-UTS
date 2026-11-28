"""3D coordinates for display only: one ETKDG conformer, MMFF-relaxed, with a fixed seed.

The geometry illustrates molecular shape. It is not a property prediction and says nothing
about stability, odour, or colour.
"""

from pydantic import BaseModel
from rdkit import Chem
from rdkit.Chem import AllChem

MAX_ATOMS = 160
SEED = 2971


class Atom3D(BaseModel):
    element: str
    x: float
    y: float
    z: float


class Bond3D(BaseModel):
    a: int
    b: int
    order: float


class Conformer(BaseModel):
    canonical_smiles: str
    atoms: list[Atom3D]
    bonds: list[Bond3D]
    method: str
    note: str


def conformer(smiles: str) -> Conformer:
    mol = Chem.MolFromSmiles(smiles)
    if mol is None:
        raise ValueError("SMILES tidak dapat dibaca.")
    canonical = Chem.MolToSmiles(mol)
    mol = Chem.AddHs(mol)
    if mol.GetNumAtoms() > MAX_ATOMS:
        raise ValueError(f"Molekul terlalu besar untuk tampilan 3D (> {MAX_ATOMS} atom).")
    params = AllChem.ETKDGv3()
    params.randomSeed = SEED
    if AllChem.EmbedMolecule(mol, params) != 0:
        raise ValueError("Koordinat 3D tidak dapat dibuat untuk struktur ini.")
    relaxed = AllChem.MMFFHasAllMoleculeParams(mol)
    if relaxed:
        AllChem.MMFFOptimizeMolecule(mol, maxIters=500)
    positions = mol.GetConformer().GetPositions()
    center = positions.mean(axis=0)
    atoms = [
        Atom3D(element=atom.GetSymbol(), x=float(p[0]), y=float(p[1]), z=float(p[2]))
        for atom, p in zip(mol.GetAtoms(), positions - center, strict=True)
    ]
    bonds = [
        Bond3D(a=b.GetBeginAtomIdx(), b=b.GetEndAtomIdx(), order=b.GetBondTypeAsDouble())
        for b in mol.GetBonds()
    ]
    return Conformer(
        canonical_smiles=canonical,
        atoms=atoms,
        bonds=bonds,
        method="RDKit ETKDGv3" + (" + MMFF94" if relaxed else "") + f", seed {SEED}",
        note=(
            "Bentuk 3D ilustratif dari satu konformer; "
            "bukan prediksi sifat, warna, atau stabilitas."
        ),
    )
