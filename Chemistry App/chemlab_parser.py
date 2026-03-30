"""
ChemLab Parser - Handles all parsing and validation logic
"""

import re
from math import gcd
from functools import reduce
from mendeleev import element
from constants import ARROWS, SUBSCRIPT_MAP, STATE_SYMBOL_PATTERN

class ChemLabParser:
    """Handles reaction parsing, element extraction, and validation"""
    
    @staticmethod
    def has_arrow(reaction):
        """Check if reaction contains any arrow"""
        return any(arrow in reaction for arrow in ARROWS)
    
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
            except:
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
            invalid_elements = []
            all_elements = set(reactant_elements + product_elements)
            for elem in all_elements:
                try:
                    element(elem)  # Test if element exists
                except:
                    invalid_elements.append(elem)
            
            if invalid_elements:
                return {
                    'valid': False, 
                    'error': f'Invalid elements: {", ".join(invalid_elements)}'
                }
            
            # Check element consistency (LHS elements must be in RHS)
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
                
                return {
                    'valid': False, 
                    'error': error_msg,
                    'allow_save': True  # Allow unbalanced equations
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
        reactants_str, products_str = ChemLabParser.split_reaction(reaction)
        if not reactants_str or not products_str:
            return reaction
        
        reactant_compounds = [c.strip() for c in reactants_str.split('+')]
        product_compounds = [c.strip() for c in products_str.split('+')]
        
        all_elements = ChemLabParser._get_all_elements(reactant_compounds, product_compounds)
        if not all_elements:
            return reaction
        
        reactant_counts = ChemLabParser._get_element_counts(reactant_compounds)
        product_counts = ChemLabParser._get_element_counts(product_compounds)
        
        r_coeffs, p_coeffs = ChemLabParser._find_coefficients(
            reactant_counts, product_counts, all_elements
        )
        
        if r_coeffs is None:
            return reaction
        
        return ChemLabParser._build_balanced_reaction(
            reaction, reactant_compounds, product_compounds, r_coeffs, p_coeffs
        )
    
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
    def _find_coefficients(reactant_counts, product_counts, all_elements, max_coeff=20):
        """Find balanced coefficients using iterative approach"""
        r_coeffs = [1] * len(reactant_counts)
        p_coeffs = [1] * len(product_counts)
        
        for _ in range(100):
            balanced, r_coeffs, p_coeffs = ChemLabParser._check_and_adjust(
                r_coeffs, p_coeffs, reactant_counts, product_counts, all_elements, max_coeff
            )
            if balanced:
                return ChemLabParser._simplify_coefficients(r_coeffs, p_coeffs)
        
        return None, None
    
    @staticmethod
    def _check_and_adjust(r_coeffs, p_coeffs, r_counts, p_counts, elements, max_coeff):
        """Check balance and adjust coefficients if needed"""
        for elem in elements:
            lhs = sum(r_coeffs[i] * r_counts[i].get(elem, 0) for i in range(len(r_counts)))
            rhs = sum(p_coeffs[i] * p_counts[i].get(elem, 0) for i in range(len(p_counts)))
            
            if lhs != rhs:
                if lhs == 0 or rhs == 0:
                    return False, r_coeffs, p_coeffs
                
                if lhs < rhs:
                    r_coeffs = ChemLabParser._increase_coefficient(r_coeffs, r_counts, elem, max_coeff)
                else:
                    p_coeffs = ChemLabParser._increase_coefficient(p_coeffs, p_counts, elem, max_coeff)
                return False, r_coeffs, p_coeffs
        
        return True, r_coeffs, p_coeffs
    
    @staticmethod
    def _increase_coefficient(coeffs, counts, element, max_coeff):
        """Increase coefficient for compound containing the element"""
        new_coeffs = coeffs[:]
        for i in range(len(coeffs)):
            if counts[i].get(element, 0) > 0 and coeffs[i] < max_coeff:
                new_coeffs[i] += 1
                break
        return new_coeffs
    
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
