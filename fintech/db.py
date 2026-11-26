import logging
from flask import g
from psycopg2.extras import RealDictCursor
from psycopg2.pool import ThreadedConnectionPool

logger = logging.getLogger(__name__)


class Database:
    def __init__(self, app=None):
        self.pool = None
        if app is not None:
            self.init_app(app)

    def init_app(self, app):
        database_url = app.config.get("DATABASE_URL")
        self.pool = ThreadedConnectionPool(
            minconn=1,
            maxconn=10,
            dsn=database_url,
            connect_timeout=5,
            cursor_factory=RealDictCursor,
        )
        app.logger.info("PostgreSQL connection pool initialized.")

    def get_connection(self):
        if not hasattr(g, "db_conn") or g.db_conn.closed:
            try:
                g.db_conn = self.pool.getconn()
            except Exception as exc:
                # Falhas de encoding no driver costumam mascarar credenciais inválidas ou lc_messages.
                logger.error("Failed to acquire PostgreSQL connection: %s", exc)
                raise RuntimeError("Não foi possível conectar ao banco de dados.") from exc
        return g.db_conn

    def put_connection(self, exception=None):
        conn = g.pop("db_conn", None)
        if conn is not None and self.pool:
            if exception is not None:
                try:
                    conn.rollback()
                except Exception:
                    pass
            self.pool.putconn(conn)


db = Database()