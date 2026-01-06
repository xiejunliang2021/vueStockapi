# -*- coding: UTF-8 -*-
'''
@Project ：vueStockapi 
@File ：test_oracle.py
@Author ：Anita_熙烨（路虽远，行则降至！事虽难，做则必成！）
@Date ：2025/11/19 10:20 
@JianShu : 
'''
# Follow driver installation and setup instructions here:
# https://www.oracle.com/database/technologies/appdev/python/quickstartpython.html

import oracledb
# Replace USER_NAME, PASSWORD with your username and password
DB_USER = "huabenwuxin"
DB_PASSWORD = "19861023Xjl_"
# If you want to connect using your wallet, comment out the following line.
CONNECT_STRING = '(description= (retry_count=20)(retry_delay=3)(address=(protocol=tcps)(port=1522)(host=adb.ap-melbourne-1.oraclecloud.com))(connect_data=(service_name=geb977e4f1273f7_stockapi_medium.adb.oraclecloud.com))(security=(ssl_server_dn_match=yes)))'
def run_app():
	try:
		# If THICK mode is needed, uncomment the following line.
		#oracledb.init_oracle_client()

		# If you want to connect using your wallet, uncomment the following CONNECT_STRING line.
		# dbname - is the TNS alias present in tnsnames.ora dbname
		# CONNECT_STRING = "dbname_medium"
		pool = oracledb.create_pool(
			# If you want to connect using your wallet, uncomment the following line.
			# config_dir="/Users/test/wallet_dbname/",
			user=DB_USER,
			password=DB_PASSWORD,
			dsn=CONNECT_STRING,
			# If THIN mode is needed and your Python version is 3.13 and above, uncomment the following lines.
			# wallet_location="/path/to/your/ewallet.pem",
			# wallet_password="WALLET_PASSWORD"
		)
		with pool.acquire() as connection:
			with connection.cursor() as cursor:
				cursor.execute("SELECT 1 FROM DUAL")
				result = cursor.fetchone()
				if result:
					print(f"Connected successfully! Query result: {result[0]}")
	except oracledb.Error as e:
		print(f"Could not connect to the database - Error occurred: {str(e)}")
	except Exception as e:
		import traceback
		traceback.print_exc()

if __name__ == "__main__":
	run_app()