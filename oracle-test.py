# oracle-test.py (new version)
import os
import oracledb
from decouple import config
import logging

# Configure basic logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def run_app():
    try:
        # Load configuration from .env file
        db_user = config('USER_ORACLE')
        db_password = config('PASSWORD_ORACLE')
        tns_name = config('NAME_ORACLE')
        wallet_directory = config('WALLET_DIRECTORY')
        wallet_password = config('WALLET_PEM_PASS_PHRASE', default='')

        logging.info(f"Attempting to connect with user '{db_user}' and TNS name '{tns_name}'.")
        logging.info(f"Using wallet directory: '{wallet_directory}'")

        # Check if wallet directory exists
        if not wallet_directory or not os.path.exists(wallet_directory):
            logging.error(f"Wallet directory not found at the specified path: {wallet_directory}")
            return

        # Connect using Thin mode (no Oracle Client needed)
        # Pass config_dir and wallet_location directly to create_pool
        logging.info("Using python-oracledb Thin mode.")

        # Create a connection pool using the wallet configuration
        # The 'dsn' should be the TNS alias defined in your tnsnames.ora file (part of the wallet)
        pool_kwargs = {
            'user': db_user,
            'password': db_password,
            'dsn': tns_name,
            'config_dir': wallet_directory,
            'wallet_location': wallet_directory,
        }
        if wallet_password:
            pool_kwargs['wallet_password'] = wallet_password
            
        pool = oracledb.create_pool(**pool_kwargs)
        logging.info("Connection pool created.")

        logging.info("Acquiring connection from pool...")
        with pool.acquire() as connection:
            logging.info("Connection acquired successfully.")
            with connection.cursor() as cursor:
                logging.info("Executing test query 'SELECT 1 FROM DUAL'...")
                cursor.execute("SELECT 1 FROM DUAL")
                result = cursor.fetchone()
                if result:
                    print(f"✅ --- Database connection successful! ---")
                    print(f"Query result: {result[0]}")
                else:
                    print(f"⚠️ --- Connection successful, but query returned no result. ---")

    except oracledb.Error as e:
        print(f"❌ --- Database connection failed! ---")
        print(f"An Oracle error occurred: {e}")
        print("\n💡 Troubleshooting Tips:")
        print("1. Verify that the USER_ORACLE, PASSWORD_ORACLE, NAME_ORACLE, and WALLET_DIRECTORY in your .env file are correct.")
        print("2. Ensure the Oracle Wallet files are correctly placed in the specified directory.")
        print(f"3. The error 'ORA-12506' (if you see it again) strongly suggests a server-side ACL (Access Control List) issue. Contact your DBA to ensure this server's IP is allowed to connect.")

    except Exception as e:
        import traceback
        print(f"❌ --- An unexpected error occurred! ---")
        traceback.print_exc()

if __name__ == "__main__":
    run_app()
