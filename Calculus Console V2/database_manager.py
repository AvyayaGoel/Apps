"""
SQLite Database Manager for Formula Sheet Application (PyQt6 version)
Replaces JSON file-based storage with SQLite for better performance and scalability
"""

import logging
import shutil
import sqlite3
from typing import Dict, List, Optional


class DatabaseManager:
    """Manages SQLite database operations for formula storage."""

    # SQL query constants
    DELETE_VARIABLES_QUERY = 'DELETE FROM variables WHERE formula_id = ?'

    def __init__(self, db_path: str):
        self.db_path = db_path
        self.connection = None
        self._operation_count = 0
        self._initialize_database()

    def _initialize_database(self):
        """Initialize database connection and create tables if they don't exist."""
        try:
            self.connection = sqlite3.connect(self.db_path, check_same_thread=False)
            self.connection.row_factory = sqlite3.Row  # Enable dict-like access
            self._create_tables()
            self._create_indexes()
            logging.info("Database initialized successfully")
        except Exception as e:
            logging.error(f"Failed to initialize database: {e}")
            raise

    def _create_tables(self):
        """Create necessary database tables."""
        cursor = self.connection.cursor()

        # Main formulas table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS formulas (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                formula_text TEXT NOT NULL,
                field TEXT NOT NULL,
                topic TEXT NOT NULL,
                sub_topic TEXT DEFAULT '_GENERAL_',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # Variables table for formula variables
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS variables (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                formula_id INTEGER NOT NULL,
                symbol TEXT NOT NULL,
                name TEXT NOT NULL,
                unit TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (formula_id) REFERENCES formulas (id) ON DELETE CASCADE
            )
        ''')

        # Migration tracking table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS migration_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                migration_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                source_format TEXT,
                records_migrated INTEGER,
                status TEXT
            )
        ''')

        self.connection.commit()

        # Run database migrations
        self._run_migrations()

    def _run_migrations(self):
        """Run database migrations to ensure schema is up to date."""
        cursor = self.connection.cursor()

        try:
            # Check if updated_at column exists in formulas table
            cursor.execute("PRAGMA table_info(formulas)")
            columns = [column[1] for column in cursor.fetchall()]

            if 'updated_at' not in columns:
                logging.info("Adding missing updated_at column to formulas table")
                # Add column without default (SQLite limitation)
                cursor.execute('ALTER TABLE formulas ADD COLUMN updated_at TIMESTAMP')
                # Update existing rows to have current timestamp as updated_at
                cursor.execute('UPDATE formulas SET updated_at = created_at WHERE updated_at IS NULL')
                self.connection.commit()
                logging.info("Successfully added updated_at column")

        except Exception as e:
            logging.error(f"Migration failed: {e}")
            self.connection.rollback()
            raise

    def _create_indexes(self):
        """Create database indexes for better performance."""
        cursor = self.connection.cursor()

        # Indexes for faster searching
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_formulas_field ON formulas(field)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_formulas_topic ON formulas(topic)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_formulas_sub_topic ON formulas(sub_topic)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_formulas_text ON formulas(formula_text)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_variables_formula_id ON variables(formula_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_variables_symbol ON variables(symbol)')

        self.connection.commit()

    def add_formula(self, formula_text: str, field: str, topic: str,
                    sub_topic: str = "_GENERAL_", variables: List[Dict] = None) -> int:
        """Add a new formula to the database."""
        cursor = self.connection.cursor()

        try:
            cursor.execute('''
                INSERT INTO formulas (formula_text, field, topic, sub_topic)
                VALUES (?, ?, ?, ?)
            ''', (formula_text, field, topic, sub_topic))

            formula_id = cursor.lastrowid

            # Add variables if provided
            if variables:
                self.add_variables(formula_id, variables)

            self.connection.commit()
            logging.info(f"Added formula with ID: {formula_id}")
            return formula_id

        except sqlite3.OperationalError as e:
            self.connection.rollback()
            logging.warning(f"Database locked during formula addition: {e}")
            raise
        except Exception as e:
            self.connection.rollback()
            logging.error(f"Failed to add formula: {e}")
            raise

    def update_formula(self, formula_id: int, formula_text: str, field: str,
                       topic: str, sub_topic: str = "_GENERAL_",
                       variables: List[Dict] = None) -> bool:
        """Update an existing formula."""
        cursor = self.connection.cursor()

        try:
            cursor.execute('''
                UPDATE formulas 
                SET formula_text = ?, field = ?, topic = ?, sub_topic = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            ''', (formula_text, field, topic, sub_topic, formula_id))

            # Update variables if provided
            if variables is not None:
                self.delete_variables(formula_id)
                self.add_variables(formula_id, variables)

            self.connection.commit()

            # Increment operation count for vacuum tracking
            if not hasattr(self, '_operation_count'):
                self._operation_count = 0
            self._operation_count += 1

            # Check if we should vacuum after this operation
            if self._operation_count % 3 == 0:
                try:
                    self.connection.execute('VACUUM')
                    logging.info("Post-operation VACUUM completed")
                except Exception as e:
                    logging.warning(f"Post-operation VACUUM failed: {e}")

            logging.info(f"Updated formula with ID: {formula_id}")
            return True

        except sqlite3.OperationalError as e:
            self.connection.rollback()
            logging.warning(f"Database locked during formula update: {e}")
            return False
        except Exception as e:
            self.connection.rollback()
            logging.error(f"Failed to update formula {formula_id}: {e}")
            return False

    def delete_formula(self, formula_id: int) -> bool:
        """Delete a formula and its variables, then renumber remaining formulas."""
        cursor = self.connection.cursor()

        try:
            # Delete variables first (foreign key dependency)
            cursor.execute(self.DELETE_VARIABLES_QUERY, (formula_id,))
            # Then delete the formula
            cursor.execute('DELETE FROM formulas WHERE id = ?', (formula_id,))

            # Renumber remaining formulas to be sequential
            cursor.execute('SELECT * FROM formulas ORDER BY id')
            remaining_formulas = cursor.fetchall()

            if remaining_formulas:
                # Create a completely new table structure
                cursor.execute('DROP TABLE IF EXISTS temp_formulas')
                cursor.execute('''
                    CREATE TABLE temp_formulas (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        formula_text TEXT NOT NULL,
                        field TEXT NOT NULL,
                        topic TEXT NOT NULL,
                        sub_topic TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                ''')

                # Insert data with new sequential IDs (let AUTOINCREMENT handle it)
                old_to_new_ids = {}
                for i, formula in enumerate(remaining_formulas, 1):
                    old_id = formula[0]
                    cursor.execute('''
                        INSERT INTO temp_formulas (formula_text, field, topic, sub_topic, created_at, updated_at)
                        VALUES (?, ?, ?, ?, ?, ?)
                    ''', (formula[1], formula[2], formula[3], formula[4], formula[5],
                          formula[6] if len(formula) > 6 else None))
                    # Get the new ID that was assigned
                    new_id = cursor.lastrowid
                    old_to_new_ids[old_id] = new_id

                # Update variables with new formula IDs
                for old_id, new_id in old_to_new_ids.items():
                    cursor.execute('''
                        UPDATE variables SET formula_id = ? WHERE formula_id = ?
                    ''', (new_id, old_id))

                # Replace the old table completely
                cursor.execute('DROP TABLE formulas')
                cursor.execute('ALTER TABLE temp_formulas RENAME TO formulas')

                # Explicitly reset the AUTOINCREMENT sequence to match the count
                cursor.execute('DELETE FROM sqlite_sequence WHERE name = "formulas"')
                cursor.execute('INSERT INTO sqlite_sequence (name, seq) VALUES (?, ?)',
                               ('formulas', len(remaining_formulas)))

            self.connection.commit()
            logging.info(
                f"Deleted formula with ID: {formula_id} and its variables, then renumbered {len(remaining_formulas)} remaining formulas")
            return True

        except sqlite3.OperationalError as e:
            self.connection.rollback()
            logging.warning(f"Database locked during formula deletion: {e}")
            return False
        except Exception as e:
            self.connection.rollback()
            logging.error(f"Failed to delete formula {formula_id}: {e}")
            return False

    def get_formula(self, formula_id: int) -> Optional[Dict]:
        """Get a single formula by ID."""
        cursor = self.connection.cursor()

        try:
            cursor.execute('SELECT * FROM formulas WHERE id = ?', (formula_id,))
            formula_row = cursor.fetchone()

            if formula_row:
                formula = dict(formula_row)
                formula['variables'] = self.get_variables(formula_id)
                return formula

            return None

        except Exception as e:
            logging.error(f"Failed to get formula {formula_id}: {e}")
            return None

    def get_all_formulas(self) -> List[Dict]:
        """Get all formulas with their variables."""
        cursor = self.connection.cursor()

        try:
            cursor.execute('SELECT * FROM formulas ORDER BY id')
            formula_rows = cursor.fetchall()

            formulas = []
            for row in formula_rows:
                formula = dict(row)
                formula['variables'] = self.get_variables(formula['id'])
                formulas.append(formula)

            return formulas

        except Exception as e:
            logging.error(f"Failed to get all formulas: {e}")
            return []

    def add_variables(self, formula_id: int, variables: List[Dict]):
        """Add variables for a formula."""
        cursor = self.connection.cursor()

        try:
            for var in variables:
                cursor.execute('''
                    INSERT INTO variables (formula_id, symbol, name, unit)
                    VALUES (?, ?, ?, ?)
                ''', (formula_id, var['symbol'], var['name'], var.get('unit', '')))

            self.connection.commit()

        except sqlite3.OperationalError as e:
            self.connection.rollback()
            logging.warning(f"Database locked during variable addition: {e}")
            raise
        except Exception as e:
            self.connection.rollback()
            logging.error(f"Failed to add variables for formula {formula_id}: {e}")
            raise

    def get_variables(self, formula_id: int) -> List[Dict]:
        """Get all variables for a formula."""
        cursor = self.connection.cursor()

        try:
            cursor.execute('SELECT symbol, name, unit FROM variables WHERE formula_id = ?',
                           (formula_id,))
            var_rows = cursor.fetchall()

            return [dict(row) for row in var_rows]

        except Exception as e:
            logging.error(f"Failed to get variables for formula {formula_id}: {e}")
            return []

    def delete_variables(self, formula_id: int):
        """Delete all variables for a formula."""
        cursor = self.connection.cursor()

        try:
            cursor.execute(self.DELETE_VARIABLES_QUERY, (formula_id,))
            self.connection.commit()

        except sqlite3.OperationalError as e:
            self.connection.rollback()
            logging.warning(f"Database locked during variable deletion: {e}")
            raise
        except Exception as e:
            self.connection.rollback()
            logging.error(f"Failed to delete variables for formula {formula_id}: {e}")
            raise

    def backup_database(self, backup_path: str) -> bool:
        """Create a backup of the database."""
        try:
            shutil.copy2(self.db_path, backup_path)
            logging.info(f"Database backed up to: {backup_path}")
            return True
        except Exception as e:
            logging.error(f"Failed to backup database: {e}")
            return False

    def close(self):
        """Close database connection and optionally vacuum to reclaim space."""
        try:
            # Check if we should vacuum (every 5-6 operations)
            if self._should_vacuum():
                logging.info("Running VACUUM to reclaim database space")
                self.connection.execute('VACUUM')
                logging.info("Database VACUUM completed")

            if self.connection:
                self.connection.close()
                logging.info("Database connection closed")
        except Exception as e:
            logging.error(f"Error closing database: {e}")

    def _should_vacuum(self) -> bool:
        """Check if database should be vacuumed based on operation count."""
        # Track vacuum operations in a simple counter
        if not hasattr(self, '_operation_count'):
            self._operation_count = 0

        self._operation_count += 1

        # Vacuum every 3 operations for better automatic maintenance
        vacuum_frequency = 3
        return self._operation_count % vacuum_frequency == 0

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
