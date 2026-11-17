import os
import logging
from psycopg2.pool import ThreadedConnectionPool
from psycopg2.extras import RealDictCursor
from flask import current_app, g

logger = logging.getLogger(__name__)

class Database:
    def __init__(self, app=None):
        self.pool = None
        if app is not None:
            self.init_app(app)

    def init_app(self, app):
        database_url = app.config.get("DATABASE_URL")
        try:
            # Inicializa o pool de conexões para evitar abrir conexões a cada clique
            self.pool = ThreadedConnectionPool(
                minconn=1,
                maxconn=10,
                dsn=database_url,
                connect_timeout=5,
                cursor_factory=RealDictCursor
            )
            app.logger.info("Pool de conexões com o PostgreSQL estabelecido com sucesso.")
        except Exception as e:
            app.logger.error(f"Erro ao conectar ao PostgreSQL: {str(e)}")
            raise

    def get_connection(self):
        if not hasattr(g, 'db_conn') or g.db_conn.closed:
            try:
                g.db_conn = self.pool.getconn()
            except Exception as e:
                logger.error("UnicodeDecodeError / Erro de conexão com o banco. Verifique credenciais ou lc_messages.")
                raise RuntimeError("Não foi possível estabelecer ligação com a base de dados.") from e
        return g.db_conn

    def put_connection(self, exception=None):
        conn = g.pop('db_conn', None)
        if conn is not None and self.pool:
            if exception is not None:
                try:
                    conn.rollback()
                except Exception:
                    pass
            self.pool.putconn(conn)

db = Database()