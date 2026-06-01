"""
Migración: Crear tablas customers, email_config y agregar customer_id a sales.
"""
from sqlalchemy import create_engine, text

engine = create_engine('sqlite:///pos_app.db', connect_args={'check_same_thread': False})

SQL_STATEMENTS = [
    # Tabla customers
    """CREATE TABLE IF NOT EXISTS customers (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name VARCHAR(150) NOT NULL,
        email VARCHAR(120),
        phone VARCHAR(20),
        customer_type VARCHAR(20) DEFAULT 'LLEVAR',
        address VARCHAR(255),
        delivery_code VARCHAR(30) UNIQUE,
        gdpr_consent BOOLEAN DEFAULT 0,
        consent_email_sent BOOLEAN DEFAULT 0,
        consent_sent_at DATETIME,
        consent_email_snapshot TEXT,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        updated_at DATETIME,
        updated_by_id INTEGER
    )""",
    # Tabla email_config
    """CREATE TABLE IF NOT EXISTS email_config (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        smtp_host VARCHAR(100) DEFAULT 'smtp.gmail.com',
        smtp_port INTEGER DEFAULT 587,
        smtp_user VARCHAR(120),
        smtp_password VARCHAR(255),
        smtp_use_tls BOOLEAN DEFAULT 1,
        from_name VARCHAR(100) DEFAULT 'Sistema POS',
        from_email VARCHAR(120),
        gdpr_enabled BOOLEAN DEFAULT 0,
        gdpr_email_subject VARCHAR(200) DEFAULT 'Autorización para el tratamiento de sus datos personales',
        gdpr_email_body_html TEXT,
        last_test_at DATETIME,
        last_test_ok BOOLEAN,
        updated_at DATETIME,
        updated_by_id INTEGER
    )""",
    # Agregar customer_id a sales
    "ALTER TABLE sales ADD COLUMN customer_id INTEGER REFERENCES customers(id)",
    # Índice para búsqueda por email de cliente
    "CREATE INDEX IF NOT EXISTS idx_customers_email ON customers(email)",
    # Índice para tipo de servicio
    "CREATE INDEX IF NOT EXISTS idx_customers_type ON customers(customer_type)",
]

# Insertar configuración inicial de email (solo si no existe)
INSERT_DEFAULT_EMAIL_CONFIG = """
INSERT OR IGNORE INTO email_config (id, smtp_host, smtp_port, smtp_use_tls, from_name, gdpr_enabled)
VALUES (1, 'smtp.gmail.com', 587, 1, 'Sistema POS', 0)
"""

with engine.connect() as conn:
    for sql in SQL_STATEMENTS:
        try:
            conn.execute(text(sql))
            conn.commit()
            stmt = sql.strip().split('\n')[0][:60]
            print(f'[OK] {stmt}...')
        except Exception as e:
            msg = str(e).lower()
            if 'already exists' in msg or 'duplicate column' in msg:
                print(f'[SKIP] {sql.strip().split(chr(10))[0][:60]}... (ya existe)')
            else:
                print(f'[ERR] {sql.strip()[:60]}: {e}')

    conn.execute(text(INSERT_DEFAULT_EMAIL_CONFIG))
    conn.commit()
    print('[OK] Configuración inicial de email insertada')

print('\n=== Migración completa ===')
