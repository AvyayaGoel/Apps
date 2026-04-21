"""
SQLite Database Manager for ChemLab Application
Manages chemical reactions, elements, and compounds storage
"""

import logging
import os
import sqlite3
from typing import Dict, List, Optional

from constants import DEFAULT_REACTION_TYPE


class ChemLabDatabase:
    """Manages SQLite database operations for chemistry data."""

    @staticmethod
    def get_default_db_path():
        """Get the default database path in Local AppData.
        
        Creates the ChemLab Data folder if it doesn't exist.
        """
        # Get Local AppData path
        local_appdata = os.environ.get('LOCALAPPDATA')
        if not local_appdata:
            # Fallback to user home if env var not set
            local_appdata = os.path.expanduser('~')

        # Create ChemLab Data folder
        chemlab_folder = os.path.join(local_appdata, 'ChemLab Data')
        os.makedirs(chemlab_folder, exist_ok=True)

        # Return full db path
        return os.path.join(chemlab_folder, 'chemlab_data.db')

    def __init__(self):
        """Initialize the database."""

        self.db_path = self.get_default_db_path()
        self.connection = None
        self._initialize_database()

    def _initialize_database(self):
        """Initialize database connection and create tables if they don't exist."""
        try:
            self.connection = sqlite3.connect(self.db_path, check_same_thread=False)
            self.connection.row_factory = sqlite3.Row  # Enable dict-like access

            # Enable foreign key constraints
            cursor = self.connection.cursor()
            cursor.execute("PRAGMA foreign_keys = ON")
            self.connection.commit()

            self._create_tables()
            self._create_indexes()
        except Exception as e:
            logging.error(f"Failed to initialize ChemLab database: {e}")
            raise

    def _create_tables(self):
        """Create necessary database tables."""
        cursor = self.connection.cursor()

        # Reactions table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS reactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                reaction_text TEXT NOT NULL,
                reaction_type TEXT DEFAULT 'Unknown',
                heat_value REAL,
                heat_type TEXT,
                temperature TEXT,
                temperature_unit TEXT,
                pressure TEXT,
                pressure_unit TEXT,
                catalyst TEXT,
                is_favorite INTEGER DEFAULT 0,
                favorite_at TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # Elements table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS elements (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol TEXT UNIQUE NOT NULL,
                name TEXT NOT NULL,
                atomic_number INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # Compounds table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS compounds (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                reaction_id INTEGER NOT NULL,
                formula TEXT NOT NULL,
                type TEXT NOT NULL,
                name TEXT,
                color TEXT,
                state TEXT,
                notes TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (reaction_id) REFERENCES reactions (id) ON DELETE CASCADE
            )
        ''')

        # Saved compound names from PubChem
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS saved_compounds (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                formula TEXT UNIQUE NOT NULL,
                common_name TEXT NOT NULL,
                iupac_name TEXT,
                cid INTEGER,
                molecular_weight REAL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # Tags table for reaction tags (many-to-many relationship)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS reaction_tags (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                reaction_id INTEGER NOT NULL,
                tag TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (reaction_id) REFERENCES reactions (id) ON DELETE CASCADE,
                UNIQUE(reaction_id, tag)
            )
        ''')

        self.connection.commit()

    def _create_indexes(self):
        """Create database indexes for better performance."""
        cursor = self.connection.cursor()

        cursor.execute('CREATE INDEX IF NOT EXISTS idx_reactions_text ON reactions(reaction_text)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_elements_symbol ON elements(symbol)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_compounds_reaction_id ON compounds(reaction_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_compounds_formula ON compounds(formula)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_saved_compounds_formula ON saved_compounds(formula)')

        self.connection.commit()

    def add_reaction(self, reaction_text: str, reaction_type: str = 'Unknown',
                     heat_value: float = None, heat_type: str = None,
                     temperature: str = None, temperature_unit: str = None,
                     pressure: str = None, pressure_unit: str = None,
                     catalyst: str = None, notes: str = None) -> int:
        """Add a new reaction to the database."""
        cursor = self.connection.cursor()

        try:
            cursor.execute('''
                INSERT INTO reactions (reaction_text, reaction_type, heat_value, heat_type,
                                     temperature, temperature_unit, pressure, pressure_unit, catalyst, notes)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (reaction_text, reaction_type, heat_value, heat_type,
                  temperature, temperature_unit, pressure, pressure_unit, catalyst, notes))

            reaction_id = cursor.lastrowid
            self.connection.commit()
            self.optimize_database()
            return reaction_id

        except Exception as e:
            self.connection.rollback()
            logging.error(f"Failed to add reaction: {e}")
            raise

    def get_reaction_by_id(self, reaction_id: int) -> Optional[Dict]:
        """Get a specific reaction by ID."""
        cursor = self.connection.cursor()
        try:
            cursor.execute('SELECT * FROM reactions WHERE id = ?', (reaction_id,))
            row = cursor.fetchone()
            return dict(row) if row else None
        except Exception as e:
            logging.error(f"Failed to get reaction by id {reaction_id}: {e}")
            return None

    def get_all_reactions(self) -> List[Dict]:
        """Get all reactions from the database, favorites first (by favorite_at time)."""
        cursor = self.connection.cursor()

        try:
            cursor.execute('''
                SELECT * FROM reactions
                ORDER BY is_favorite DESC,
                         favorite_at ASC,
                         id ASC
            ''')
            reaction_rows = cursor.fetchall()
            return [dict(row) for row in reaction_rows]

        except Exception as e:
            logging.error(f"Failed to get all reactions: {e}")
            return []

    def delete_reaction(self, reaction_id: int) -> bool:
        """Delete a reaction and its associated compounds."""
        cursor = self.connection.cursor()

        try:
            # Delete reaction (CASCADE will automatically delete compounds)
            cursor.execute('DELETE FROM reactions WHERE id = ?', (reaction_id,))

            self.connection.commit()
            self.optimize_database()
            return True

        except Exception as e:
            self.connection.rollback()
            logging.error(f"Failed to delete reaction {reaction_id}: {e}")
            return False

    def add_or_update_element(self, symbol: str, name: str, atomic_number: int) -> int:
        """Add an element or update if it exists."""
        cursor = self.connection.cursor()

        try:
            # Check if element exists
            cursor.execute('SELECT id FROM elements WHERE symbol = ?', (symbol,))
            existing = cursor.fetchone()

            if existing:
                # Update existing element
                cursor.execute('''
                    UPDATE elements 
                    SET name = ?, atomic_number = ?
                    WHERE symbol = ?
                ''', (name, atomic_number, symbol))
                element_id = existing['id']
            else:
                # Insert new element
                cursor.execute('''
                    INSERT INTO elements (symbol, name, atomic_number)
                    VALUES (?, ?, ?)
                ''', (symbol, name, atomic_number))
                element_id = cursor.lastrowid

            self.connection.commit()
            self.optimize_database()
            return element_id

        except Exception as e:
            self.connection.rollback()
            logging.error(f"Failed to add/update element {symbol}: {e}")
            raise

    def add_compound(self, reaction_id: int, formula: str, compound_type: str,
                     name: str = None, color: str = None, state: str = None,
                     notes: str = None) -> int:
        """Add a compound to the database."""
        cursor = self.connection.cursor()

        try:
            cursor.execute('''
                INSERT INTO compounds (reaction_id, formula, type, name, color, state, notes)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (reaction_id, formula, compound_type, name, color, state, notes))

            compound_id = cursor.lastrowid
            self.connection.commit()
            self.optimize_database()
            return compound_id

        except Exception as e:
            self.connection.rollback()
            logging.error(f"Failed to add compound: {e}")
            raise

    def get_compounds_for_reaction(self, reaction_id: int) -> List[Dict]:
        """Get all compounds for a specific reaction."""
        cursor = self.connection.cursor()

        try:
            cursor.execute('SELECT * FROM compounds WHERE reaction_id = ? ORDER BY id', (reaction_id,))
            compound_rows = cursor.fetchall()
            return [dict(row) for row in compound_rows]

        except Exception as e:
            logging.error(f"Failed to get compounds for reaction {reaction_id}: {e}")
            return []

    def get_all_compounds(self) -> List[Dict]:
        """Get all compounds from the database for learning."""
        cursor = self.connection.cursor()

        try:
            cursor.execute('SELECT * FROM compounds ORDER BY id')
            compound_rows = cursor.fetchall()
            return [dict(row) for row in compound_rows]

        except Exception as e:
            logging.error(f"Failed to get all compounds: {e}")
            return []

    def update_compound(self, compound_id: int, name: str = None, color: str = None,
                        state: str = None, notes: str = None) -> bool:
        """Update compound details."""
        cursor = self.connection.cursor()

        try:
            updates = []
            params = []

            if name is not None:
                updates.append("name = ?")
                params.append(name)
            if color is not None:
                updates.append("color = ?")
                params.append(color)
            if state is not None:
                updates.append("state = ?")
                params.append(state)
            if notes is not None:
                updates.append("notes = ?")
                params.append(notes)

            if updates:
                params.append(compound_id)

                cursor.execute(f'''
                    UPDATE compounds 
                    SET {', '.join(updates)}
                    WHERE id = ?
                ''', params)

                self.connection.commit()
                self.optimize_database()
                return True

            return False

        except Exception as e:
            self.connection.rollback()
            logging.error(f"Failed to update compound {compound_id}: {e}")
            return False

    def delete_compounds_for_reaction(self, reaction_id: int) -> bool:
        """Delete all compounds for a specific reaction"""
        cursor = self.connection.cursor()

        try:
            cursor.execute('DELETE FROM compounds WHERE reaction_id = ?', (reaction_id,))
            self.connection.commit()
            return True
        except Exception as e:
            self.connection.rollback()
            logging.error(f"Failed to delete compounds for reaction {reaction_id}: {e}")
            return False

    def get_reaction_compounds(self, reaction_id: int) -> List[Dict]:
        """Get all compounds for a specific reaction"""
        cursor = self.connection.cursor()
        try:
            cursor.execute('''
                SELECT formula, compound_type, name, state, color
                FROM compounds
                WHERE reaction_id = ?
                ORDER BY id
            ''', (reaction_id,))
            rows = cursor.fetchall()
            return [
                {
                    'formula': row[0],
                    'type': row[1],
                    'name': row[2] or '',
                    'state': row[3] or '',
                    'color': row[4] or ''
                }
                for row in rows
            ]
        except Exception as e:
            logging.error(f"Failed to get compounds for reaction {reaction_id}: {e}")
            return []

    def get_all_reaction_types(self) -> List[str]:
        """Get all unique reaction types from database"""
        cursor = self.connection.cursor()

        try:
            cursor.execute('''
                SELECT DISTINCT reaction_type 
                FROM reactions 
                WHERE reaction_type != ? 
                ORDER BY reaction_type
            ''', (DEFAULT_REACTION_TYPE,))

            types = [row[0] for row in cursor.fetchall()]
            return types

        except Exception as e:
            logging.error(f"Failed to get reaction types: {e}")
            return []

    def optimize_database(self):
        """Optimize the database"""
        try:
            self.connection.execute('VACUUM')

        except Exception as e:
            logging.error(f"Failed to optimize database: {e}")

    def get_elements_for_reaction(self, reaction_id: int) -> List[Dict]:
        """Get all elements for a specific reaction"""
        cursor = self.connection.cursor()

        try:
            cursor.execute('''
                SELECT DISTINCT e.symbol, e.name, e.atomic_number
                FROM elements e
                JOIN compounds c ON c.formula LIKE '%' || e.symbol || '%'
                WHERE c.reaction_id = ?
                ORDER BY e.atomic_number
            ''', (reaction_id,))

            element_rows = cursor.fetchall()
            return [dict(row) for row in element_rows]

        except Exception as e:
            logging.error(f"Failed to get elements for reaction {reaction_id}: {e}")
            return []

    def update_reaction(self, reaction_id: int, reaction_text: str, reaction_type: str,
                        heat_value: float = None, heat_type: str = None,
                        temperature: str = None, temperature_unit: str = None,
                        pressure: str = None, pressure_unit: str = None,
                        catalyst: str = None, notes: str = None) -> bool:
        """Update an existing reaction"""
        cursor = self.connection.cursor()

        try:
            cursor.execute('''
                UPDATE reactions 
                SET reaction_text = ?, reaction_type = ?, heat_value = ?, heat_type = ?,
                    temperature = ?, temperature_unit = ?, pressure = ?, pressure_unit = ?, catalyst = ?, notes = ?
                WHERE id = ?
            ''', (reaction_text, reaction_type, heat_value, heat_type,
                  temperature, temperature_unit, pressure, pressure_unit, catalyst, notes, reaction_id))

            self.connection.commit()
            self.optimize_database()
            return True

        except Exception as e:
            self.connection.rollback()
            logging.error(f"Failed to update reaction {reaction_id}: {e}")
            return False

    def toggle_reaction_favorite(self, reaction_id: int) -> bool:
        """Toggle favorite status of a reaction. Returns new favorite status."""
        cursor = self.connection.cursor()

        try:
            # Get current status
            cursor.execute('SELECT is_favorite FROM reactions WHERE id = ?', (reaction_id,))
            row = cursor.fetchone()
            if not row:
                return False

            current_status = row[0] if row else 0
            new_status = 0 if current_status else 1

            if new_status:
                # Setting as favorite - set favorite_at timestamp
                cursor.execute('''
                    UPDATE reactions 
                    SET is_favorite = 1, favorite_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                ''', (reaction_id,))
            else:
                # Unfavoriting - clear favorite_at
                cursor.execute('''
                    UPDATE reactions 
                    SET is_favorite = 0, favorite_at = NULL
                    WHERE id = ?
                ''', (reaction_id,))

            self.connection.commit()
            return bool(new_status)

        except Exception as e:
            logging.error(f"Failed to toggle favorite for reaction {reaction_id}: {e}")
            return False

    def get_reaction_heat_data(self, reaction_id: int) -> dict:
        """Get heat value and type for a specific reaction."""
        cursor = self.connection.cursor()
        try:
            cursor.execute(
                "SELECT heat_value, heat_type FROM reactions WHERE id = ?",
                (reaction_id,)
            )
            row = cursor.fetchone()
            if row:
                return {'heat_value': row[0], 'heat_type': row[1]}
            return {'heat_value': None, 'heat_type': None}
        except Exception as e:
            logging.error(f"Failed to get heat data for reaction {reaction_id}: {e}")
            return {'heat_value': None, 'heat_type': None}

    def get_reaction_conditions(self, reaction_id: int) -> dict:
        """Get temperature, pressure, catalyst, and notes for a specific reaction."""
        cursor = self.connection.cursor()
        try:
            cursor.execute(
                "SELECT temperature, temperature_unit, pressure, pressure_unit, catalyst, notes FROM reactions WHERE id = ?",
                (reaction_id,)
            )
            row = cursor.fetchone()
            if row:
                return {'temperature': row[0], 'temperature_unit': row[1],
                        'pressure': row[2], 'pressure_unit': row[3],
                        'catalyst': row[4], 'notes': row[5]}
            return {'temperature': None, 'temperature_unit': None,
                    'pressure': None, 'pressure_unit': None, 'catalyst': None, 'notes': None}
        except Exception as e:
            logging.error(f"Failed to get reaction conditions for reaction {reaction_id}: {e}")
            return {'temperature': None, 'temperature_unit': None,
                    'pressure': None, 'pressure_unit': None, 'catalyst': None, 'notes': None}

    def get_total_reaction_count(self) -> int:
        """Get total count of all reactions in the database."""
        cursor = self.connection.cursor()
        try:
            cursor.execute('SELECT COUNT(*) FROM reactions')
            result = cursor.fetchone()
            return result[0] if result else 0
        except Exception as e:
            logging.error(f"Failed to get total reaction count: {e}")
            return 0

    def get_reaction_counts_by_type(self) -> List[tuple]:
        """Get count of reactions grouped by type, sorted by count descending."""
        cursor = self.connection.cursor()
        try:
            cursor.execute('''
                SELECT reaction_type, COUNT(*) as count
                FROM reactions
                GROUP BY reaction_type
                ORDER BY count DESC, reaction_type ASC
            ''')
            return [(row[0], row[1]) for row in cursor.fetchall()]
        except Exception as e:
            logging.error(f"Failed to get reaction counts by type: {e}")
            return []

    def get_reaction_counts_by_heat_type(self) -> dict:
        """Get count of reactions by heat type (exothermic/endothermic)."""
        cursor = self.connection.cursor()
        try:
            cursor.execute('''
                SELECT 
                    SUM(CASE WHEN LOWER(heat_type) = 'exothermic' THEN 1 ELSE 0 END) as exothermic,
                    SUM(CASE WHEN LOWER(heat_type) = 'endothermic' THEN 1 ELSE 0 END) as endothermic
                FROM reactions
            ''')
            row = cursor.fetchone()
            return {
                'exothermic': row[0] or 0,
                'endothermic': row[1] or 0
            }
        except Exception as e:
            logging.error(f"Failed to get reaction counts by heat type: {e}")
            return {'exothermic': 0, 'endothermic': 0}

    def close(self):
        """Close database connection."""
        try:
            if self.connection:
                self.connection.close()
        except Exception as e:
            logging.error(f"Error closing database: {e}")

    def add_compound_name(self, formula: str, common_name: str, iupac_name: str = None,
                          cid: int = None, molecular_weight: float = None) -> int:
        """Add a saved compound name from PubChem lookup."""
        cursor = self.connection.cursor()
        try:
            cursor.execute('''
                INSERT OR REPLACE INTO saved_compounds
                (formula, common_name, iupac_name, cid, molecular_weight)
                VALUES (?, ?, ?, ?, ?)
            ''', (formula, common_name, iupac_name, cid, molecular_weight))
            self.connection.commit()
            return cursor.lastrowid
        except Exception as e:
            self.connection.rollback()
            logging.error(f"Failed to add compound name: {e}")
            raise

    def get_compound_by_formula(self, formula: str):
        """Get saved compound info by formula."""
        cursor = self.connection.cursor()
        try:
            cursor.execute('''
                SELECT formula, common_name, iupac_name, cid, molecular_weight
                FROM saved_compounds
                WHERE formula = ?
            ''', (formula,))
            row = cursor.fetchone()
            return dict(row) if row else None
        except Exception as e:
            logging.error(f"Failed to get compound: {e}")
            return None

    # Tag management methods
    def add_tag_to_reaction(self, reaction_id: int, tag: str) -> bool:
        """Add a tag to a reaction. Returns True if added, False if already exists."""
        cursor = self.connection.cursor()
        try:
            cursor.execute('''
                INSERT OR IGNORE INTO reaction_tags (reaction_id, tag)
                VALUES (?, ?)
            ''', (reaction_id, tag.lower().strip()))
            self.connection.commit()
            return cursor.rowcount > 0
        except Exception as e:
            logging.error(f"Failed to add tag '{tag}' to reaction {reaction_id}: {e}")
            return False

    def remove_tag_from_reaction(self, reaction_id: int, tag: str) -> bool:
        """Remove a tag from a reaction."""
        cursor = self.connection.cursor()
        try:
            cursor.execute('''
                DELETE FROM reaction_tags WHERE reaction_id = ? AND tag = ?
            ''', (reaction_id, tag.lower().strip()))
            self.connection.commit()
            return cursor.rowcount > 0
        except Exception as e:
            logging.error(f"Failed to remove tag '{tag}' from reaction {reaction_id}: {e}")
            return False

    def get_tags_for_reaction(self, reaction_id: int) -> List[str]:
        """Get all tags for a specific reaction."""
        cursor = self.connection.cursor()
        try:
            cursor.execute('''
                SELECT tag FROM reaction_tags WHERE reaction_id = ? ORDER BY tag
            ''', (reaction_id,))
            rows = cursor.fetchall()
            return [row[0] for row in rows]
        except Exception as e:
            logging.error(f"Failed to get tags for reaction {reaction_id}: {e}")
            return []

    def delete_tags_for_reaction(self, reaction_id: int) -> bool:
        """Delete all tags for a reaction (used when updating)."""
        cursor = self.connection.cursor()
        try:
            cursor.execute('DELETE FROM reaction_tags WHERE reaction_id = ?', (reaction_id,))
            self.connection.commit()
            return True
        except Exception as e:
            logging.error(f"Failed to delete tags for reaction {reaction_id}: {e}")
            return False

    def get_all_unique_tags(self) -> List[str]:
        """Get all unique tags across all reactions."""
        cursor = self.connection.cursor()
        try:
            cursor.execute('SELECT DISTINCT tag FROM reaction_tags ORDER BY tag')
            rows = cursor.fetchall()
            return [row[0] for row in rows]
        except Exception as e:
            logging.error(f"Failed to get all tags: {e}")
            return []

    def search_reactions_by_tag(self, tag: str) -> List[int]:
        """Get reaction IDs that have a tag matching the search (partial match)."""
        cursor = self.connection.cursor()
        try:
            cursor.execute('''
                SELECT reaction_id FROM reaction_tags WHERE tag LIKE ?
            ''', (f'%{tag.lower().strip()}%',))
            rows = cursor.fetchall()
            return [row[0] for row in rows]
        except Exception as e:
            logging.error(f"Failed to search reactions by tag '{tag}': {e}")
            return []

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
