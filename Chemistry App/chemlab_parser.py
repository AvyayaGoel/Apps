"""
ChemLab Parser - Handles all parsing and validation logic
"""

import re
import logging
from math import gcd, lcm
from fractions import Fraction
from functools import reduce
from mendeleev import element
from constants import ARROWS, SUBSCRIPT_MAP, STATE_SYMBOL_PATTERN, SUBSCRIPT_DISPLAY_MAP, ARROW_MAP, STATE_NAMES

class ChemLabParser:
    """Handles reaction parsing, element extraction, and validation"""

    @staticmethod
    def split_reaction(reaction):
        """Split reaction into reactants and products"""
        for arrow in ARROWS:
            if arrow in reaction:
                parts = reaction.split(arrow)
                if len(parts) == 2:
                    return parts[0].strip(), parts[1].strip()
        return None, None
    
    @staticmethod
    def extract_elements_from_side(side):
        """Extract elements from one side of reaction"""
        elements = []
        
        # Split by + to get individual compounds
        compounds = [c.strip() for c in side.split('+')]
        
        # Extract elements from each compound
        for compound in compounds:
            # Remove state symbols like (aq), (s), etc.
            compound = re.sub(r'\([a-z]+\)', '', compound)
            # Remove coefficients
            compound = re.sub(r'^\d+', '', compound)
            # Parse formula
            try:
                elements_in_compound = ChemLabParser.parse_formula(compound)
                elements.extend(elements_in_compound.keys())
            except (ValueError, KeyError):
                continue
        
        return elements
    
    @staticmethod
    def extract_elements_from_reaction(reaction):
        """Extract all elements from reaction"""
        elements = set()
        
        reactants, products= ChemLabParser.split_reaction(reaction)
        if not reactants or not products:
            return list(elements)
        
        # Extract from both sides
        reactant_elements = ChemLabParser.extract_elements_from_side(reactants)
        product_elements = ChemLabParser.extract_elements_from_side(products)
        
        elements.update(reactant_elements)
        elements.update(product_elements)
        
        return list(elements)
    
    @staticmethod
    def parse_formula(formula):
        """Parse chemical formula to extract elements"""
        formula = formula.translate(SUBSCRIPT_MAP)
        pattern = r"([A-Z][a-z]*)(\d*)|(\()|(\))(\d*)"

        stack = [{}]

        for match in re.finditer(pattern, formula):
            groups = match.groups()
            elem = groups[0]
            count = groups[1]
            open_p = groups[2]
            close_p = groups[3]
            multiplier = groups[4]

            if elem:
                num = int(count) if count else 1
                stack[-1][elem] = stack[-1].get(elem, 0) + num
            elif open_p:
                stack.append({})
            elif close_p:
                mult = int(multiplier) if multiplier else 1
                popped_layer = stack.pop()
                for e, c in popped_layer.items():
                    stack[-1][e] = stack[-1].get(e, 0) + (c * mult)

        return stack[0]
    
    @staticmethod
    def calculate_molar_mass(formula):
        """Calculate molar mass of a compound in g/mol"""
        try:
            elements = ChemLabParser.parse_formula(formula)
            total_mass = 0.0
            
            for elem_symbol, count in elements.items():
                try:
                    elem_data = element(elem_symbol)
                    atomic_mass = elem_data.atomic_weight
                    if atomic_mass:
                        total_mass += atomic_mass * count
                except (ValueError, KeyError, AttributeError):
                    logging.warning(f"Could not find atomic mass for element: {elem_symbol}")
                    continue
            
            return round(total_mass, 3)
        except Exception as e:
            logging.error(f"Error calculating molar mass for {formula}: {e}")
            return None
    
    @staticmethod
    def calculate_elemental_composition(formula):
        """Calculate elemental composition (% by mass)"""
        try:
            elements = ChemLabParser.parse_formula(formula)
            total_mass = 0.0
            element_masses = {}
            
            # Calculate mass contribution of each element
            for elem_symbol, count in elements.items():
                try:
                    elem_data = element(elem_symbol)
                    atomic_mass = elem_data.atomic_weight
                    if atomic_mass:
                        mass = atomic_mass * count
                        element_masses[elem_symbol] = {
                            'count': count,
                            'mass': mass
                        }
                        total_mass += mass
                except (ValueError, KeyError, AttributeError):
                    continue
            
            # Calculate percentages
            composition = {}
            for elem_symbol, data in element_masses.items():
                composition[elem_symbol] = {
                    'count': data['count'],
                    'mass': round(data['mass'], 3),
                    'percentage': round((data['mass'] / total_mass) * 100, 2) if total_mass > 0 else 0
                }
            
            return composition, round(total_mass, 3)
        except Exception as e:
            logging.error(f"Error calculating elemental composition for {formula}: {e}")
            return None, None
    
    @staticmethod
    def get_element_properties(elem_symbol):
        """Get properties of an element from mendeleev"""
        try:
            elem_data = element(elem_symbol)
            return {
                'name': elem_data.name,
                'atomic_number': elem_data.atomic_number,
                'atomic_weight': round(elem_data.atomic_weight, 3) if elem_data.atomic_weight else None,
                'symbol': elem_data.symbol,
                'group': elem_data.group_id,
                'period': elem_data.period,
                'category': elem_data.series
            }
        except (ValueError, KeyError, AttributeError):
            return None
    
    @staticmethod
    def extract_compounds_from_reaction(reaction):
        """Extract reactants and products from reaction"""
        compounds = []
        
        reactants, products = ChemLabParser.split_reaction(reaction)
        if not reactants or not products:
            return compounds
        
        # Process reactants
        reactant_compounds = [c.strip() for c in reactants.split('+')]
        for compound in reactant_compounds:
            state,_ = ChemLabParser.extract_state_symbol(compound)
            compounds.append({
                'formula': compound,
                'type': 'Reactant',
                'name': '',
                'color': '',
                'state': state,
                'notes': ''
            })
        
        # Process products
        product_compounds = [c.strip() for c in products.split('+')]
        for compound in product_compounds:
            state,_ = ChemLabParser.extract_state_symbol(compound)
            compounds.append({
                'formula': compound,
                'type': 'Product',
                'name': '',
                'color': '',
                'state': state,
                'notes': ''
            })
        
        return compounds
    
    @staticmethod
    def _validate_elements_exist(reactant_elements, product_elements):
        """Check if all elements in the reaction are real elements.
        
        Returns:
            tuple: (valid: bool, invalid_elements: list or None)
        """
        invalid_elements = []
        all_elements = set(reactant_elements + product_elements)
        for elem in all_elements:
            try:
                element(elem)  # Test if element exists
            except (ValueError, KeyError):
                invalid_elements.append(elem)
        
        if invalid_elements:
            return False, invalid_elements
        return True, None

    @staticmethod
    def _check_element_consistency(reactant_elements, product_elements):
        """Check if elements are consistent between reactants and products.
        
        Returns:
            tuple: (valid: bool, error_msg: str or None, allow_save: bool)
        """
        reactant_set = set(reactant_elements)
        product_set = set(product_elements)
        
        missing_in_products = reactant_set - product_set
        missing_in_reactants = product_set - reactant_set
        
        if missing_in_products or missing_in_reactants:
            error_msg = "Element mismatch: "
            if missing_in_products:
                error_msg += f"Missing in products: {', '.join(missing_in_products)}"
            if missing_in_reactants:
                if missing_in_products:
                    error_msg += "; "
                error_msg += f"Missing in reactants: {', '.join(missing_in_reactants)}"
            
            return False, error_msg, True  # Allow unbalanced equations
        
        return True, None, False

    @staticmethod
    def validate_reaction(reaction):
        """Validate reaction for real elements and element consistency"""
        try:
            # Split reaction by arrow
            reactants, products = ChemLabParser.split_reaction(reaction)
            if not reactants or not products:
                return {'valid': False, 'error': 'No valid arrow found'}
            
            # Extract elements from both sides
            reactant_elements = ChemLabParser.extract_elements_from_side(reactants)
            product_elements = ChemLabParser.extract_elements_from_side(products)
            
            # Check if all elements are real
            elements_valid, invalid_elements = ChemLabParser._validate_elements_exist(
                reactant_elements, product_elements
            )
            
            if not elements_valid:
                return {
                    'valid': False, 
                    'error': f'Invalid elements: {", ".join(invalid_elements)}'
                }
            
            # Check element consistency (LHS elements must be in RHS)
            consistency_valid, error_msg, allow_save = ChemLabParser._check_element_consistency(
                reactant_elements, product_elements
            )
            
            if not consistency_valid:
                return {
                    'valid': False, 
                    'error': error_msg,
                    'allow_save': allow_save
                }
            
            return {'valid': True, 'error': None}
            
        except Exception as e:
            return {'valid': False, 'error': f'Validation error: {str(e)}'}
    
    @staticmethod
    def extract_state_symbol(formula):
        """Extract state from compound formula and return (state, clean_formula)"""
        state_match = re.search(STATE_SYMBOL_PATTERN, formula)
        if state_match:
            state = state_match.group(1)
            clean_formula = re.sub(STATE_SYMBOL_PATTERN, '', formula)
            return state, clean_formula
        return '', formula
    
    @staticmethod
    def clean_formula(formula):
        """Remove coefficients from formula"""
        return re.sub(r'^\d+', '', formula)

    @staticmethod
    def auto_balance_reaction(reaction):
        """Auto-balance a chemical reaction using iterative coefficient finding"""
        logging.info(f"[BALANCE] Starting auto-balance for reaction: {reaction}")
        
        reactants_str, products_str = ChemLabParser.split_reaction(reaction)
        logging.info(f"[BALANCE] Split - reactants='{reactants_str}', products='{products_str}'")
        
        if not reactants_str or not products_str:
            logging.error("[BALANCE] Split failed - returning original")
            return reaction
        
        reactant_compounds = [c.strip() for c in reactants_str.split('+')]
        product_compounds = [c.strip() for c in products_str.split('+')]
        logging.info(f"[BALANCE] Parsed - reactants={reactant_compounds}, products={product_compounds}")
        
        all_elements = ChemLabParser._get_all_elements(reactant_compounds, product_compounds)
        logging.info(f"[BALANCE] Elements found: {all_elements}")
        
        if not all_elements:
            logging.error("[BALANCE] No elements found - returning original")
            return reaction
        
        reactant_counts = ChemLabParser._get_element_counts(reactant_compounds)
        product_counts = ChemLabParser._get_element_counts(product_compounds)
        logging.info(f"[BALANCE] Element counts - reactants={reactant_counts}, products={product_counts}")
        
        r_coeffs, p_coeffs = ChemLabParser._find_coefficients(
            reactant_counts, product_counts, all_elements
        )
        
        logging.info(f"[BALANCE] Found coefficients - r_coeffs={r_coeffs}, p_coeffs={p_coeffs}")
        
        if r_coeffs is None:
            logging.error("[BALANCE] Failed to find coefficients - returning original")
            return reaction
        
        result = ChemLabParser._build_balanced_reaction(
            reaction, reactant_compounds, product_compounds, r_coeffs, p_coeffs
        )
        logging.info(f"[BALANCE] Final balanced reaction: {result}")
        return result
    
    @staticmethod
    def _get_all_elements(reactant_compounds, product_compounds):
        """Extract all unique elements from compounds"""
        all_elements = set()
        for comp in reactant_compounds + product_compounds:
            elements = ChemLabParser.extract_elements_from_side(comp)
            all_elements.update(elements)
        return all_elements
    
    @staticmethod
    def _get_element_counts(compounds):
        """Get element counts for each compound"""
        counts = []
        for comp in compounds:
            comp_clean = re.sub(r'^\d+', '', comp)
            comp_clean = re.sub(r'\([a-z]+\)', '', comp_clean)
            parsed = ChemLabParser.parse_formula(comp_clean)
            counts.append(parsed)
        return counts
    
    @staticmethod
    def _build_augmented_matrix(reactant_counts, product_counts, elements, num_r, num_p):
        """Build augmented matrix for Gaussian elimination."""
        matrix = []
        for elem in elements:
            row = []
            # Reactants have positive coefficients
            for rc in reactant_counts:
                row.append(Fraction(rc.get(elem, 0)))
            # Products have negative coefficients
            for pc in product_counts:
                row.append(Fraction(-pc.get(elem, 0)))
            # RHS = 0 for element balance equations
            row.append(Fraction(0))
            matrix.append(row)
        
        # Add constraint row: first reactant = 1
        constraint_row = [Fraction(0)] * (num_r + num_p) + [Fraction(1)]
        if num_r > 0:
            constraint_row[0] = Fraction(1)
        matrix.append(constraint_row)
        
        return matrix

    @staticmethod
    def _convert_to_integers(r_coeffs_frac, p_coeffs_frac):
        """Convert fractional coefficients to integers by finding LCM of denominators."""
        all_fracs = r_coeffs_frac + p_coeffs_frac
        denominators = [f.denominator for f in all_fracs]
        common_denom = denominators[0]
        for d in denominators[1:]:
            common_denom = lcm(common_denom, d)
        
        r_coeffs = [int(f * common_denom) for f in r_coeffs_frac]
        p_coeffs = [int(f * common_denom) for f in p_coeffs_frac]
        
        return r_coeffs, p_coeffs, common_denom

    @staticmethod
    def _verify_coefficients(r_coeffs, p_coeffs, reactant_counts, product_counts, elements, num_r, num_p):
        """Verify that coefficients balance all elements."""
        for elem in elements:
            lhs = sum(r_coeffs[i] * reactant_counts[i].get(elem, 0) for i in range(num_r))
            rhs = sum(p_coeffs[i] * product_counts[i].get(elem, 0) for i in range(num_p))
            if lhs != rhs:
                logging.error(f"[FIND_COEFFS] Verification failed for {elem}: {lhs} != {rhs}")
                return False
        return True

    @staticmethod
    def _find_coefficients(reactant_counts, product_counts, all_elements):
        """Find balanced coefficients using matrix-based linear algebra approach."""
        elements = sorted(all_elements)
        num_r = len(reactant_counts)
        num_p = len(product_counts)
        num_vars = num_r + num_p
        
        logging.info(f"[FIND_COEFFS] Solving for {len(elements)} elements, {num_r} reactants, {num_p} products")
        logging.info(f"[FIND_COEFFS] Elements: {elements}")
        logging.info(f"[FIND_COEFFS] Reactant counts: {reactant_counts}")
        logging.info(f"[FIND_COEFFS] Product counts: {product_counts}")
        
        if num_vars < 2:
            return None, None
        
        matrix = ChemLabParser._build_augmented_matrix(reactant_counts, product_counts, elements, num_r, num_p)
        
        logging.info(f"[FIND_COEFFS] Augmented matrix: {len(matrix)} rows x {len(matrix[0])} cols")
        for i, row in enumerate(matrix):
            logging.info(f"[FIND_COEFFS] Row {i}: {[str(x) for x in row]}")
        
        solution = ChemLabParser._solve_linear_system(matrix, num_vars)
        logging.info(f"[FIND_COEFFS] Solution from solver: {solution}")
        
        if solution is None:
            logging.error("[FIND_COEFFS] Failed to solve linear system")
            return None, None
        
        r_coeffs_frac = [Fraction(solution[i]) for i in range(num_r)]
        p_coeffs_frac = [Fraction(solution[num_r + i]) for i in range(num_p)]
        
        r_coeffs, p_coeffs, common_denom = ChemLabParser._convert_to_integers(r_coeffs_frac, p_coeffs_frac)
        
        logging.info(f"[FIND_COEFFS] LCM of denominators: {common_denom}")
        logging.info(f"[FIND_COEFFS] Raw solution: r_coeffs={r_coeffs}, p_coeffs={p_coeffs}")
        
        if not ChemLabParser._verify_coefficients(r_coeffs, p_coeffs, reactant_counts, product_counts, elements, num_r, num_p):
            return None, None
        
        return ChemLabParser._simplify_coefficients(r_coeffs, p_coeffs)
    
    @staticmethod
    def _find_pivot_row(aug, col, start_row, num_rows):
        """Find pivot row with non-zero element in given column."""
        for r in range(start_row, num_rows):
            if aug[r][col] != 0:
                return r
        return None

    @staticmethod
    def _normalize_row(aug, row, col):
        """Normalize row so pivot element becomes 1."""
        pivot_val = aug[row][col]
        return [val / pivot_val for val in aug[row]]

    @staticmethod
    def _eliminate_column(aug, pivot_row, col, num_rows):
        """Eliminate column from all rows except pivot row."""
        for r in range(num_rows):
            if r != pivot_row and aug[r][col] != 0:
                factor = aug[r][col]
                aug[r] = [aug[r][c] - factor * aug[pivot_row][c] for c in range(len(aug[r]))]
        return aug

    @staticmethod
    def _extract_solution(aug, num_vars, num_rows):
        """Extract solution vector from reduced row echelon form."""
        solution = [Fraction(0)] * num_vars
        for r in range(num_rows):
            row = aug[r]
            # Find leading 1 (pivot)
            for c in range(num_vars):
                if row[c] == 1:
                    solution[c] = row[-1]
                    break
        return solution

    @staticmethod
    def _solve_linear_system(matrix, num_vars):
        """Solve linear system using Gaussian elimination with augmented matrix [A | b]."""
        logging.info(f"[SOLVE] Entering solver with {len(matrix)} rows, {num_vars} variables")
        
        if not matrix:
            return None
        
        num_rows = len(matrix)
        aug = [row[:] for row in matrix]
        
        logging.info("[SOLVE] Starting Gaussian elimination on augmented matrix")
        
        row = 0
        for col in range(num_vars):
            pivot_row = ChemLabParser._find_pivot_row(aug, col, row, num_rows)
            
            if pivot_row is None:
                logging.info(f"[SOLVE] No pivot found for column {col}, skipping")
                continue
            
            logging.info(f"[SOLVE] Pivot for col {col}: row {pivot_row}, value {aug[pivot_row][col]}")
            
            # Swap rows
            aug[row], aug[pivot_row] = aug[pivot_row], aug[row]
            
            # Normalize and eliminate
            aug[row] = ChemLabParser._normalize_row(aug, row, col)
            logging.info(f"[SOLVE] Normalized row {row}: {[str(x) for x in aug[row]]}")
            
            aug = ChemLabParser._eliminate_column(aug, row, col, num_rows)
            
            row += 1
            if row >= num_rows:
                break
        
        logging.info("[SOLVE] Elimination complete. Final augmented matrix:")
        for i, r in enumerate(aug):
            logging.info(f"[SOLVE] Row {i}: {[str(x) for x in r]}")
        
        solution = ChemLabParser._extract_solution(aug, num_vars, num_rows)
        
        logging.info(f"[SOLVE] Final solution: {[str(x) for x in solution]}")
        
        # Check if any coefficient is 0 or negative
        if any(s <= 0 for s in solution):
            logging.error("[SOLVE] ERROR: Invalid solution (zero or negative coefficients)")
            return None
        
        return solution
    
    @staticmethod
    def _simplify_coefficients(r_coeffs, p_coeffs):
        """Simplify coefficients by dividing by GCD"""
        all_coeffs = r_coeffs + p_coeffs
        common_gcd = int(reduce(gcd, all_coeffs))
        if common_gcd > 1:
            r_coeffs = [c // common_gcd for c in r_coeffs]
            p_coeffs = [c // common_gcd for c in p_coeffs]
        return r_coeffs, p_coeffs
    
    @staticmethod
    def _build_balanced_reaction(reaction, r_compounds, p_compounds, r_coeffs, p_coeffs):
        """Build the balanced reaction string"""
        arrow_used = ChemLabParser._get_arrow_used(reaction)
        r_side = ChemLabParser._format_side(r_compounds, r_coeffs)
        p_side = ChemLabParser._format_side(p_compounds, p_coeffs)
        return f"{r_side} {arrow_used} {p_side}"
    
    @staticmethod
    def _get_arrow_used(reaction):
        """Get the arrow used in the original reaction"""
        for arrow in ARROWS:
            if arrow in reaction:
                return arrow
        return '→'
    
    @staticmethod
    def _format_side(compounds, coeffs):
        """Format one side of the reaction with coefficients, preserving state symbols"""
        parts = []
        for i, comp in enumerate(compounds):
            coeff = coeffs[i]
            # Remove only leading coefficients, preserve state symbols
            comp_clean = re.sub(r'^\d+', '', comp)
            if coeff == 1:
                parts.append(comp_clean)
            else:
                parts.append(f"{coeff}{comp_clean}")
        return ' + '.join(parts)

    # ============================================================================
    # PARSING UTILITY METHODS (moved from ChemLab)
    # ============================================================================

    @staticmethod
    def normalize_formula(formula):
        """Normalize formula for lookup - remove coefficients, state symbols, convert to ASCII"""
        if not formula:
            return ''
        value = str(formula).strip()
        value = re.sub(r'^\d+', '', value)
        value = re.sub(STATE_SYMBOL_PATTERN, '', value)
        value = value.translate(SUBSCRIPT_MAP)
        return value.strip()

    @staticmethod
    def display_formula(formula):
        """Convert formula for display with Unicode subscripts (H2O → H₂O)"""
        if not formula:
            return ''
        value = str(formula).strip()
        value = re.sub(r'^\d+', '', value)  # Remove coefficients
        # Don't strip state symbols here - let them remain for display
        return value.translate(SUBSCRIPT_DISPLAY_MAP)

    @staticmethod
    def convert_arrows_to_unicode(text):
        """Convert keyboard arrows in text to Unicode arrows"""
        result = text
        for arrow, unicode_arrow in ARROW_MAP.items():
            result = result.replace(arrow, unicode_arrow)
        return result

    @staticmethod
    def parse_compound(compound):
        """Parse compound formula to extract clean formula and state info"""
        raw_formula = compound['formula']
        clean_formula = re.sub(r'^\d+', '', raw_formula)
        clean_formula = re.sub(STATE_SYMBOL_PATTERN, '', clean_formula)
        clean_formula = clean_formula.translate(SUBSCRIPT_MAP)

        state_match = re.search(STATE_SYMBOL_PATTERN, raw_formula)
        detected_state_abbr = state_match.group(1) if state_match else ''
        detected_state = STATE_NAMES.get(detected_state_abbr, '')
        return clean_formula, detected_state, detected_state_abbr

    @staticmethod
    def extract_elements_from_compounds(compounds):
        """Extract unique element symbols from compound formulas"""
        reaction_elements = set()
        for compound in compounds:
            formula = (compound.get('formula') or '').translate(SUBSCRIPT_MAP)
            formula = re.sub(STATE_SYMBOL_PATTERN, '', formula)
            matches = re.findall(r'[A-Z][a-z]?', formula)
            for match in matches:
                reaction_elements.add(match)
        return reaction_elements

    @staticmethod
    def get_state_display(compound):
        """Get display state name from compound data"""
        state_value = compound.get('state') or ''
        return STATE_NAMES.get(state_value, state_value)

    @staticmethod
    def load_elements_data(reaction_elements):
        """Load element data from mendeleev for given symbols"""
        elements_data = {}
        for elem_symbol in reaction_elements:
            elements_data[elem_symbol] = ChemLabParser._get_element_info(elem_symbol)
        return elements_data

    @staticmethod
    def _get_element_info(elem_symbol):
        """Get element info from mendeleev, return default if not found"""
        try:
            elem = element(elem_symbol)
            return {'name': elem.name, 'atomic_number': elem.atomic_number}
        except (ValueError, KeyError):
            return {'name': 'Unknown', 'atomic_number': 0}