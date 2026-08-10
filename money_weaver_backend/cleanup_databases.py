#!/usr/bin/env python3
"""
Database Cleanup Script for MoneyWeaver

This script consolidates database files to ensure only one database is used
throughout the application.

Usage:
    python cleanup_databases.py
"""

import os
import shutil
from pathlib import Path

def main():
    # Define the project root
    project_root = Path(__file__).parent
    
    # Define database paths
    database_paths = {
        'src_database': project_root / 'src' / 'database' / 'app.db',
        'database': project_root / 'database' / 'app.db',
        'instance': project_root / 'instance' / 'app.db'
    }
    
    # Check which databases exist
    existing_dbs = {name: path for name, path in database_paths.items() if path.exists()}
    
    print("Existing database files:")
    for name, path in existing_dbs.items():
        size = path.stat().st_size
        print(f"  {name}: {path} ({size} bytes)")
    
    # Determine which database to use (prefer instance since that's what's currently working)
    target_db = database_paths['database']  # Target location per configuration
    source_db = database_paths['instance']  # Source with correct data
    
    print(f"\nConsolidating databases...")
    print(f"Source (with correct data): {source_db}")
    print(f"Target (configuration expects): {target_db}")
    
    # Create directories if they don't exist
    target_db.parent.mkdir(parents=True, exist_ok=True)
    
    # Copy the instance database to the target location
    if source_db.exists():
        shutil.copy2(source_db, target_db)
        print(f"Copied {source_db.name} to {target_db}")
    
    # Remove other database files to avoid confusion
    for name, path in database_paths.items():
        if name != 'database' and path.exists():
            try:
                path.unlink()
                print(f"Removed {name}: {path}")
            except Exception as e:
                print(f"Failed to remove {name}: {path} - {e}")
    
    print("\nDatabase consolidation complete!")
    print("The application will now use the database at:")
    print(f"  {target_db}")

if __name__ == '__main__':
    main()