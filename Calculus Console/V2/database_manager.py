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
                notes TEXT DEFAULT '',
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

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS formula_tags (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                formula_id INTEGER NOT NULL,
                tag TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (formula_id) REFERENCES formulas (id) ON DELETE CASCADE,
                UNIQUE(formula_id, tag)
            )
        ''')

        self.connection.commit()

        # Run database migrations
        self._run_migrations()

    def add_formula_tags(self, formula_id: int, tags: list[str]):
        """Add tags to a formula."""
        cursor = self.connection.cursor()

        try:
            cleaned_tags = []

            for tag in tags:
                if not tag:
                    continue

                cleaned = tag.strip().lower()

                if cleaned and cleaned not in cleaned_tags:
                    cleaned_tags.append(cleaned)

            cursor.executemany(
                '''
                INSERT OR IGNORE INTO formula_tags (formula_id, tag)
                VALUES (?, ?)
                ''',
                [(formula_id, tag) for tag in cleaned_tags]
            )

            self.connection.commit()

        except Exception as e:
            self.connection.rollback()
            logging.error(f"Failed to add formula tags: {e}")

    def get_formula_tags(self, formula_id: int) -> list[str]:
        """Get all tags for a formula."""
        cursor = self.connection.cursor()

        try:
            cursor.execute(
                '''
                SELECT tag
                FROM formula_tags
                WHERE formula_id = ?
                ORDER BY tag ASC
                ''',
                (formula_id,)
            )

            return [row[0] for row in cursor.fetchall()]

        except Exception as e:
            logging.error(f"Failed to get formula tags: {e}")
            return []

    def replace_formula_tags(self, formula_id: int, tags: list[str]):
        """Replace all tags for a formula."""
        cursor = self.connection.cursor()

        try:
            cursor.execute(
                'DELETE FROM formula_tags WHERE formula_id = ?',
                (formula_id,)
            )

            self.add_formula_tags(formula_id, tags)

            self.connection.commit()

        except Exception as e:
            self.connection.rollback()
            logging.error(f"Failed to replace formula tags: {e}")

    def _run_migrations(self):
        """Run database migrations to ensure schema is up to date."""
        cursor = self.connection.cursor()

        try:
            cursor.execute("PRAGMA table_info(formulas)")
            columns = [column[1] for column in cursor.fetchall()]

            if 'updated_at' not in columns:
                cursor.execute(
                    'ALTER TABLE formulas ADD COLUMN updated_at TIMESTAMP'
                )
                cursor.execute(
                    '''
                    UPDATE formulas
                    SET updated_at = created_at
                    WHERE updated_at IS NULL
                    '''
                )

            if 'notes' not in columns:
                cursor.execute(
                    '''
                    ALTER TABLE formulas
                    ADD COLUMN notes TEXT DEFAULT ''
                    '''
                )

                cursor.execute(
                    '''
                    UPDATE formulas
                    SET notes = ''
                    WHERE notes IS NULL
                    '''
                )

            self.connection.commit()

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

    def add_formula(
            self,
            formula_text: str,
            field: str,
            topic: str,
            sub_topic: str = "_GENERAL_",
            notes: str = "",
            variables: List[Dict] | None = None
    ) -> int:
        """Add a new formula to the database."""

        cursor = self.connection.cursor()

        try:
            cursor.execute(
                '''
                INSERT INTO formulas
                (formula_text, field, topic, sub_topic, notes)
                VALUES (?, ?, ?, ?, ?)
                ''',
                (formula_text, field, topic, sub_topic, notes)
            )

            formula_id = cursor.lastrowid

            if variables:
                self.add_variables(formula_id, variables)

            self.connection.commit()
            return formula_id

        except sqlite3.OperationalError as e:
            self.connection.rollback()
            logging.warning(f"Database locked during formula addition: {e}")
            raise

        except Exception as e:
            self.connection.rollback()
            logging.error(f"Failed to add formula: {e}")
            raise

    def update_formula(
            self,
            formula_id: int,
            formula_text: str,
            field: str,
            topic: str,
            sub_topic: str = "_GENERAL_",
            notes: str = "",
            variables: List[Dict] | None = None
    ) -> bool:
        """Update an existing formula."""

        cursor = self.connection.cursor()

        try:
            cursor.execute(
                '''
                UPDATE formulas
                SET formula_text = ?,
                    field = ?,
                    topic = ?,
                    sub_topic = ?,
                    notes = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                ''',
                (
                    formula_text,
                    field,
                    topic,
                    sub_topic,
                    notes,
                    formula_id
                )
            )

            if variables is not None:
                self.delete_variables(formula_id)
                self.add_variables(formula_id, variables)

            self.connection.commit()

            if self._should_vacuum():
                try:
                    self.connection.execute('VACUUM')
                except Exception as e:
                    logging.warning(f"Post-operation VACUUM failed: {e}")

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
        cursor = self.connection.cursor()
        try:
            cursor.execute(self.DELETE_VARIABLES_QUERY, (formula_id,))
            cursor.execute('DELETE FROM formula_tags WHERE formula_id = ?', (formula_id,))
            cursor.execute('DELETE FROM formulas WHERE id = ?', (formula_id,))

            # Get column order dynamically instead of assuming positions
            cursor.execute("PRAGMA table_info(formulas)")
            columns = [col[1] for col in cursor.fetchall()]

            # Build explicit column list for SELECT and INSERT
            col_names = ', '.join(columns)

            cursor.execute(f'SELECT {col_names} FROM formulas ORDER BY id')
            remaining_formulas = cursor.fetchall()

            if remaining_formulas:
                cursor.execute('DROP TABLE IF EXISTS temp_formulas')

                # Recreate with same schema
                cursor.execute('''
                    CREATE TABLE temp_formulas (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        formula_text TEXT NOT NULL,
                        field TEXT NOT NULL,
                        topic TEXT NOT NULL,
                        sub_topic TEXT DEFAULT '_GENERAL_',
                        notes TEXT DEFAULT '',
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                ''')

                old_to_new_ids = {}

                for formula in remaining_formulas:
                    old_id = formula[columns.index('id')]

                    # Extract values by column name, not position
                    vals = [formula[columns.index(c)] for c in columns if c != 'id']

                    cursor.execute(f'''
                        INSERT INTO temp_formulas
                        ({', '.join([c for c in columns if c != 'id'])})
                        VALUES ({', '.join(['?' for _ in vals])})
                    ''', vals)

                    new_id = cursor.lastrowid
                    old_to_new_ids[old_id] = new_id

                # Update foreign keys...
                for old_id, new_id in old_to_new_ids.items():
                    cursor.execute('UPDATE variables SET formula_id = ? WHERE formula_id = ?', (new_id, old_id))
                    cursor.execute('UPDATE formula_tags SET formula_id = ? WHERE formula_id = ?', (new_id, old_id))

                cursor.execute('DROP TABLE formulas')
                cursor.execute('ALTER TABLE temp_formulas RENAME TO formulas')
                cursor.execute('DELETE FROM sqlite_sequence WHERE name = "formulas"')
                cursor.execute('INSERT INTO sqlite_sequence (name, seq) VALUES (?, ?)',
                               ('formulas', len(remaining_formulas)))

            self.connection.commit()
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
            return True
        except Exception as e:
            logging.error(f"Failed to backup database: {e}")
            return False

    def close(self):
        """Close database connection and optionally vacuum to reclaim space."""
        try:
            # Check if we should vacuum (every 5-6 operations)
            if self._should_vacuum():
                self.connection.execute('VACUUM')

            if self.connection:
                self.connection.close()
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
