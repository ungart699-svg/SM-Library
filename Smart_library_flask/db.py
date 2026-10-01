"""db.py - database connection, nothing else."""

import mysql.connector

def get_db():
    """Opens a fresh connection to the smart_library database."""
    return mysql.connector.connect(
        host='127.0.0.1',
        user='root',
        password='2002',          # set your MySQL password here
        database='smart_library'
    )
