# backend/tests/conftest.py
import sys
import os
import pytest
from asyncpg import transaction as asyncpg_transaction
import asyncpg
import asyncio
from typing import AsyncGenerator, Dict, Any, Optional
import uuid
import subprocess  # For calling psql

project_backend_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if project_backend_root not in sys.path:
    sys.path.insert(0, project_backend_root)

from core.security import get_password_hash
from db.repositories.user_repository import UserRepository


# Function to get schema SQL (adjust path if necessary)
def get_schema_sql() -> str:
    # Attempt to locate it in the parent of project_backend_root if not found directly
    # This is to handle running tests from backend/ or from SmartInfo/
    schema_file_path_primary = os.path.join(
        project_backend_root, "db", "migrations", "0001_initial_schema.sql"
    )
    schema_file_path_alt = os.path.join(
        os.path.dirname(project_backend_root),
        "db",
        "migrations",
        "0001_initial_schema.sql",
    )

    if os.path.exists(schema_file_path_primary):
        schema_file_path = schema_file_path_primary
    elif os.path.exists(schema_file_path_alt):
        schema_file_path = schema_file_path_alt
    else:
        pytest.exit(
            f"Schema file not found at {schema_file_path_primary} or {schema_file_path_alt}"
        )

    with open(schema_file_path, "r", encoding="utf-8") as f:
        return f.read()


@pytest.fixture(scope="session")
def db_test_env_vars() -> Dict[str, str]:
    """Provides test database connection details as a dictionary."""
    test_db_user = os.getenv("TEST_DB_USER")
    test_db_password = os.getenv("TEST_DB_PASSWORD")
    test_db_name = os.getenv("TEST_DB_NAME")
    test_db_host = os.getenv("TEST_DB_HOST", "localhost")
    test_db_port = os.getenv("TEST_DB_PORT", "5434")

    if not all([test_db_user, test_db_password, test_db_name]):
        pytest.exit(
            "Missing required TEST_DB environment variables (USER, PASSWORD, NAME)."
        )
    # Since we exit if any are None, we can safely assert they are strings
    assert test_db_user is not None
    assert test_db_password is not None
    assert test_db_name is not None
    return {
        "user": test_db_user,
        "password": test_db_password,
        "name": test_db_name,
        "host": test_db_host,
        "port": test_db_port,
    }


@pytest.fixture(scope="session")
def db_test_dsn(db_test_env_vars: Dict[str, str]) -> str:
    """Provides the DSN for the test database."""
    return f"postgresql://{db_test_env_vars['user']}:{db_test_env_vars['password']}@{db_test_env_vars['host']}:{db_test_env_vars['port']}/{db_test_env_vars['name']}"


@pytest.fixture(scope="session", autouse=True)
def setup_test_database_tables(db_test_env_vars: Dict[str, str]):
    """
    Session-scoped fixture to ensure the test database schema (tables) is created once using psql.
    Assumes the database itself already exists and the user has permissions to create/drop tables.
    This runs automatically for the session.
    """
    schema_sql = get_schema_sql()

    # psql command to connect to the specific test database and execute the schema file
    psql_command = [
        "psql",
        "-h",
        db_test_env_vars["host"],
        "-p",
        db_test_env_vars["port"],
        "-U",
        db_test_env_vars["user"],
        "-d",
        db_test_env_vars["name"],
        "-c",
        schema_sql,
    ]

    env = os.environ.copy()
    env["PGPASSWORD"] = db_test_env_vars["password"]

    try:
        print(f"Attempting to apply schema to database '{db_test_env_vars['name']}'...")
        # First, ensure the database exists and we can connect.
        check_db_command = [
            "psql",
            "-h",
            db_test_env_vars["host"],
            "-p",
            db_test_env_vars["port"],
            "-U",
            db_test_env_vars["user"],
            "-d",
            db_test_env_vars["name"],
            "-c",
            "\\q",
        ]
        result_check_db = subprocess.run(
            check_db_command, env=env, capture_output=True, text=True, check=False
        )
        if result_check_db.returncode != 0:
            pytest.exit(
                f"Failed to connect to the test database '{db_test_env_vars['name']}'. Please ensure it exists and the user has connect permissions. "
                f"Return code: {result_check_db.returncode}\\nStdout: {result_check_db.stdout}\\nStderr: {result_check_db.stderr}"
            )

        # If connection is fine, proceed to apply schema
        result_apply_schema = subprocess.run(
            psql_command, env=env, capture_output=True, text=True, check=False
        )
        if result_apply_schema.returncode != 0:
            pytest.exit(
                f"Failed to apply schema to '{db_test_env_vars['name']}' using psql. Return code: {result_apply_schema.returncode}\\n"
                f"Stdout: {result_apply_schema.stdout}\\nStderr: {result_apply_schema.stderr}"
            )
        print(
            f"Test database tables (re)created in '{db_test_env_vars['name']}' via psql."
        )

    except FileNotFoundError:
        pytest.exit(
            "psql command not found. Please ensure PostgreSQL client tools are installed and in PATH."
        )
    except Exception as e:
        pytest.exit(f"Failed to initialize test database schema via psql: {e}")


@pytest.fixture()
async def db_conn(
    db_test_dsn: str,
    # setup_test_database_tables dependency is implicitly handled by autouse=True
) -> AsyncGenerator[asyncpg.Connection, None]:
    """
    Provides a direct database connection for each test function, with transaction management.
    """
    connection: Optional[asyncpg.Connection] = None
    tx_object: Optional[asyncpg_transaction.Transaction] = None

    try:
        connection = await asyncpg.connect(dsn=db_test_dsn)
        if connection is None:
            pytest.fail(
                "Failed to create direct database connection for test function."
            )

        tx_object = connection.transaction()
        await tx_object.start()  # Start transaction

        yield connection

    except Exception as e:
        print(
            f"Error in db_conn fixture setup or during test execution with DB: {e}",
            file=sys.stderr,
        )
        if (
            tx_object is not None
            and hasattr(tx_object, "_state")
            and tx_object._state == asyncpg_transaction.TransactionState.STARTED
        ):
            try:
                await tx_object.rollback()
                print(
                    "Transaction rolled back due to error in db_conn setup/yield.",
                    file=sys.stderr,
                )
            except Exception as rb_err:
                print(
                    f"Error during emergency rollback in db_conn: {rb_err}",
                    file=sys.stderr,
                )
        raise
    finally:
        if (
            tx_object is not None
            and hasattr(tx_object, "_state")
            and tx_object._state == asyncpg_transaction.TransactionState.STARTED
        ):
            try:
                await tx_object.rollback()
                print(
                    "Transaction rolled back in finally block of db_conn.",  # Clarified message
                    file=sys.stderr,
                )
            except Exception as e:
                print(
                    f"Error during transaction rollback in finally: {e}",
                    file=sys.stderr,
                )

        if connection and not connection.is_closed():
            await connection.close()


@pytest.fixture
async def created_test_user(db_conn: asyncpg.Connection) -> Dict[str, Any]:
    user_repo = UserRepository(connection=db_conn)
    username = f"test_user_{uuid.uuid4().hex[:8]}"
    password = "aSecurePassword123!"
    hashed_password = get_password_hash(password)

    user = await user_repo.add_user(username=username, hashed_password=hashed_password)

    assert user is not None, f"Failed to create test user '{username}' for test setup."
    assert user.id is not None, "Created test user has no ID."

    return {
        "id": user.id,
        "username": username,
        "password": password,
        "hashed_password": hashed_password,
    }
