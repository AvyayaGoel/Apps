"""RDKit integration, naming, formula/mass, and file I/O."""

import json
import logging
import math
import os
import re
import urllib.parse
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Optional, Tuple, List, Set

import pubchempy as pcp
import requests
from rdkit import Chem, RDLogger
from rdkit.Chem import rdCoordGen, rdDepictor

from config import IONIC_DISTANCE
from models import Molecule

RDLogger.logger().setLevel(RDLogger.CRITICAL)
logger = logging.getLogger(__name__)

# ── Disk cache for names ─────────────────────────────────────────────────────
_CACHE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), '.cache')
os.makedirs(_CACHE_DIR, exist_ok=True)
_NAME_CACHE_FILE = os.path.join(_CACHE_DIR, 'name_cache.json')
_name_disk_cache: dict[str, str] = {}
try:
    with open(_NAME_CACHE_FILE, 'r', encoding='utf-8') as f:
        _name_disk_cache = json.load(f)
except Exception as exc:
    logger.warning(f'Could not load name disk cache: {exc}')


def _save_name_cache():
    try:
        with open(_NAME_CACHE_FILE, 'w', encoding='utf-8') as f:
            json.dump(_name_disk_cache, f, indent=2, ensure_ascii=False)
    except Exception as exc:
        logger.warning(f'Could not save name disk cache: {exc}')


# ── Name resolver sources (SMILES → Name) ──────────────────────────────────────
# Each returns a name string or None.  They are run in parallel with a
# ThreadPoolExecutor capped at MAX_CONCURRENT sources.

MAX_CONCURRENT_SOURCES = 2  # limit active network requests to avoid lag


def _fetch_name_from_cactus(smiles: str) -> Optional[str]:
    """CACTUS NIH Chemical Identifier Resolver."""
    try:
        enc = urllib.parse.quote(smiles, safe='')
        url = f'https://cactus.nci.nih.gov/chemical/structure/{enc}/iupac_name'
        r = requests.get(url, timeout=4)
        if r.status_code == 200:
            name = r.text.strip()
            if name and name != smiles:
                logger.info(f'CACTUS resolved: {name[:60]}')
                return name
            else:
                logger.warning('CACTUS returned empty or same-as-SMILES result')
    except Exception as exc:
        logger.warning(f'CACTUS request failed: {exc}')
    return None


def _fetch_name_from_pubchem_rest(smiles: str) -> Optional[str]:
    """PubChem PUG REST: SMILES → CID → IUPAC name."""
    try:
        # Step 1: SMILES → CID
        enc = urllib.parse.quote(smiles, safe='')
        url = f'https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/smiles/{enc}/cids/JSON'
        r = requests.get(url, timeout=6)
        if r.status_code != 200:
            logger.warning(f'PubChem REST SMILES→CID failed: {r.status_code}')
            return None
        data = r.json()
        cids = data.get('IdentifierList', {}).get('CID', [])
        if not cids:
            logger.warning('PubChem REST: no CIDs found')
            return None
        cid = cids[0]
        # Step 2: CID → IUPAC name
        url2 = f'https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/cid/{cid}/property/IUPACName/JSON'
        r2 = requests.get(url2, timeout=6)
        if r2.status_code == 200:
            props = r2.json().get('PropertyTable', {}).get('Properties', [])
            if props:
                name = props[0].get('IUPACName', '').strip()
                if name:
                    logger.info(f'PubChem REST resolved: {name[:60]}')
                    return name
    except Exception as exc:
        logger.warning(f'PubChem REST request failed: {exc}')
    return None


def _fetch_name_from_pubchempy(smiles: str) -> Optional[str]:
    """PubChemPy library (optional dependency)."""
    try:
        compounds = pcp.get_compounds(smiles, 'smiles', timeout=6)
        if compounds is not None:
            name = compounds[0].iupac_name
            if name:
                logger.info(f'PubChemPy resolved: {name[:60]}')
                return name
    except ImportError:
        logger.debug('PubChemPy not installed, skipping')
    except Exception as exc:
        logger.warning(f'PubChemPy request failed: {exc}')
    return None


