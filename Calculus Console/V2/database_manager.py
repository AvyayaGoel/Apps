"""
SQLite Database Manager for Formula Sheet Application
Soft-delete architecture with display numbering and undo support.
"""

import logging
import shutil
import sqlite3
from datetime import datetime, timedelta
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
            self.connection.row_factory = sqlite3.Row
            self._create_tables()
            self._run_migrations()
            self._create_indexes()
        except Exception as e:
            logging.exception(f"Failed to initialize database: {e}")
            raise

    def _create_tables(self):
        """Create necessary database tables with soft-delete support."""
        cursor = self.connection.cursor()

        # Main formulas table — now with deleted flag, deleted_at, display_num
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS formulas (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                display_num INTEGER,
                formula_text TEXT NOT NULL,
                field TEXT NOT NULL,
                topic TEXT NOT NULL,
                sub_topic TEXT DEFAULT '_GENERAL_',
                notes TEXT DEFAULT '',
                deleted INTEGER DEFAULT 0,
                deleted_at TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # Variables table — unchanged schema, but now foreign keys are stable forever
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

    def _run_migrations(self):
        """Run database migrations to ensure schema is up to date."""
        cursor = self.connection.cursor()

        try:
            cursor.execute("PRAGMA table_info(formulas)")
            columns = {col[1] for col in cursor.fetchall()}

            # Migration: add soft-delete columns if missing
            if 'deleted' not in columns:
                cursor.execute('ALTER TABLE formulas ADD COLUMN deleted INTEGER DEFAULT 0')
                cursor.execute('ALTER TABLE formulas ADD COLUMN deleted_at TIMESTAMP')
                logging.info("Migration: added deleted/deleted_at columns")

            if 'display_num' not in columns:
                cursor.execute('ALTER TABLE formulas ADD COLUMN display_num INTEGER')
                # Initialize display_num from existing sequential order
                cursor.execute('''
                    WITH numbered AS (
                        SELECT id, ROW_NUMBER() OVER (ORDER BY id) as rn
                        FROM formulas
                        WHERE deleted = 0 OR deleted IS NULL
                    )
                    UPDATE formulas
                    SET display_num = numbered.rn
                    FROM numbered
                    WHERE formulas.id = numbered.id
                ''')
                logging.info("Migration: added display_num column")

            # Legacy migrations (keep for existing databases)
            if 'updated_at' not in columns:
                cursor.execute('ALTER TABLE formulas ADD COLUMN updated_at TIMESTAMP')
                cursor.execute('UPDATE formulas SET updated_at = created_at WHERE updated_at IS NULL')

            if 'notes' not in columns:
                cursor.execute('ALTER TABLE formulas ADD COLUMN notes TEXT DEFAULT \'\'')
                cursor.execute('UPDATE formulas SET notes = \'\' WHERE notes IS NULL')

            self.connection.commit()

        except Exception as e:
            logging.exception(f"Migration failed: {e}")
            self.connection.rollback()
            raise

    def _create_indexes(self):
        """Create database indexes for better performance."""
        cursor = self.connection.cursor()

        cursor.execute('CREATE INDEX IF NOT EXISTS idx_formulas_field ON formulas(field)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_formulas_topic ON formulas(topic)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_formulas_sub_topic ON formulas(sub_topic)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_formulas_text ON formulas(formula_text)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_formulas_deleted ON formulas(deleted)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_formulas_display_num ON formulas(display_num)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_variables_formula_id ON variables(formula_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_variables_symbol ON variables(symbol)')

        self.connection.commit()

    # ─────────────────────────────────────────────────────────────
    # DISPLAY NUMBER MANAGEMENT
    # ─────────────────────────────────────────────────────────────

    def _renumber_display_nums(self):
        """Recalculate display_num for all non-deleted formulas."""
        cursor = self.connection.cursor()
        try:
            cursor.execute('''
                WITH numbered AS (
                    SELECT id, ROW_NUMBER() OVER (ORDER BY display_num IS NULL, display_num, id) as new_num
                    FROM formulas
                    WHERE deleted = 0
                )
                UPDATE formulas
                SET display_num = numbered.new_num
                FROM numbered
                WHERE formulas.id = numbered.id
            ''')
            self.connection.commit()
        except Exception as e:
            self.connection.rollback()
            logging.exception(f"Failed to renumber display_nums: {e}")
            raise

    # ─────────────────────────────────────────────────────────────
    # FORMULA CRUD
    # ─────────────────────────────────────────────────────────────

    def add_formula(
            self,
            formula_text: str,
            field: str,
            topic: str,
            sub_topic: str = "_GENERAL_",
            notes: str = "",
            variables: List[Dict] | None = None
    ) -> int:
        """Add a new formula. display_num auto-assigned as next sequential."""

        cursor = self.connection.cursor()

        try:
            # Get next display_num
            cursor.execute('SELECT MAX(display_num) FROM formulas WHERE deleted = 0')
            result = cursor.fetchone()
            next_display = (result[0] or 0) + 1

            cursor.execute(
                '''
                INSERT INTO formulas
                (display_num, formula_text, field, topic, sub_topic, notes)
                VALUES (?, ?, ?, ?, ?, ?)
                ''',
                (next_display, formula_text, field, topic, sub_topic, notes)
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
            logging.exception(f"Failed to add formula: {e}")
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
        """Update an existing formula. Does NOT touch display_num or deleted state."""

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
                (formula_text, field, topic, sub_topic, notes, formula_id)
            )

            if variables is not None:
                self.delete_variables(formula_id)
                self.add_variables(formula_id, variables)

            self.connection.commit()
            return True

        except sqlite3.OperationalError as e:
            self.connection.rollback()
            logging.warning(f"Database locked during formula update: {e}")
            return False
        except Exception as e:
            self.connection.rollback()
            logging.exception(f"Failed to update formula {formula_id}: {e}")
            return False

    def soft_delete_formula(self, formula_id: int) -> bool:
        """
        Soft-delete a formula. Sets deleted=1, clears display_num, renumbers remaining.
        Returns True if successful.
        """
        cursor = self.connection.cursor()

        try:
            cursor.execute(
                '''
                UPDATE formulas
                SET deleted = 1,
                    deleted_at = CURRENT_TIMESTAMP
                WHERE id = ? AND deleted = 0
                ''',
                (formula_id,)
            )

            if cursor.rowcount == 0:
                logging.warning(f"Formula {formula_id} not found or already deleted")
                return False

            self.connection.commit()
            self._renumber_display_nums()
            return True

        except Exception as e:
            self.connection.rollback()
            logging.exception(f"Failed to soft-delete formula {formula_id}: {e}")
            return False

    def restore_formula(self, formula_id: int) -> bool:
        """
        Undo a soft-delete. Restores deleted=0, assigns new display_num, renumbers.
        Returns True if successful.
        """
        cursor = self.connection.cursor()

        try:
            cursor.execute(
                '''
                UPDATE formulas
                SET deleted = 0,
                    deleted_at = NULL
                WHERE id = ? AND deleted = 1
                ''',
                (formula_id,)
            )

            if cursor.rowcount == 0:
                logging.warning(f"Formula {formula_id} not found or not deleted")
                return False

            self.connection.commit()
            self._renumber_display_nums()
            return True

        except Exception as e:
            self.connection.rollback()
            logging.exception(f"Failed to restore formula {formula_id}: {e}")
            return False

    def hard_delete_formula(self, formula_id: int) -> bool:
        """
        PERMANENTLY delete a formula and all associated data.
        Use only for garbage collection or user-confirmed permanent deletion.
        """
        cursor = self.connection.cursor()

        try:
            cursor.execute(self.DELETE_VARIABLES_QUERY, (formula_id,))
            cursor.execute('DELETE FROM formula_tags WHERE formula_id = ?', (formula_id,))
            cursor.execute('DELETE FROM formulas WHERE id = ?', (formula_id,))

            self.connection.commit()

            # Only renumber if we actually deleted a visible formula
            if cursor.rowcount > 0:
                self._renumber_display_nums()

            return True

        except Exception as e:
            self.connection.rollback()
            logging.exception(f"Failed to hard-delete formula {formula_id}: {e}")
            return False

    def garbage_collect_deleted(self, days_old: int = 30) -> int:
        """
        Permanently delete formulas that have been soft-deleted for longer than `days_old`.
        Returns count of formulas permanently deleted.
        """
        cursor = self.connection.cursor()
        cutoff = datetime.now() - timedelta(days=days_old)

        try:
            cursor.execute(
                '''
                SELECT id FROM formulas
                WHERE deleted = 1 AND deleted_at < ?
                ''',
                (cutoff.isoformat(),)
            )

            to_delete = [row[0] for row in cursor.fetchall()]
            count = 0

            for formula_id in to_delete:
                if self.hard_delete_formula(formula_id):
                    count += 1

            return count

        except Exception as e:
            logging.exception(f"Garbage collection failed: {e}")
            return 0

    # ─────────────────────────────────────────────────────────────
    # QUERIES — ALL RETURN NON-DELETED FORMULAS WITH DISPLAY_NUM AS ID
    # ─────────────────────────────────────────────────────────────

    def get_formula(self, formula_id: int) -> Optional[Dict]:
        """
        Get a single formula by its STABLE id (not display_num).
        Returns None if deleted or not found.
        """
        cursor = self.connection.cursor()

        try:
            cursor.execute(
                '''
                SELECT id, display_num, formula_text, field, topic, sub_topic, notes,
                       created_at, updated_at
                FROM formulas
                WHERE id = ? AND deleted = 0
                ''',
                (formula_id,)
            )
            row = cursor.fetchone()

            if not row:
                return None

            return self._row_to_dict(row)

        except Exception as e:
            logging.exception(f"Failed to get formula {formula_id}: {e}")
            return None

    def get_all_formulas(self) -> List[Dict]:
        """
        Get all NON-DELETED formulas, ordered by display_num.
        Returns list of dicts with 'id' = display_num (for UI), 'db_id' = stable id.
        """
        cursor = self.connection.cursor()

        try:
            cursor.execute(
                '''
                SELECT id, display_num, formula_text, field, topic, sub_topic, notes,
                       created_at, updated_at
                FROM formulas
                WHERE deleted = 0
                ORDER BY display_num
                '''
            )

            return [self._row_to_dict(row) for row in cursor.fetchall()]

        except Exception as e:
            logging.exception(f"Failed to get all formulas: {e}")
            return []

    def get_formula_by_display_num(self, display_num: int) -> Optional[Dict]:
        """Look up a formula by its display number (UI-facing ID)."""
        cursor = self.connection.cursor()

        try:
            cursor.execute(
                '''
                SELECT id, display_num, formula_text, field, topic, sub_topic, notes,
                       created_at, updated_at
                FROM formulas
                WHERE display_num = ? AND deleted = 0
                ''',
                (display_num,)
            )
            row = cursor.fetchone()

            if not row:
                return None

            return self._row_to_dict(row)

        except Exception as e:
            logging.exception(f"Failed to get formula by display_num {display_num}: {e}")
            return None

    def get_deleted_formulas(self, limit: int = 50) -> List[Dict]:
        """Get recently soft-deleted formulas for 'undo' UI."""
        cursor = self.connection.cursor()

        try:
            cursor.execute(
                '''
                SELECT id, display_num, formula_text, field, topic, sub_topic, notes,
                       deleted, deleted_at, created_at, updated_at
                FROM formulas
                WHERE deleted = 1
                ORDER BY deleted_at DESC
                LIMIT ?
                ''',
                (limit,)
            )

            formulas = []
            for row in cursor.fetchall():
                d = self._row_to_dict(row, include_deleted=True)
                d['deleted_at'] = row['deleted_at']
                formulas.append(d)

            return formulas

        except Exception as e:
            logging.exception(f"Failed to get deleted formulas: {e}")
            return []

    def _row_to_dict(self, row: sqlite3.Row, include_deleted: bool = False) -> Dict:
        """
        Convert a DB row to the dict format expected by the app.
        'id' = display_num (UI-facing), 'db_id' = stable internal id.
        Strips all deleted-related flags by default.
        """
        result = {
            'db_id': row['id'],
            'id': row['display_num'],  # UI sees display_num as the "ID"
            'formula_text': row['formula_text'],
            'field': row['field'],
            'topic': row['topic'],
            'sub_topic': row['sub_topic'],
            'notes': row['notes'],
            'created_at': row['created_at'],
            'updated_at': row['updated_at'],
            'variables': self.get_variables(row['id']),
        }

        if include_deleted:
            result['deleted'] = row['deleted']

        return result

    def add_formula_tags(self, formula_id: int, tags: list[str]):
        """Add tags to a formula. Uses stable db_id internally."""
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
            logging.exception(f"Failed to add formula tags: {e}")

    def get_formula_tags(self, formula_id: int) -> list[str]:
        """Get all tags for a formula. Uses stable db_id."""
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
            logging.exception(f"Failed to get formula tags: {e}")
            return []

    def replace_formula_tags(self, formula_id: int, tags: list[str]):
        """Replace all tags for a formula. Uses stable db_id."""
        cursor = self.connection.cursor()

        try:
            cursor.execute('DELETE FROM formula_tags WHERE formula_id = ?', (formula_id,))
            self.add_formula_tags(formula_id, tags)
            self.connection.commit()

        except Exception as e:
            self.connection.rollback()
            logging.exception(f"Failed to replace formula tags: {e}")

    def add_variables(self, formula_id: int, variables: List[Dict]):
        """Add variables for a formula. Uses stable db_id."""
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
            logging.exception(f"Failed to add variables for formula {formula_id}: {e}")
            raise

    def get_variables(self, formula_id: int) -> List[Dict]:
        """Get all variables for a formula. Uses stable db_id."""
        cursor = self.connection.cursor()

        try:
            cursor.execute(
                'SELECT symbol, name, unit FROM variables WHERE formula_id = ?',
                (formula_id,)
            )
            return [dict(row) for row in cursor.fetchall()]

        except Exception as e:
            logging.exception(f"Failed to get variables for formula {formula_id}: {e}")
            return []

    def delete_variables(self, formula_id: int):
        """Delete all variables for a formula. Uses stable db_id."""
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
            logging.exception(f"Failed to delete variables for formula {formula_id}: {e}")
            raise

    def backup_database(self, backup_path: str) -> bool:
        """Create a backup of the database."""
        try:
            shutil.copy2(self.db_path, backup_path)
            return True
        except Exception as e:
            logging.exception(f"Failed to backup database: {e}")
            return False

    def close(self):
        """Close database connection."""
        try:
            if self._should_vacuum():
                self.connection.execute('VACUUM')
            if self.connection:
                self.connection.close()
        except Exception as e:
            logging.exception(f"Error closing database: {e}")

    def _should_vacuum(self) -> bool:
        """Check if database should be vacuumed."""
        if not hasattr(self, '_operation_count'):
            self._operation_count = 0
        self._operation_count += 1
        return self._operation_count % 10 == 0  # Less frequent now that we don't rebuild tables

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
