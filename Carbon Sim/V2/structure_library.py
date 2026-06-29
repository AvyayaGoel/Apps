"""Structure Browser support module."""

import logging
from typing import Dict, List, Optional, Tuple

from rdkit import Chem
from rdkit.Chem import rdDepictor
from rdkit.Chem.Draw import rdMolDraw2D

from chemistry import _build_formula, format_formula_html
from structures_data import PREBUILT_STRUCTURES, STRUCTURE_CATEGORY_ORDER

logger = logging.getLogger(__name__)


class StructureEntry:
    __slots__ = ('name', 'category', 'smiles', 'elements', '_formula', '_formula_html',
                 '_mass', '_svg_cache', '_ghost_cache')

    def __init__(self, data: dict):
        self.name: str = data['name']
        self.category: str = data['category']
        self.smiles: str = data['smiles']
        self.elements: Dict[str, int] = data['elements']
        self._formula: Optional[str] = None
        self._formula_html: Optional[str] = None
        self._mass: Optional[float] = None
        self._svg_cache: Optional[str] = None
        self._ghost_cache: Optional[Tuple[List[Tuple[float, float, str, int]], List[Tuple[int, int, str]]]] = None

    @property
    def formula(self) -> str | None:
        if self._formula is None:
            try:
                self._formula = _build_formula(self.elements)
            except Exception as e:
                logger.exception(f'StructureEntry.formula error for {self.name}: {e}')
                self._formula = ''
        return self._formula

    @property
    def formula_html(self) -> str | None:
        if self._formula_html is None:
            self._formula_html = format_formula_html(self.formula)
        return self._formula_html

    @property
    def atom_count(self) -> int:
        return sum(self.elements.values())

    @property
    def heavy_atom_count(self) -> int:
        return sum(n for el, n in self.elements.items() if el != 'H')

    @property
    def mass(self) -> float | None:
        if self._mass is None:
            try:
                pt = Chem.GetPeriodicTable()
                self._mass = sum(pt.GetAtomicWeight(el) * n for el, n in self.elements.items())
            except Exception as e:
                logger.exception(f'StructureEntry.mass error for {self.name}: {e}')
                self._mass = 0.0
        return self._mass

    def svg(self, width: int = 130, height: int = 64) -> str | None:
        if self._svg_cache is not None:
            return self._svg_cache
        try:
            mol = Chem.MolFromSmiles(self.smiles)
            if mol is None:
                self._svg_cache = ''
                return self._svg_cache
            rdDepictor.Compute2DCoords(mol)
            drawer = rdMolDraw2D.MolDraw2DSVG(width, height)
            opts = drawer.drawOptions()
            opts.clearBackground = False
            opts.bondLineWidth = 2
            drawer.DrawMolecule(mol)
            drawer.FinishDrawing()
            svg = drawer.GetDrawingText()
            svg = svg.replace('stroke:#000000', 'stroke:#dce8ff').replace('fill:#000000', 'fill:#dce8ff')
            self._svg_cache = svg
        except Exception as e:
            logger.exception(f'StructureEntry.svg error for {self.name}: {e}')
            self._svg_cache = ''
        return self._svg_cache

    def ghost_geometry(self) -> tuple[list[tuple[float, float, str, int]], list[tuple[int, int, str]]] | None:
        if self._ghost_cache is not None:
            return self._ghost_cache
        try:
            mol = Chem.MolFromSmiles(self.smiles)
            if mol is None:
                self._ghost_cache = ([], [])
                return self._ghost_cache
            Chem.Kekulize(mol, clearAromaticFlags=True)
            mol = Chem.AddHs(mol)
            rdDepictor.Compute2DCoords(mol)
            conf = mol.GetConformer(0)
            xs = [conf.GetAtomPosition(i).x for i in range(mol.GetNumAtoms())]
            ys = [conf.GetAtomPosition(i).y for i in range(mol.GetNumAtoms())]
            cx = sum(xs) / len(xs) if xs else 0.0
            cy = sum(ys) / len(ys) if ys else 0.0
            atoms: List[Tuple[float, float, str, int]] = []
            for i, atom in enumerate(mol.GetAtoms()):
                pos = conf.GetAtomPosition(i)
                atoms.append((pos.x - cx, pos.y - cy, atom.GetSymbol(), atom.GetFormalCharge()))
            bonds: List[Tuple[int, int, str]] = []
            for bond in mol.GetBonds():
                bt = bond.GetBondType()
                if bt == Chem.BondType.TRIPLE:
                    btype = 'T'
                elif bt == Chem.BondType.DOUBLE:
                    btype = 'D'
                else:
                    btype = 'S'
                bonds.append((bond.GetBeginAtomIdx(), bond.GetEndAtomIdx(), btype))
            self._ghost_cache = (atoms, bonds)
        except Exception as e:
            logger.exception(f'StructureEntry.ghost_geometry error for {self.name}: {e}')
            self._ghost_cache = ([], [])
        return self._ghost_cache


class StructureLibrary:
    def __init__(self):
        try:
            self.entries: List[StructureEntry] = [StructureEntry(d) for d in PREBUILT_STRUCTURES]
            self._by_category: Dict[str, List[StructureEntry]] = {}
            for e in self.entries:
                self._by_category.setdefault(e.category, []).append(e)
        except Exception as ex:
            logger.exception(f'StructureLibrary init error: {ex}')
            self.entries = []
            self._by_category = {}

    def categories(self) -> List[str]:
        present = set(self._by_category.keys())
        ordered = [c for c in STRUCTURE_CATEGORY_ORDER if c in present]
        leftover = sorted(present - set(ordered))
        return ordered + leftover

    def entries_for_category(self, category: str) -> List[StructureEntry]:
        return self._by_category.get(category, [])

    def search(self, query: str) -> List[StructureEntry]:
        q = query.strip().lower()
        if not q:
            return list(self.entries)
        results = []
        for e in self.entries:
            if q in e.name.lower() or q in e.formula.lower() or q in e.category.lower():
                results.append(e)
        return results