# Ordered by reliability / speed.  Only the first N are used per request.
_NAME_SOURCES = [
    ('cactus', _fetch_name_from_cactus),
    ('pubchem_rest', _fetch_name_from_pubchem_rest),
    ('pubchempy', _fetch_name_from_pubchempy),
]


def resolve_name_parallel(smiles: str) -> Optional[str]:
    """Run multiple name resolvers in parallel, return the first success.

    Uses a ThreadPoolExecutor capped at MAX_CONCURRENT_SOURCES so we
    never hammer the network with more than 2 simultaneous requests.
    """
    if not smiles:
        return None

    # Check disk cache first
    if smiles in _name_disk_cache:
        cached = _name_disk_cache[smiles]
        logger.info('Name cache hit for SMILES')
        return cached

    # Pick a subset of sources (rotate to balance load)
    sources = _NAME_SOURCES[:MAX_CONCURRENT_SOURCES + 1]

    with ThreadPoolExecutor(max_workers=MAX_CONCURRENT_SOURCES) as executor:
        futures = {
            executor.submit(fn, smiles): name
            for name, fn in sources
        }
        for future in as_completed(futures):
            source_name = futures[future]
            try:
                result = future.result(timeout=8)
                if result:
                    _name_disk_cache[smiles] = result
                    _save_name_cache()
                    logger.info(f'First successful name from {source_name}: {result[:60]}')
                    return result
            except Exception as exc:
                logger.warning(f'Name source {source_name} failed: {exc}')

    logger.info('All name resolvers returned empty')
    return None


# ── Formula / Mass ─────────────────────────────────────────────────────────────

def _build_formula(counts: dict) -> str:
    """Build formula string from element counts."""
    pieces = []
    if counts.get('C', 0) > 0:
        n = counts['C']
        pieces.append(f"C{(n if n > 1 else '')}")
    if counts.get('H', 0) > 0:
        n = counts['H']
        pieces.append(f"H{(n if n > 1 else '')}")
    for el in sorted(counts.keys()):
        if el in ('C', 'H'):
            continue
        n = counts[el]
        pieces.append(f"{el}{(n if n > 1 else '')}")
    return ''.join(pieces) if pieces else ''


def _compute_mass(counts: dict) -> float:
    """Compute molecular mass from element counts."""
    mass = 0.0
    try:
        pt = Chem.GetPeriodicTable()
        for el, n in counts.items():
            mass += pt.GetAtomicWeight(el) * n
    except Exception as exc:
        logger.warning(f'Mass calculation failed: {exc}')
    return mass


def compute_formula_and_mass(mol: Molecule) -> Tuple[str, float]:
    try:
        counts = {}
        for a in mol.atoms:
            counts[a.element] = counts.get(a.element, 0) + 1
        formula = _build_formula(counts)
        mass = _compute_mass(counts)
        return formula, mass
    except Exception as exc:
        logger.exception(f"compute_formula_and_mass error: {exc}")
        return '', 0.0


def compute_fragment_formula(mol: Molecule) -> Tuple[str, float, int]:
    try:
        counts = {}
        net_charge = 0
        for a in mol.atoms:
            counts[a.element] = counts.get(a.element, 0) + 1
            net_charge += a.formal_charge
        formula = _build_formula(counts)
        mass = _compute_mass(counts)
        return formula, mass, net_charge
    except Exception as exc:
        logger.exception(f"compute_fragment_formula error: {exc}")
        return '', 0.0, 0


