"""
SQLite Database Manager for ChemLab Application
Manages chemical reactions, elements, and compounds storage
"""

import sqlite3
import logging
from typing import Dict, List
from constants import DEFAULT_REACTION_TYPE


class ChemLabDatabase:
    """Manages SQLite database operations for chemistry data."""

    def __init__(self, db_path: str):
        self.db_path = db_path
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
            logging.info("ChemLab database initialized successfully")
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

        self.connection.commit()

    def _create_indexes(self):
        """Create database indexes for better performance."""
        cursor = self.connection.cursor()

        cursor.execute('CREATE INDEX IF NOT EXISTS idx_reactions_text ON reactions(reaction_text)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_elements_symbol ON elements(symbol)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_compounds_reaction_id ON compounds(reaction_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_compounds_formula ON compounds(formula)')

        self.connection.commit()

    def add_reaction(self, reaction_text: str, reaction_type: str = 'Unknown') -> int:
        """Add a new reaction to the database."""
        cursor = self.connection.cursor()

        try:
            cursor.execute('''
                INSERT INTO reactions (reaction_text, reaction_type)
                VALUES (?, ?)
            ''', (reaction_text, reaction_type))

            reaction_id = cursor.lastrowid
            self.connection.commit()
            self.optimize_database()
            logging.info(f"Added reaction with ID: {reaction_id}")
            return reaction_id

        except Exception as e:
            self.connection.rollback()
            logging.error(f"Failed to add reaction: {e}")
            raise

    def get_all_reactions(self) -> List[Dict]:
        """Get all reactions from the database."""
        cursor = self.connection.cursor()

        try:
            cursor.execute('SELECT * FROM reactions ORDER BY id ASC')
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
            logging.info(f"Deleted reaction with ID: {reaction_id}")
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
            logging.info(f"Added compound with ID: {compound_id}")
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
                logging.info(f"Updated compound with ID: {compound_id}")
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
            logging.info(f"Deleted compounds for reaction {reaction_id}")
            return True
        except Exception as e:
            self.connection.rollback()
            logging.error(f"Failed to delete compounds for reaction {reaction_id}: {e}")
            return False

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
    
    def update_reaction(self, reaction_id: int, reaction_text: str, reaction_type: str) -> bool:
        """Update an existing reaction"""
        cursor = self.connection.cursor()
        
        try:
            cursor.execute('''
                UPDATE reactions 
                SET reaction_text = ?, reaction_type = ?
                WHERE id = ?
            ''', (reaction_text, reaction_type, reaction_id))
            
            self.connection.commit()
            self.optimize_database()
            logging.info(f"Updated reaction with ID: {reaction_id}")
            return True
            
        except Exception as e:
            self.connection.rollback()
            logging.error(f"Failed to update reaction {reaction_id}: {e}")
            return False


    def close(self):
        """Close database connection."""
        try:
            if self.connection:
                self.connection.close()
                logging.info("ChemLab database connection closed")
        except Exception as e:
            logging.error(f"Error closing database: {e}")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
