import logging
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any, Hashable

import pandas as pd
import requests
from constant_parameters import COLUMNS, DATA, HEADERS, PARAMS, SCANNER_URL
from pandas import DataFrame
from requests import Response

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(funcName)s - %(levelname)s - %(message)s",
    handlers=[logging.FileHandler("stock_analysis.log"), logging.StreamHandler()],
)
logger: logging.Logger = logging.getLogger(__name__)


class TradingViewError(Exception):
    """Custom exception for TradingView API related errors."""

    pass


def create_database_path() -> Path:
    """Create database directory and return path for today's database file."""
    logger.debug("Creating database path")
    try:
        db_dir = Path("src/database")
        db_dir.mkdir(exist_ok=True)
        logger.debug(f"Database directory created/verified: {db_dir}")

        date_str: str = datetime.now().date().strftime("%Y-%m-%d")
        db_path: Path = db_dir / f"{date_str}.db"

        logger.info(f"Database path created: {db_path}")
        return db_path
    except Exception as e:
        logger.error(f"Failed to create database path: {e}")
        raise TradingViewError(f"Database path creation failed: {e}")


def create_sql_db(path: Path, df: DataFrame) -> None:
    """Save DataFrame to SQLite database with proper connection handling."""
    logger.debug(f"Saving data to database: {path}")
    try:
        with sqlite3.connect(path) as conn:
            df.to_sql("stock_data", conn, if_exists="replace", index=False)
            logger.info(f"Successfully saved {len(df)} records to database: {path}")
    except Exception as e:
        logger.error(f"Failed to save data to database {path}: {e}")
        raise TradingViewError(f"Database save operation failed: {e}")


def response_to_df(response: Response) -> DataFrame:
    """Parse API response and convert to DataFrame with validation."""
    logger.debug("Converting API response to DataFrame")
    try:
        json_response: dict[str, list[Any]] = response.json()
        logger.debug(f"Response keys found: {list(json_response.keys())}")

        data: list[dict[str, Any]] | None = json_response.get("data", None)

        if not data:
            logger.error("No 'data' key found in API response")
            raise TradingViewError("Unable to find 'data' key in response")

        logger.debug(f"Found {len(data)} data items in response")

        # Filter out None values and log warnings for missing data
        rows: list[Any] = []
        for i, row in enumerate(data):
            row_data: Any | None = row.get("d", None)
            if row_data is None:
                logger.warning(f"Row {i} missing 'd' key, skipping")
                continue
            rows.append(row_data)

        if not rows:
            logger.error("No valid rows found after filtering")
            raise TradingViewError("Unable to find valid rows in response")

        df: DataFrame = pd.DataFrame(rows, columns=list(COLUMNS.values()))
        logger.info(
            f"Successfully created DataFrame with {len(df)} rows and {len(df.columns)} columns"
        )

        # Log column names for debugging
        logger.debug(f"DataFrame columns: {list(df.columns)}")

        return df

    except requests.exceptions.JSONDecodeError as e:
        logger.error(f"Failed to decode JSON response: {e}")
        raise TradingViewError(f"Invalid JSON response: {e}")
    except Exception as e:
        logger.error(f"Unexpected error converting response to DataFrame: {e}")
        raise TradingViewError(f"Response conversion failed: {e}")


def get_response() -> Response:
    """Fetch data from TradingView API with comprehensive error handling."""
    logger.info("Fetching data from TradingView API")
    logger.debug(f"API URL: {SCANNER_URL}")

    try:
        response: Response = requests.post(
            url=SCANNER_URL,
            headers=HEADERS,
            params=PARAMS,
            data=DATA,
            timeout=30,  # Add timeout for better error handling
        )

        logger.debug(f"API response status code: {response.status_code}")
        logger.debug(f"Response headers: {dict(response.headers)}")

        response.raise_for_status()

        logger.info("Successfully received response from TradingView API")
        return response

    except requests.exceptions.Timeout as e:
        logger.error(f"API request timed out after 30 seconds: {e}")
        raise TradingViewError(f"API request timeout: {e}")
    except requests.exceptions.ConnectionError as e:
        logger.error(f"Connection error when accessing TradingView API: {e}")
        raise TradingViewError(f"Connection failed: {e}")
    except requests.exceptions.HTTPError as e:
        logger.error(f"HTTP error from TradingView API: {e}")
        raise TradingViewError(f"HTTP error: {e}")
    except Exception as e:
        logger.error(f"Unexpected error accessing TradingView API: {e}")
        raise TradingViewError(f"Unable to access TradingView API: {e}")


def scrape_data() -> None:
    """Main function to scrape stock data and save to database."""
    logger.info("Starting stock data scraping process")

    try:
        # Step 1: Get response from API
        logger.info("Step 1: Fetching data from TradingView API")
        response: Response = get_response()

        # Step 2: Convert response to DataFrame
        logger.info("Step 2: Converting response to DataFrame")
        df: DataFrame = response_to_df(response)

        # Step 3: Create database path
        logger.info("Step 3: Creating database path")
        db_path: Path = create_database_path()

        # Step 4: Save to database
        logger.info("Step 4: Saving data to database")
        create_sql_db(db_path, df)

        logger.info("Stock data scraping completed successfully")
        logger.info(f"Data saved to: {db_path}")

    except TradingViewError as e:
        logger.error(f"TradingView error during scraping: {e}")
        raise
    except Exception as e:
        logger.error(f"Unexpected error during scraping process: {e}")
        raise TradingViewError(f"Error while scraping data: {e}")


def get_table_overview() -> str:
    """Get database table schema and preview with proper error handling.

    This function retrieves the schema and a sample row from the stock_data table
    in the SQLite database. If the database doesn't exist, it automatically
    triggers data scraping to create it.

    Returns:
        str: A formatted string containing:
            - Database table name
            - Complete schema information with column details
            - Preview of table values (first row)

    Raises:
        TradingViewError: If unable to access the database or retrieve table information
    """
    logger.info("Getting table overview")

    try:
        database_path: Path = create_database_path()
        logger.debug(f"Checking if database exists at: {database_path}")

        if not database_path.exists():
            logger.warning(
                f"Database file not found at {database_path}, scraping new data"
            )
            scrape_data()

        with sqlite3.connect(database_path) as conn:
            # Get table schema
            schema_query = "PRAGMA table_info(stock_data);"
            schema: DataFrame = pd.read_sql_query(schema_query, conn)
            logger.debug(f"Retrieved schema with {len(schema)} columns")

            # Get table preview
            preview_query = "SELECT * FROM stock_data LIMIT 1;"
            preview: DataFrame = pd.read_sql_query(preview_query, conn)
            logger.debug(f"Retrieved preview with {len(preview)} rows")

        # Format output with proper spacing
        schema_dict: list[dict[Hashable, Any]] = schema.to_dict(orient="records")
        preview_dict: list[dict[Hashable, Any]] = preview.to_dict(orient="records")

        overview: str = (
            "The database table name: `stock_data`.\n"
            f"The following is the schema of the data table `stock_data`: {schema_dict}\n"
            f"The following is the preview of the table values: {preview_dict}"
        )

        logger.info("Successfully generated table overview")
        return overview

    except Exception as e:
        logger.error(f"Failed to get table overview: {e}")
        raise TradingViewError(f"Unable to get table overview: {e}")


if __name__ == "__main__":
    overview: str = get_table_overview()
    print(overview)