# Unicode subscript/superscript digit mappings (Qt RichText does NOT support <sub>/<sup>)
_SUBSCRIPT_DIGITS = {
    '0': '₀', '1': '₁', '2': '₂', '3': '₃', '4': '₄',
    '5': '₅', '6': '₆', '7': '₇', '8': '₈', '9': '₉',
}
_SUPERSCRIPT_DIGITS = {
    '0': '⁰', '1': '¹', '2': '²', '3': '³', '4': '⁴',
    '5': '⁵', '6': '⁶', '7': '⁷', '8': '⁸', '9': '⁹',
}
_SUPERSCRIPT_PLUS = '⁺'
_SUPERSCRIPT_MINUS = '⁻'


def _to_subscript(s: str) -> str:
    """Convert digit string to Unicode subscript characters."""
    return ''.join(_SUBSCRIPT_DIGITS.get(ch, ch) for ch in s)


def _to_superscript(s: str) -> str:
    """Convert string to Unicode superscript characters."""
    result = []
    for ch in s:
        if ch in _SUPERSCRIPT_DIGITS:
            result.append(_SUPERSCRIPT_DIGITS[ch])
        elif ch == '+':
            result.append(_SUPERSCRIPT_PLUS)
        elif ch == '-':
            result.append(_SUPERSCRIPT_MINUS)
        else:
            result.append(ch)
    return ''.join(result)


def format_formula_html(formula: str, charge: int = 0) -> str:
    if not formula:
        return '—'
    html = re.sub(r'(\d+)', lambda m: _to_subscript(m.group(1)), formula)
    if charge != 0:
        sign = '+' if charge > 0 else '-'
        abs_q = abs(charge)
        charge_str = f'{abs_q}{sign}' if abs_q > 1 else sign
        html += _to_superscript(charge_str)
    return html


def find_fragments(mol: Molecule, ionic_distance: float = IONIC_DISTANCE) -> List[Set[int]]:
    if not mol.atoms:
        return []
    parent = {a.id: a.id for a in mol.atoms}

    def find(x: int) -> int:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(x: int, y: int):
        rx, ry = find(x), find(y)
        if rx != ry:
            parent[rx] = ry

    for bond in mol.bonds:
        union(bond.a1, bond.a2)
    charged = [a for a in mol.atoms if a.formal_charge != 0]
    for i, a1 in enumerate(charged):
        for a2 in charged[i + 1:]:
            if a1.formal_charge * a2.formal_charge < 0:
                d = math.hypot(a1.x - a2.x, a1.y - a2.y)
                if d <= ionic_distance:
                    union(a1.id, a2.id)
    groups: dict[int, Set[int]] = {}
    for a in mol.atoms:
        root = find(a.id)
        groups.setdefault(root, set()).add(a.id)
    return list(groups.values())


def extract_fragment_mol(mol: Molecule, atom_ids: Set[int]) -> Molecule:
    try:
        frag = Molecule()
        id_map: dict[int, int] = {}
        for a in mol.atoms:
            if a.id in atom_ids:
                new_a = frag.add_atom(a.x, a.y, a.element, a.formal_charge, a.auto)
                id_map[a.id] = new_a.id
        for b in mol.bonds:
            if b.a1 in atom_ids and b.a2 in atom_ids:
                frag.add_bond(id_map[b.a1], id_map[b.a2], b.type)
        return frag
    except Exception as exc:
        logger.exception(f"extract_fragment_mol error: {exc}")
        return Molecule()


def _add_atoms_to_rwmol(rw: Chem.RWMol, mol: Molecule) -> dict[int, int]:
    """Add atoms from Molecule to RWMol, return id→idx mapping."""
    id_to_idx = {}
    for a in mol.atoms:
        at = Chem.Atom(a.element)
        idx = rw.AddAtom(at)
        id_to_idx[a.id] = idx
        if a.formal_charge != 0:
            rw.GetAtomWithIdx(idx).SetFormalCharge(a.formal_charge)
    return id_to_idx


