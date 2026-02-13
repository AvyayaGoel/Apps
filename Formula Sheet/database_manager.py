"""
SQLite Database Manager for Formula Sheet Application
Replaces JSON file-based storage with SQLite for better performance and scalability
"""

import json
import logging
import os
import sqlite3
import shutil
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime


class DatabaseManager:
    """Manages SQLite database operations for formula storage."""
    
    def __init__(self, db_path: str):
        self.db_path = db_path
        self.connection = None
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
    
    @staticmethod
    def _save_variables_for_formula(cursor, formula_id: int, variables: List[Dict]) -> None:
        """Save variables for a formula."""
        for var in variables:
            cursor.execute('''
                INSERT INTO variables (formula_id, symbol, name, unit)
                VALUES (?, ?, ?, ?)
            ''', (formula_id, var['symbol'], var['name'], var.get('unit', '')))
    
    def _update_existing_formula(self, cursor, formula_id: int, formula_text: str, 
                                field: str, topic: str, sub_topic: str, variables: List[Dict]) -> None:
        """Update an existing formula and its variables."""
        cursor.execute('''
            UPDATE formulas 
            SET formula_text = ?, field = ?, topic = ?, sub_topic = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        ''', (formula_text, field, topic, sub_topic, formula_id))
        
        cursor.execute('DELETE FROM variables WHERE formula_id = ?', (formula_id,))
        self._save_variables_for_formula(cursor, formula_id, variables)
    
    def _insert_new_formula(self, cursor, formula_id: int, formula_text: str, 
                           field: str, topic: str, sub_topic: str, variables: List[Dict]) -> bool:
        """Insert a new formula and its variables. Returns True if successful."""
        cursor.execute('''
            INSERT OR IGNORE INTO formulas (id, formula_text, field, topic, sub_topic)
            VALUES (?, ?, ?, ?, ?)
        ''', (formula_id, formula_text, field, topic, sub_topic))
        
        if cursor.rowcount > 0:
            self._save_variables_for_formula(cursor, formula_id, variables)
            return True
        return False
    
    @staticmethod
    def _extract_formula_data(formula_data: Dict) -> tuple:
        """Extract formula data from the input dictionary."""
        main_info = formula_data['main_info']
        formula_text = main_info[1]
        field = main_info[2]
        topic = main_info[3]
        sub_topic = main_info[4] if len(main_info) > 4 else "_GENERAL_"
        variables = formula_data.get('variables', [])
        return formula_text, field, topic, sub_topic, variables

    def save_formulas_batch(self, formulas_data: Dict[int, Dict]) -> Tuple[int, int]:
        """
        Save multiple formulas (INSERT/UPDATE) in a single transaction for optimal performance.
        
        Args:
            formulas_data: Dictionary mapping formula_id to formula_data
            
        Returns:
            Tuple of (inserted_count, updated_count)
        """
        cursor = self.connection.cursor()
        inserted_count = 0
        updated_count = 0
        
        try:
            self.connection.execute("BEGIN TRANSACTION")
            
            existing_ids = set()
            if formulas_data:
                cursor.execute(f"SELECT id FROM formulas WHERE id IN ({','.join(['?'] * len(formulas_data))})", 
                             tuple(formulas_data.keys()))
                existing_ids = {row[0] for row in cursor.fetchall()}
            
            for formula_id, formula_data in formulas_data.items():
                formula_text, field, topic, sub_topic, variables = self._extract_formula_data(formula_data)
                
                if formula_id in existing_ids:
                    self._update_existing_formula(cursor, formula_id, formula_text, field, topic, sub_topic, variables)
                    updated_count += 1
                else:
                    if self._insert_new_formula(cursor, formula_id, formula_text, field, topic, sub_topic, variables):
                        inserted_count += 1
            
            self.connection.commit()
            logging.info(f"Batch saved: {inserted_count} inserted, {updated_count} updated")
            
            return inserted_count, updated_count
            
        except sqlite3.OperationalError as e:
            self.connection.rollback()
            logging.warning(f"Database locked during batch save, will retry: {e}")
            return 0, 0
        except Exception as e:
            self.connection.rollback()
            logging.error(f"Failed to batch save formulas: {e}")
            return 0, 0
    
    def add_formulas_batch(self, formulas_data: List[Dict]) -> int:
        """Add multiple formulas in a single transaction for better performance."""
        cursor = self.connection.cursor()
        migrated_count = 0
        
        try:
            # Begin transaction
            self.connection.execute("BEGIN TRANSACTION")
            
            for formula_data in formulas_data:
                cursor.execute('''
                    INSERT INTO formulas (formula_text, field, topic, sub_topic)
                    VALUES (?, ?, ?, ?)
                ''', (
                    formula_data['formula_text'],
                    formula_data['field'],
                    formula_data['topic'],
                    formula_data['sub_topic']
                ))
                migrated_count += 1
            
            # Commit transaction
            self.connection.commit()
            logging.info(f"Batch inserted {migrated_count} formulas")
            
            # Add variables for each formula if they exist
            for formula_data in formulas_data:
                if formula_data.get('variables'):
                    # Get the ID of the inserted formula
                    cursor.execute('SELECT id FROM formulas WHERE formula_text = ? AND field = ? AND topic = ? LIMIT 1',
                               (formula_data['formula_text'], formula_data['field'], formula_data['topic']))
                    result = cursor.fetchone()
                    if result:
                        formula_id = result[0]
                        self.add_variables(formula_id, formula_data['variables'])
            
            return migrated_count
            
        except sqlite3.OperationalError as e:
            self.connection.rollback()
            logging.warning(f"Database locked during batch insert, will retry: {e}")
            return 0
        except Exception as e:
            self.connection.rollback()
            logging.error(f"Failed to batch insert formulas: {e}")
            return 0
    
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
        """Delete a formula and its variables."""
        cursor = self.connection.cursor()
        
        try:
            cursor.execute('DELETE FROM formulas WHERE id = ?', (formula_id,))
            self.connection.commit()
            logging.info(f"Deleted formula with ID: {formula_id}")
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
    
    def search_formulas(self, query: str = None, field: str = None, 
                       topic: str = None, sub_topic: str = None) -> List[Dict]:
        """Search formulas with optional filters."""
        cursor = self.connection.cursor()
        
        try:
            base_query = 'SELECT * FROM formulas WHERE 1=1'
            params = []
            
            if query:
                base_query += ' AND formula_text LIKE ?'
                params.append(f'%{query}%')
            
            if field:
                base_query += ' AND field = ?'
                params.append(field)
            
            if topic:
                base_query += ' AND topic = ?'
                params.append(topic)
            
            if sub_topic:
                base_query += ' AND sub_topic = ?'
                params.append(sub_topic)
            
            base_query += ' ORDER BY id'
            
            cursor.execute(base_query, params)
            formula_rows = cursor.fetchall()
            
            formulas = []
            for row in formula_rows:
                formula = dict(row)
                formula['variables'] = self.get_variables(formula['id'])
                formulas.append(formula)
            
            return formulas
            
        except Exception as e:
            logging.error(f"Failed to search formulas: {e}")
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
            cursor.execute('DELETE FROM variables WHERE formula_id = ?', (formula_id,))
            self.connection.commit()
            
        except sqlite3.OperationalError as e:
            self.connection.rollback()
            logging.warning(f"Database locked during variable deletion: {e}")
            raise
        except Exception as e:
            self.connection.rollback()
            logging.error(f"Failed to delete variables for formula {formula_id}: {e}")
            raise
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get database statistics."""
        cursor = self.connection.cursor()
        
        try:
            stats = {}
            
            # Total formulas
            cursor.execute('SELECT COUNT(*) FROM formulas')
            stats['total_formulas'] = cursor.fetchone()[0]
            
            # Formulas by field
            cursor.execute('SELECT field, COUNT(*) FROM formulas GROUP BY field')
            stats['by_field'] = dict(cursor.fetchall())
            
            # Formulas by topic
            cursor.execute('SELECT topic, COUNT(*) FROM formulas GROUP BY topic')
            stats['by_topic'] = dict(cursor.fetchall())
            
            # Total variables
            cursor.execute('SELECT COUNT(*) FROM variables')
            stats['total_variables'] = cursor.fetchone()[0]
            
            # Average variables per formula
            if stats['total_formulas'] > 0:
                stats['avg_variables_per_formula'] = stats['total_variables'] / stats['total_formulas']
            else:
                stats['avg_variables_per_formula'] = 0
            
            return stats
            
        except Exception as e:
            logging.error(f"Failed to get statistics: {e}")
            return {}
    
    def migrate_from_json(self, json_file_path: str) -> Tuple[bool, int]:
        """Migrate data from JSON file to SQLite database."""
        if not os.path.exists(json_file_path):
            logging.warning("JSON data file not found")
            return False, 0
        
        # Check if migration has already been done
        migration_marker = os.path.join(os.path.dirname(self.db_path), f".json_formula_migration_{os.path.basename(json_file_path)}")
        if os.path.exists(migration_marker):
            logging.info("JSON formula migration already completed")
            return True, 0
        
        try:
            with open(json_file_path, 'r', encoding='utf-8') as f:
                json_data = json.load(f)
            
            migrated_count = 0
            
            for item in json_data:
                # Normalize the data structure
                main_info = item.get('main_info', [])
                if len(main_info) < 4:
                    continue  # Skip invalid entries
                
                # Extract formula data
                formula_text = main_info[1]
                field = main_info[2]
                topic = main_info[3]
                sub_topic = main_info[4] if len(main_info) > 4 else "_GENERAL_"
                variables = item.get('variables', [])
                
                # Add to database (ignore the original ID, let SQLite generate new ones)
                self.add_formula(formula_text, field, topic, sub_topic, variables)
                migrated_count += 1
            
            # Log the migration
            cursor = self.connection.cursor()
            cursor.execute('''
                INSERT INTO migration_log (source_format, records_migrated, status)
                VALUES (?, ?, ?)
            ''', ('JSON', migrated_count, 'SUCCESS'))
            self.connection.commit()
            
            # Mark migration as complete
            with open(migration_marker, "w") as f:
                f.write(f"Migration completed: {datetime.now().isoformat()}")
            
            logging.info(f"Successfully migrated {migrated_count} formulas from JSON to SQLite")
            return True, migrated_count
            
        except json.JSONDecodeError as e:
            logging.error(f"JSON decode error: {e}")
            return False, 0
        except Exception as e:
            logging.error(f"Failed to migrate from JSON: {e}")
            return False, 0
    
    def export_to_json(self, json_file_path: str) -> bool:
        """Export database to JSON format (for backup or compatibility)."""
        try:
            formulas = self.get_all_formulas()
            
            # Convert to the expected JSON format
            json_data = []
            for formula in formulas:
                main_info = [
                    formula['id'],
                    formula['formula_text'],
                    formula['field'],
                    formula['topic'],
                    formula['sub_topic']
                ]
                
                json_item = {
                    'main_info': main_info,
                    'variables': [
                        {'symbol': var['symbol'], 'name': var['name'], 'unit': var['unit']}
                        for var in formula['variables']
                    ]
                }
                json_data.append(json_item)
            
            with open(json_file_path, 'w', encoding='utf-8') as f:
                json.dump(json_data, f, indent=4, ensure_ascii=False)
            
            logging.info(f"Successfully exported {len(json_data)} formulas to JSON")
            return True
            
        except Exception as e:
            logging.error(f"Failed to export to JSON: {e}")
            return False
    
    def backup_database(self, backup_path: str) -> bool:
        """Create a backup of the database."""
        try:
            shutil.copy2(self.db_path, backup_path)
            logging.info(f"Database backed up to: {backup_path}")
            return True
        except Exception as e:
            logging.error(f"Failed to backup database: {e}")
            return False
    
    def create_system_backup(self, backup_dir: str = None) -> Optional[str]:
        """Create a backup with system-like naming convention."""
        if backup_dir is None:
            backup_dir = os.path.dirname(self.db_path)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_name = f"clr_cache_{timestamp}.tmp"
        backup_path = os.path.join(backup_dir, backup_name)
        
        if self.backup_database(backup_path):
            return backup_path
        return None
    
    def close(self):
        """Close database connection."""
        if self.connection:
            self.connection.close()
            logging.info("Database connection closed")
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