def _add_bonds_to_rwmol(rw: Chem.RWMol, mol: Molecule, id_to_idx: dict[int, int]):
    """Add bonds from Molecule to RWMol."""
    for b in mol.bonds:
        if b.a1 not in id_to_idx or b.a2 not in id_to_idx:
            logger.warning(f'  Bond {b.a1}-{b.a2} references unknown atom ID')
            continue
        bt = {'S': Chem.BondType.SINGLE, 'D': Chem.BondType.DOUBLE, 'T': Chem.BondType.TRIPLE}.get(b.type,
                                                                                                   Chem.BondType.SINGLE)
        try:
            if bt:
                rw.AddBond(id_to_idx[b.a1], id_to_idx[b.a2], bt)
        except Exception as exc:
            logger.warning(f'  Failed to add bond {b.a1}-{b.a2}: {exc}')


def molecule_to_rdkit(mol: Molecule) -> Optional[Chem.Mol]:
    try:
        if not mol.atoms:
            return None
        rw = Chem.RWMol()
        id_to_idx = _add_atoms_to_rwmol(rw, mol)
        _add_bonds_to_rwmol(rw, mol, id_to_idx)
        rdmol = rw.GetMol()
        rdmol.UpdatePropertyCache()
        try:
            Chem.SanitizeMol(rdmol)
        except Exception as exc:
            logger.warning(f'molecule_to_rdkit: RDKit sanitization failed: {exc}')
        return rdmol
    except Exception as exc:
        logger.exception(f'molecule_to_rdkit error: {exc}')
        return None


def rdkit_to_molecule(rdmol: Chem.Mol, center_x: float, center_y: float, scale: float = 65.0) -> Molecule:
    try:
        mol = Molecule()
        if rdmol.GetNumAtoms() == 0:
            logger.warning('rdkit_to_molecule: empty RDKit mol')
            return mol
        if rdmol.GetNumConformers() == 0:
            rdmol = Chem.AddHs(rdmol)
            rdDepictor.Compute2DCoords(rdmol)
        conf = rdmol.GetConformer(0)
        xs = [conf.GetAtomPosition(i).x for i in range(rdmol.GetNumAtoms())]
        ys = [conf.GetAtomPosition(i).y for i in range(rdmol.GetNumAtoms())]
        cx = sum(xs) / len(xs)
        cy = sum(ys) / len(ys)
        idx_to_sim = {}
        for i, atom in enumerate(rdmol.GetAtoms()):
            pos = conf.GetAtomPosition(i)
            x = (pos.x - cx) * scale + center_x
            y = (pos.y - cy) * scale + center_y
            a = mol.add_atom(x, y, atom.GetSymbol(), atom.GetFormalCharge())
            idx_to_sim[i] = a.id
        for bond in rdmol.GetBonds():
            a1 = idx_to_sim[bond.GetBeginAtomIdx()]
            a2 = idx_to_sim[bond.GetEndAtomIdx()]
            bt = bond.GetBondType()
            if bt == Chem.BondType.TRIPLE:
                btype = 'T'
            elif bt == Chem.BondType.DOUBLE:
                btype = 'D'
            else:
                btype = 'S'
            mol.add_bond(a1, a2, btype)
        return mol
    except Exception as exc:
        logger.exception(f"rdkit_to_molecule error: {exc}")
        return Molecule()


def compute_smiles(mol: Molecule) -> str:
    try:
        """Return canonical SMILES, or empty string if invalid."""
        if not mol.atoms:
            return ''
        rdmol = molecule_to_rdkit(mol)
        if not rdmol:
            logger.warning('compute_smiles: RDKit conversion failed')
            return ''
        try:
            return Chem.MolToSmiles(rdmol, canonical=True)
        except Exception as exc:
            logger.warning(f'compute_smiles: MolToSmiles failed: {exc}')
            return ''
    except Exception as exc:
        logger.exception(f"compute_smiles error: {exc}")
        return ''


def build_from_name(name: str) -> Optional[Molecule]:
    try:
        url = 'https://opsin.ch.cam.ac.uk/opsin/' + urllib.parse.quote(name) + '.json'
        r = requests.get(url, timeout=8)
        if r.status_code != 200:
            logger.warning(f'OPSIN failed: {r.status_code}')
            return None
        data = r.json()
        if 'smiles' not in data:
            logger.warning('No SMILES in OPSIN response')
            return None
        smiles = data['smiles']
        rdmol = Chem.MolFromSmiles(smiles)
        if not rdmol:
            logger.warning('RDKit could not parse SMILES')
            return None
        return rdkit_to_molecule(rdmol, 0, 0, scale=55.0)
    except Exception as exc:
        logger.exception(f'OPSIN error: {exc}')
        return None


def compute_name(mol: Molecule) -> str:
    try:
        """Look up human-readable name for molecule using parallel resolvers.

        Fast path: uses RDKit's built-in naming for simple/common molecules.
        Slow path: runs CACTUS, PubChem REST, and PubChemPy in parallel,
                  returns the first successful result.
        """
        if not mol.atoms:
            return '—'
        rdmol = molecule_to_rdkit(mol)
        if not rdmol:
            logger.warning('compute_name: RDKit conversion failed')
            return 'Invalid structure'
        try:
            no_h = Chem.RemoveHs(rdmol)
            Chem.SanitizeMol(no_h)
        except Exception as exc:
            logger.warning(f'compute_name: SanitizeMol failed, using original: {exc}')
            no_h = rdmol
        try:
            smiles = Chem.MolToSmiles(no_h, canonical=True)
        except Exception as exc:
            logger.warning(f'compute_name: MolToSmiles failed: {exc}')
            smiles = None
        if not smiles:
            return 'Unknown'
        if smiles in _name_disk_cache:
            return _name_disk_cache[smiles]

        # Parallel resolution with capped concurrency
        name = resolve_name_parallel(smiles)
        if name:
            return name

        # Fallback: InChIKey
        try:
            inchi = Chem.MolToInchi(no_h)
            if inchi:
                key = Chem.InchiToInchiKey(inchi)
                if key and key != 'InChIKey=None':
                    return f'InChIKey: {key[:14]}...'
        except Exception as exc:
            logger.warning(f'compute_name: InChIKey generation failed: {exc}')
        return smiles
    except Exception as exc:
        logger.exception(f"compute_name error: {exc}")
        return 'Unknown'


def save_scene(mol: Molecule, path: str, camera_x: float = 0, camera_y: float = 0, zoom: float = 1.0):
    try:
        data = mol.to_dict()
        data['camera_x'] = camera_x
        data['camera_y'] = camera_y
        data['zoom'] = zoom
        with open(path, 'w') as f:
            json.dump(data, f, indent=2)
    except Exception as exc:
        logger.exception(f'save_scene failed: {exc}')
        raise


def load_scene(path: str) -> Tuple[Molecule, float, float, float]:
    try:
        with open(path, 'r') as f:
            data = json.load(f)
        mol = Molecule()
        mol.from_dict(data)
        cam_x = data.get('camera_x', 0.0)
        cam_y = data.get('camera_y', 0.0)
        zoom = data.get('zoom', 1.0)
        return mol, cam_x, cam_y, zoom
    except Exception as exc:
        logger.exception(f'load_scene failed: {exc}')
        raise


def clear_up_molecule(mol: Molecule) -> Molecule:
    try:
        rdmol = molecule_to_rdkit(mol)
        if not rdmol:
            logger.warning('clear_up_molecule: RDKit conversion failed, returning original')
            return mol
        try:
            rdmol = Chem.AddHs(rdmol)
            rdCoordGen.AddCoords(rdmol)
            cx, cy = mol.center()
            return rdkit_to_molecule(rdmol, cx, cy, scale=65.0)
        except Exception as exc:
            logger.exception(f'Clear-up error: {exc}')
            return mol
    except Exception as exc:
        logger.exception(f"clear_up_molecule error: {exc}")
        return mol
